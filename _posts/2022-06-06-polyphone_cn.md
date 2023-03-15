---
layout: post
title: "多音字消歧"
date: 2022-06-06
categories: zsh blogging
---

**EN version [https://newzsh.github.io/zsh/blogging/2022/06/06/polyphone.html]**

## 1. 任务

在中文TTS（Text-to-speech，文本转语音）系统中，一个关键的问题是为多音字确定读音（通常这个任务称为polyphone disambiguation，即多音字消歧）。

在某些情况下，一个字的读音可以在词或者短语语境内确定，比如，'为'可以读'wei2'或者'wei4'，在'以为'中读'wei2'，在'为人民服务'中读'wei4'。但是，NLP难就难在，这种情况通常不成立。问题有二：
However, if we can determine the phone with a large table of collected word or phrase, things get easier and NLP will not be recognized to be hard. There are two problems that come up:

1. **分词错误**。例如，'中国共产党以为（wei4）人民服务为宗旨'，jieba分词的结果是'中国/共产党/以为/人民/服务/为/宗旨'
2. **即使分词正确，一些词在上下文中也具有不同含义**。例如，
     '张朝(chao2)阳在北京朝(chao2)阳公园迎着朝(zhao1)阳奔跑'
     '我在春天播种(zhong4)希望' '春天播种(zhong3), 秋天收获'
     
其它一些经典case：

- 一把把把把住了
- 人要是行，干一行行一行，一行行，行行行。行行行，干哪行都行。要是不行，干一行不行一行，一行不行行行不行。行行不行，干哪行都不行 。要想行行行，首先一行行。成为行业内的内行，行行成内行
- 南京市长江大桥正式通车了


## 2. 中文多音字语料构建

Chinese Polyphone with Pinyin (CPP), 见[g2pM](https://github.com/kakaobrain/g2pM)，应该是当前唯一公开的中文多音字数据集，包含了训练、验证和测试集的切分。然而其中的错误非常多，末尾的附录会详细说明。这里介绍我如何构建语料，并进行开源()：

1. 首先搞清楚，中文有多少个常用多音字。[g2pM](https://github.com/kakaobrain/g2pM)中， `./g2pM/digest_cedict.pkl`记录了汉字的读音，但是其中有一些多音字（'丌', '乀'等）不常用，也有字的读音出现缺少、增多或者错误，我手动修改了多音字读音（注意，非多音字的字的读音未经检查）,原有791个多音字，经过修改后有612个。（此外，`./g2pM/class2idx.pkl`文件其实没什么用。）
  
2. 搜集拼音下的组词。[phrase-pinyin-data](https://github.com/mozillazg/phrase-pinyin-data)中，`./large-pinyin.txt`搜集了大量的词语和对应的读音。经过处理，可以得到多音字的不同读音能组成什么词语。例子如下：
  
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

  可以看到，这份数据很脏。幸运的是'行'在`./g2pM/digest_cedict.pkl`中的读音是对的，只有'xing2'和'hang2'。利用它对上面的词表进行过滤，转换成为以词为索引的格式，以下称为**PCP表**（phrase-character-pinyin）。PCP表形如：
  
  > 清浄无为	{"为": "wei2"}
  > 
  > 痛痛切切	{"切": \["qie4"\]}
  > 
  > 调调	{"调": \["diao4"\]}
  > 
  > 走了和尚走不了寺	{"了": \["le", "liao3"\]}
  > 
  > 好善恶恶	{"恶": \["wu4", "e4"\]}

第一行是一个多音字仅出现一次的例子，第二、三行是多音字重复出现但是读音不变的例子，读音列表中仅有一个元素，第四、五行是多音字重复出现且读音改变的例子，读音列表中的拼音与出现的次数相同、顺序相应。
  
3. 使用权威字典检查PCP表。[MCD7](https://github.com/CNMan/XDHYCD7th/blob/master/XDHYCD7th.txt)是现代汉语词典（第七版）的线上版本（其中包含部分错误，我强烈建议大家买一本纸质版放在手边）。可以用于矫正PCP表格的错误，这部分是通过机器捞回不一致的读音之后人工审核的。例如，'部分'标注的是'bu4 fen4'，但是正确的'bu4 fen5'。

4. 爬取语料并清洗。对PCP表中的每个词语，爬取百度百科的词条并清洗语料，爬取过程见附录。清洗

## 3. 模型

1. 测试标准

2. 性能

|  acc   |  dev    | test  |
|  ----  | ----    | ----  |
| Chinese Bert	| 97.95 | 97.85 |
| g2pM   | 97.36	| 97.31 |
| g2pW
| ours   | 97.90  | 99.01\% |

## 4. 未来工作

谨记我们的研究目的，不是停留在为多音字指定一个拼音，而是支撑TTS应用。因此还有至少如下问题需要解决

### a. 一个分句中多音字的联合建模

一个分句中如果有多个多音字，按照排列组合有很多种可能性，但是实际上，由于语义之间的相互约束，某些可能性是不必考虑的。比如“强”“行”都是多音字，但是“强行”只能发音为“qiang2 xing2”，“教”“会”都是多音字，但是“教会”只能发音为“jiao4 hui4”或者“jiao1 hui4”。所以，下一步可以构建一个单句包含多个多音字的语料，训练一个模型捕捉其潜在关系。

### b. 轻声
轻声是一个复杂的语言现象([2])。简单来说，很多字在使用中都可以发轻声。

### c. 方言
TTS合成方言可以考虑两个路线，一个是基于规范音素合成带地方特色的音色，一个是在文本转音素的时候就出地方特色。如果采用后者，我们就要扩充词典，使其包含一些“错误的”读音。例如，在东北方言，'那些'发音为'nei4 xie1'。

### d. 古汉语
现代汉语有很多成语和常用的诗词都来自古汉语。古汉语中，一些现代汉语中不作为多音字使用的字有多个读音，比如 '雨(yu3)' 在现代汉语只有读音，但是在古汉语也能读'yu4'(作动词用)，如在'天雨雪'中读'yu4'。




# 参考
[1] jieba
[2] Unstressed sound: https://baike.baidu.com/item/%E8%BD%BB%E5%A3%B0/5667261?fr=aladdin

# 附录

## 1. CPP数据集的错误更正



## 2. 爬虫

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

