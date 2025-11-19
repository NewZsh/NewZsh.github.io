---
layout: post
title: "大模型推理的成本计算（草稿）"
date: 2025-07-15
categories: zsh blogging
---

## 概述

本文分析大模型（以DeepSeek为例）推理过程中的成本计算，主要关注Prefill和Decode两个阶段的性能瓶颈和成本优化策略。

---

## 1. Decode阶段分析

### 1.1 性能瓶颈

在Decode阶段，从核心计算速度来看，不存在计算瓶颈。真正的制约因素在于：
- **显存大小**：能存放的数据量
- **显存带宽**：将参数从内存搬运到计算核心的速度

### 1.2 理论计算

对于DeepSeek模型：
- 每张卡的参数量：`671B / 8 = 84GB`
- 理论token生成速度：`4.8TB/s / 84GB = 57 token/s`
- 实际速度（考虑搬运效率）：约 `30 token/s`

这个数据与梁斌使用AMD MI300X（内存带宽5.3TB/s）在并发=1时的测试结果基本吻合。

### 1.3 卡间传输分析

- **SXM互联速度**：900GB/s
- **特点**：虽然小于GPU内存带宽，但Decode阶段只需搬运 `batch × dimension` 大小的矩阵，远小于模型参数
- **结论**：瓶颈不在卡间传输

---

## 2. Prefill阶段分析

### 2.1 计算瓶颈

Prefill阶段受限于**计算瓶颈**。假设：
- 批处理大小：`bs` 条请求
- Prompt长度：1000 tokens

#### 计算量分析

每个参数至少经过一次乘法和加法：

```
计算量 = bs × 1000 × 84GB × 2
```

当 `bs = 23` 时：
```
计算量 = 3864 × 10^12 FLOPS
```
已经接近H200的算力上限。

### 2.2 不同硬件对比

**AMD MI300X (FP8)**：
- 算力：5.2 PFLOPS
- 一秒处理的batch size：约30
- 特点：`bs < 32` 时，`token/s` 与 `bs` 成正比；超过32后增加bs会带来阻塞

**8卡系统吞吐量**：
- 流水线处理：8张卡一秒可处理8个batch
- 每个batch大小：约20
- TPOT：50ms（详见下文计算）
- 每秒吐出token数：`8 × 20 × 20 = 3200 token/s`

### 2.3 与英伟达官方数据对比

