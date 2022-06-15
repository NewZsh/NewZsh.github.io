---
layout: post
title: "polyphone "
date: 2022-06-06
categories: zsh blogging
---

## Build a corpus for Chinese polyphone 

In Chinese Text-to-speech (TTS) applications, one key problem is to determine a phone for polyphones. In some cases, a phone can be determined within a word or phrase. For example, '为' can pronounce 'wei2' or 'wei4', in the word '以为' (in English, think), it must pronounce as 'wei2', and in the phrase '为人民服务'(in English, serve for people), it must pronounce as 'wei4'.

However, if we can determine the phone with a large table of collected word or phrase, things get easier and NLP will not be recognized to be hard. There are two problems that come up:

1. **Tokenization is not as what we expect to be**. For example, '中国共产党以为（wei4）人民服务为宗旨'(in English, the CPC takes serving the people as its purpose)，tokenization with jieba gives the result as: '中国/共产党/以为/人民/服务/为/宗旨'. The phrase '为人民服务' is broken down and the first character '为' is observed by the character '以', wrongly formulating a word '以为'.
2. **Even if tokenization is correct, some words have different meaning in different context**. For example, '张朝(chao2)阳在北京朝(chao2)阳公园迎着朝(zhao1)阳奔跑'(in English, Zhang Chaoyang runs with the rising sun in Beijing Chaoyang Park). The first '朝阳' is a name (the founder of Sou Hu Company), the second '朝阳' is a park in Beijing, the third '朝阳' is the rising sun. The phone must be determined in context. As another example, '我在春天播种(zhong4)下希望', the word '播种' is a verb (in English, plant something), while in '春天播种(zhong3), 秋天收获', the word '播种' is a verb-object word (in English, plant seeds in the soil).

Some extremely hard case are listed for fun:

- 一把把把把住了
- 人要是行，干一行行一行，一行行，行行行。行行行，干哪行都行。要是不行，干一行不行一行，一行不行行行不行。行行不行，干哪行都不行 。要想行行行，首先一行行。成为行业内的内行，行行成内行
- 南京市长江大桥正式通车了


## 1. How many polyphones are there in Chinese?


**remark**: remember the purpose of our study, we do not stop at assigning a phone to polyphones. The target is to build a TTS aaplication, which will face the following three problems:

### a. unstressed sound
Unstressed sound is a complex phenomenum (please refer to [2]). In short, some chracters are pronounced without tonic in usage.

### b. dialect
If we expect the TTS application can adapt to personalized voice, we should tolerate some 'wrong' phones. For example, in north-east China, '那些' may pronounce as 'nei4 xie1'.

### c. ancient Chinese
In ancient Chinese, some characters have extra phones. For example, '雨(yu3)' only has a single phone in modern Chinese, but in ancient Chinese, it can pronouce as 'yu4' (used as a verb, meaning 'falling like rain from the sky') like in '天雨雪' (in English, it snows).

## 2. Spider

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
