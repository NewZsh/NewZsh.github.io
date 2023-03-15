---
layout: post
title: "polyphone "
date: 2022-06-06
categories: zsh blogging
---

## Build a corpus for Chinese polyphone 

**[中文版](https://newzsh.github.io/zsh/blogging/2022/06/06/polyphone_cn.html)**

In Chinese Text-to-speech (TTS) applications, one key problem is to determine a phone for polyphones. In some cases, a phone can be determined within a word or phrase. For example, '为' can pronounce 'wei2' or 'wei4', in the word '以为' (in English, think), it must pronounce as 'wei2', and in the phrase '为人民服务'(in English, serve for people), it must pronounce as 'wei4'.

However, if we can determine the phone with a large table of collected word or phrase, things get easier and NLP will not be recognized to be hard. There are two problems that come up:

1. **Tokenization is not as what we expect to be**. For example, '中国共产党以为（wei4）人民服务为宗旨'(in English, the CPC takes serving the people as its purpose)，tokenization with jieba gives the result as: '中国/共产党/以为/人民/服务/为/宗旨'. The phrase '为人民服务' is broken down and the first character '为' is observed by the character '以', wrongly formulating a word '以为'.
2. **Even if tokenization is correct, some words have different meaning in different context**. For example, '张朝(chao2)阳在北京朝(chao2)阳公园迎着朝(zhao1)阳奔跑'(in English, Zhang Chaoyang runs with the rising sun in Beijing Chaoyang Park). The first '朝阳' is a name (the founder of Sou Hu Company), the second '朝阳' is a park in Beijing, the third '朝阳' is the rising sun. The phone must be determined in context. As another example, '我在春天播种(zhong4)下希望', the word '播种' is a verb (in English, plant something), while in '春天播种(zhong3), 秋天收获', the word '播种' is a verb-object word (in English, plant seeds in the soil).

Some extremely hard case are listed for fun:

- 一把把把把住了
- 人要是行，干一行行一行，一行行，行行行。行行行，干哪行都行。要是不行，干一行不行一行，一行不行行行不行。行行不行，干哪行都不行 。要想行行行，首先一行行。成为行业内的内行，行行成内行
- 南京市长江大桥正式通车了


## 1. How many polyphones are there in Chinese?

I start my work from previous works:

- g2PM: https://github.com/kakaobrain/g2pM

  In this repo, there is a CPP dataset with train/dev/test split. Besides, at path `./g2pM/digest_cedict.pkl`, the file records 791 polyphones (but some are rarely used, like '丌', '乀', and etc, I delete them by hand and get 374 polyphones). 
  
  Note that at path `./g2pM/class2idx`, there are 876 phones, but it is not complete. At least, it misses the following phones: huo5, he5, di5, xiong4, xue4, deng1, lv3, long5, hong5, xie3, zheng5, dou5, fen5, gan5, pai3, dang5, feng5, lv4, tiao5, chu5, fang5, ha4.
  
- phrase-pinyin-data: https://github.com/mozillazg/phrase-pinyin-data

  In this repo, `./large-pinyin.txt` a large collected table for phrase and phones. I collect the characters with different phones and get the words and phrases that they in. For example, 
  
  > 行 xíng	一一行行/一一行行/一介行人/一介行李/一意孤行/ ……
  > 
	>   háng	一分行情一分货/一百二十行/一目五行/一目十行/一目数行/ ……
	>   
	>   xí	便把令来行
	>   
	>   hàng	树行子
	>   
	>   xing	言信行直
	>   
	>   héng	道行

  It is too dirty! 
  
  Luckily, '行' in `g2PM` repo only has two phones: 'xing2', 'hang2'. It is feasible to use `g2PM` to filter this data! After filtering, I have a table containing 115260 words and phrases, each one corresponds to a polyphones (I will call it `PCP-table`). For example:
  
  > 清浄无为	{"为": "wei2"}
  > 
  > 痛痛切切	{"切": \["qie4"\]}
  > 
  > 调调	{"调": \["diao4"\]}
  > 
  > 走了和尚走不了寺	{"了": \["le", "liao3"\]}
  > 
  > 好善恶恶	{"恶": \["wu4", "e4"\]}

The first line is an example that the word contains only one goal polyphone, and the phone is recorded as string type. The second and third lines are examples that the word contains multiple goal polyphones with **SAME** phone, and the phone is recorded as list type. The fourth and fifth lines are examples that the word contains multiple goal polyohoens with **DIFFERERENT** phones, and the order corresponds to its order in the word **one by one**.
  
- official dictionary: https://github.com/CNMan/XDHYCD7th/blob/master/XDHYCD7th.txt

  Finally, I use it to adjust some remainning error. For example, '部分' is wrongly labelled as 'bu4 fen4', but the true label is 'bu4 fen5'. (The online dictionary has some typos too. I strongly recommend you to buy a print version on hand!)
  
**remark**: remember the purpose of our study, we do not stop at assigning a phone to polyphones. The target is to build a TTS aaplication, which will face the following three problems:

### a. unstressed sound
Unstressed sound is a complex phenomenum (please refer to [2]). In short, some chracters are pronounced without tonic in usage.

### b. dialect
If we expect the TTS application can adapt to personalized voice, we should tolerate some 'wrong' phones. For example, in north-east China, '那些' may pronounce as 'nei4 xie1'.

### c. ancient Chinese
In ancient Chinese, some characters have extra phones. For example, '雨(yu3)' only has a single phone in modern Chinese, but in ancient Chinese, it can pronouce as 'yu4' (used as a verb, meaning 'falling like rain from the sky') like in '天雨雪' (in English, it snows).

## 2. Spider

  The `PCP-table` is treated as correct label, now the task is to get some sentences containing the words and phrases. Here I use [Ba](https://baike.baidu.com/) as a source. Codes here ~:
  
```python3
from lxml import etree
import requests
import json
from urllib.parse import quote

USER_AGENT = 'XXXX'

# load PCP_table

nn = 0
for word, phone in PCP_table:
    resp = requests.get('https://baike.baidu.com/item/%s' % (quote(word)),
            headers={'User-Agent': USER_AGENT},
            timeout=5
        )

    if '您所访问的页面不存在' in resp.content.decode():
        continue

    time.sleep(0.1)
    html = etree.HTML(resp.text)

    elements = html.xpath('//div[@class="lemmaWgt-subLemmaListTitle"]')
    if len(elements) > 0:
        signal = ''.join(elements[0].xpath('.//text()')).strip()
        if signal.startswith('这是一个多义词'):
            for item in html.xpath('//*[starts-with(@href, "/item")]'):
                if ''.join(item.xpath('./text()')) == '%s：汉语词汇' % word:
                    url = 'https://baike.baidu.com' + item.xpath('./@href')[0]
                    resp = requests.get(url,
                            headers={'User-Agent': USER_AGENT},
                            timeout=5
                        )
                    html = etree.HTML(resp.text)

    # get sentences
    for i in html.xpath('.//div[@class="para"]'):
        t = ''.join(i.xpath('.//text()')).strip().replace('\n', '').replace(' ', '')
        if word in t and len(t) > len(word) + 10 and ('读音' not in t and '汉语词语' not in t):
            f = open('sentence.txt', 'a+')
            f.write(json.dumps({'sentence': t, 'word': word, 'phone': phone}) + '\n')
            f.close()
```

## 3. Post-process

## 4. Build model

public data from:
  https://github.com/kakaobrain/g2pM

performace:

|  acc   |  dev    | test  |
|  ----  | ----    | ----  |
| Chinese Bert	| 97.95 | 97.85 |
| g2pM   | 97.36	| 97.31 |
| ours   | 97.90  | 98.07 |

### Support or Contact

Having trouble with Pages? Check out our [documentation](https://docs.github.com/categories/github-pages-basics/) or [contact support](https://support.github.com/contact) and we’ll help you sort it out.


# reference
[1] jieba
[2] Unstressed sound: https://baike.baidu.com/item/%E8%BD%BB%E5%A3%B0/5667261?fr=aladdin