根据[NVIDIA博客](https://blogs.nvidia.com/blog/deepseek-r1-nim-microservice/)：

> "The DeepSeek-R1 NIM microservice can deliver up to 3,872 tokens per second on a single NVIDIA HGX H200 system."

我们的计算结果与官方数据大致吻合。

### 2.4 显存和传输分析

#### 显存占用（无瓶颈）

- **模型参数**：84GB
- **输入特征**：`bs × 1000 × 7168`
- **KV Cache**：`bs × promptLen × (128 × 4.5) × 8`
  - 128：attention value维度
  - 4.5：MLA理论估算倍数
  - 8：8层打到一张卡

当 `bs = 23` 时：
- 输入特征：约0.165GB
- KV Cache：约0.106GB
- **结论**：远未达到显存瓶颈

#### 卡间传输（无瓶颈）

- 搬运数据量：`bs × 1000 × 7168`
- 当 `bs = 23` 时：0.165GB
- **结论**：卡间传输可忽略不计

### 2.5 结论

**Prefill阶段的瓶颈在计算能力。**

---

## 3. 延迟指标分析

### 3.1 TTFT (Time To First Token)

**假设**：2秒内完成Prefill
- 一台8卡H200可以处理 `batch = 50`
- **优化思路**：通过展示"搜索中"等待动画，降低用户对延迟的感知，争取更大的TTFT空间

### 3.2 TPOT (Time Per Output Token)

#### 用户预期

假定用户接受1分钟生成1000 tokens（包含thinking + response，R1模型的实际速度）：

```
TPOT ≈ 60s / 1000 = 50ms
```

#### 延迟构成分析

**情况1：每张卡84GB参数**

显存带宽延迟：
```
延迟 = (84GB + bs × 7168 × 2) / 4.8TB/s ≈ 17.5ms
```

**情况2：优化后每张卡2GB参数**

根据DeepSeek V3报告（第19页）：
- Decode阶段使用320张卡
- 每个MoE专家单独在一张卡上
- 每张卡参数：2GB

显存带宽延迟：
```
延迟 = 2GB / 4.8TB/s ≈ 0.4ms
```

在此基础上，batch可打满显存，估计达到**10万量级**。

#### 通信延迟计算

**卡间搬运**：
- 数据量：`bs × 7168`
- 速度：900GB/s
- 当 `bs = 10w` 时，延迟约：0.8ms

**服务器间搬运**（[参考](https://zhuanlan.zhihu.com/p/678455569)）：
- 速度：100GB/s
- 当 `bs = 10w` 时，延迟约：7ms

**总延迟估算**（激活37GB参数，需要20张卡）：
```
总延迟 = 18次卡间通信 + 2次机器间通信
      = 18 × 0.8ms + 2 × 7ms
      = 28.4ms
```

加上实际延迟和少量计算，符合 **TPOT = 50ms** 的目标。

---

## 4. 成本核算

### 4.1 收入计算

**官方定价**：16 RMB / 百万token

8×H200一秒钟创造的价值：
```
收入 = 3872 × 16 / 1,000,000 = 0.062 RMB/s
```

**租赁成本**：
```
成本 = 120,000 / (30 × 24 × 3600) = 0.046 RMB/s
```

**结论**：量级对应，有合理利润空间。

### 4.2 大规模部署成本

#### Prefill算力限制

```
计算量 = bs × 1000 × 2GB × 2
```

当 `bs = 800` 时，算力饱和。考虑实际利用率50%，取 `bs = 400`。

#### 系统配置

为维持 `decode bs = 10w`：
- **Decode实例**：1个（320张卡）
- **Prefill实例**：10个（每个32张卡）
- **总卡数**：320 + 320 = 640张卡

调整后配置（`bs = 1w`）：
- **Decode**：320张卡
- **Prefill**：10个实例 × 32张卡 = 320张卡

#### 收入与成本对比

**吞吐量**：
```
token数 = 10,000 × (1s / 50ms) = 200,000 token/s
收入 = 200,000 × 16 / 1,000,000 = 3.2 RMB/s
```

**成本**：
```
总卡数 = 320 (decode) + 320 (prefill) = 640张卡
成本 = 120,000 / 8 / 30 / 24 / 3600 × 640 = 3.7 RMB/s
```

**结论**：成本与收入量级匹配，卖API基本等于卖机器租赁价格。

---

## 5. 优化建议与结论

### 5.1 架构优化

1. **Prefill与Decode分离**
   - 云端高QPS场景应考虑分离架构
   - 参考DeepSeek V3报告的具体实施方案

2. **降低Prefill实例数**
   - Prefill必须使用高性能（昂贵）机器
   - 减少Prefill实例，降低整体batch size
   - Decode阶段可使用性能较弱、成本较低的设备（因算力非主要瓶颈）

3. **硬件选型**
   - 推理阶段可能不需要使用昂贵的SXM互联方案
   - 可根据具体显卡型号进行性价比计算

### 5.2 性能指标

- **Batch Size**：可达1万量级
- **吞吐量**：单8卡H200系统可达3,200-3,872 token/s
- **成本效益**：DeepSeek报告中的成本核算合理可行

### 5.3 总结

通过详细的性能分析和成本核算，验证了DeepSeek V3架构的合理性。在实际部署中，应根据具体QPS需求，灵活调整Prefill/Decode实例比例和硬件配置，以达到最佳性价比。

---

## 参考资料

1. [CSDN - 大模型推理优化](https://blog.csdn.net/qq_32204441/article/details/139483688)
2. [arXiv - LLM推理论文](https://arxiv.org/pdf/2311.18677)
3. [AMD MI300X产品规格](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
4. [知乎 - 服务器互联技术](https://zhuanlan.zhihu.com/p/678455569)
5. [DeepSeek-V3技术报告](https://github.com/deepseek-ai/DeepSeek-V3/blob/main/DeepSeek_V3.pdf)
6. [NVIDIA Blog - DeepSeek-R1 NIM](https://blogs.nvidia.com/blog/deepseek-r1-nim-microservice/)
7. [知乎 - 推理成本分析](https://www.zhihu.com/question/7837132971/answer/65978205766)
8. [搜狐 - AI推理技术](https://www.sohu.com/a/859885653_116132)
9. [微博 - DeepSeek讨论](https://m.weibo.cn/detail/5133555271467127#comment)
10. [雷锋网 - AI推理成本](https://www.leiphone.com/category/ai/RoIFmqrqyUclOLwP.html)
