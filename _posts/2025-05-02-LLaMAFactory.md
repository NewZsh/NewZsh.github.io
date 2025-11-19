---
layout: post
title: "LLaMA Factory 代码拆解"
date: 2025-05-02
categories: zsh blogging
---
learning based on [this version] (https://github.com/hiyouga/LLaMA-Factory/tree/59a56f7226f24b3b8c37b6a4da0a5802b4022ead)

背景：训练know how的几个维度

- 数据（预处理、质量、比例）
- 训练技巧（退火、平均，packing/batching）
- 训练框架（超参数、损失函数计算、框架逻辑、训练效率）
- 训练结果评估（通用评测基本复现公开结果，场景评测需要增加可自动化的底线benchmark）

代码框架
```
    ├── src
    │   ├── llamafactory
    │   │   ├── data
    │   │   │   ├── **processor**
    │   │   │   │   ├── __init__.py
    │   │   │   │   ├── pretrain.py: `class PretrainProcessor(DatasetProcessor)`
    │   │   │   ├── collator.py: `SFTDataCollatorWith4DAttentionMask` --> `prepare_4d_attention_mask`
    │   │   │   ├── loader.py: `get_dataset` --> `_get_merged_dataset`(-->`_load_single_dataset`) + `_get_preprocessed_dataset`(--> `_get_dataset_processor`)
    │   │   │   ├── template.py
    │   │   │── hparams
    │   │   │   ├── model_args.py: `class ModelArguments(SGLangArguments, VllmArguments, ExportArguments, ProcessorArguments, QuantizationArguments, BaseModelArguments):`
    │   │   │   ├── finetuning_args.py: `class FinetuningArguments(SwanLabArguments, BAdamArgument, ApolloArguments, GaloreArguments, RLHFArguments, LoraArguments, FreezeArguments):`
    |   |   ├── train
    |   |   |   ├── sft
    |   |   |   |   ├── __init__.py
    |   |   |   |   ├── metric.py
    |   |   |   |   ├── trainer.py
    |   |   |   |   ├── workflow.py: `run_sft`
    |   |   |   ├── trainer_utils.py: `get_ray_trainer`
    |   |   |   ├── tuner.py: `run_exp` -->（关键参数 ray_args.use_ray） `get_ray_trainer` /--> `_training_function` --> model_args, data_args, training_args, finetuning_args, generating_args = get_train_args(args)  -->（关键参数finetuning_args.stage）run_pt/sft/rm/ppo/dpo/kto
    |   ├── train.py: --> `run_exp`
```

### GPU效率
- 理论上的batch size计算
显存分三块，模型参数记为Φ，存储参数包括：

  - param (fp32) + momentum (fp32) + variance (fp32) --> 12Φ
  - param (fp16) + gradient (fp16) --> 4Φ
  - activation (fp16)：理论上总能用时重算，但实践中也不是全部都这么做。Qwen为例，需要存储的activation的参数的上限是：
    - Layer norm:  2 [attention, FFN 各1各LN] * batch_size * seq_len * hidden_dim [忽略批输入的均值、方差]
    - Embedding: batch_size * seq_len * hidden_dim 
    - Attention
      - Q/K/V: 3 * batch_size* seq_len * (num_heads * attn_dim)
      - QK: batch_size * seq_len * seq_len * num_heads [MHA]
      - QK-softmax: batch_size * seq_len * seq_len * num_heads [MHA]
      - QKV: batch_size* seq_len * (num_heads * attn_dim)
      - Linear: batch_size * seq_len * hidden_dim
    - FFN: batch_size * seq_len * inter_dim * 4 + batch_size * seq_len * hidden_dim
    - 总体：n_layers * (4 * batch_size * seq_len * hidden_dim +  batch_size * seq_len * inter_dim * 4 + 4 * batch_size* seq_len * (num_heads * attn_dim) + 2 * batch_size * seq_len * seq_len * num_heads)  + batch_size * seq_len * hidden_dim 
      - 一般有  num_heads * attn_dim = hidden_dim 所以进一步简化为：n_layers * (8 * batch_size * seq_len * hidden_dim + batch_size * seq_len * inter_dim * 4 + 2 * batch_size * seq_len * seq_len * num_heads)  + batch_size * seq_len * hidden_dim 
      - qwen2.5-1.5B: num_heads=12, hidden_dim=1536, inter_dim=8960, n_layers=28, 激活参数数量=28 * (8 * batch_size * seq_len * 1536 + batch_size * seq_len * 8960 * 4 + 2 * batch_size * seq_len * seq_len * 12)  + batch_size * seq_len * 1536 = 1349120 * batch_size * seq_len + 56 * batch_size * seq_len * seq_len
        - seq_len = 8000时候，16Φ已经有24GB占用，剩余56GB，batch_size=4（4.18）
        - seq_len = 4000时候，batch_size=9（9.56）
        - seq_len = 2000时候，batch_size=20 （20.58）
    
  - ZeRO1/2/3
    - ZeRO2比较常用，梯度和动量、方差切分到N个卡，只有模型参数不切分，以八卡为例，每个卡存储参数量为：2Φ + 14Φ/8 = 5.625GB
    - qwen2.5-1.5B，批大小的增益相对有限
      - seq_len = 8000时候，batch_size=5（5.55）
      - seq_len = 4000时候，batch_size=12（12.69)
      - seq_len = 2000时候，batch_size = 27 （27.33）
  - activation ckpt
    Ref https://cloud.tencent.com/developer/article/2401246、https://arxiv.org/pdf/2205.05198
    - offload到CPU，恢复时间取决于PCIe传输速度，200GB/s左右
    - 分布到其他卡上，恢复时间取决于卡间通讯速度，SXM最高800GB/s左右
    - 每层记录输入，用时重算，恢复时间取决于计算速度，A800以312TFLOPS计算
    - 显然重算的耗时最短
    - Deepspeed的具体实现
      - https://www.deepspeed.ai/docs/config-json/#activation-checkpointing
      - https://lightning.ai/docs/pytorch/stable/advanced/model_parallel/deepspeed.html#deepspeed-activation-checkpointing
      - `CheckpointFunction.apply(function, all_outputs, *args)` https://github.com/deepspeedai/DeepSpeed/blob/ee492c30a716474578d6d42115f2698ab131ab79/deepspeed/runtime/activation_checkpointing/checkpointing.py#L948
  - 总体训练时间：
    - 系数：forward + backward + re-activation = 1 + 2 + 1 = 4，每个参数，一次乘法，一次加法，系数就是8
    - 8 * tokens * n_params / (n_GPU * GPU_flops * MFU_ratio) = 训练时间
    - 实际可以通过训练时间计算MFU_ratio：也就是我们的硬件使用率，注意如果没有re-activation，系数是6即可
- [图片]
      - 以GPT3-175B为例，6*174600M*300B = 3.1428E+23（表格第二列）
        - 原文中说了是V100显卡。原文没有说训练时间，普遍说法是512张V100是7个月，1024张A100是1个月
        - A100的MFU = 3.1428E+23 / (1024* 312 TFlops * 30 * 86400) = 37.9%
      - 以LLaMA-65B为例，原文讲了，2048张80GB A100，1.4TB tokens，65B 模型，21天。MFU = （6*1.4E+12*65E+9）/ (2048*312*10E+12 * 21 * 86400) = 47% 
      
- 功耗
- 利用率

### 重点函数

- `preprocess_dataset`

  代码总结 ：预训练使用了简单拼接，会产生截断，SFT packing比较合理

  Experiments checklist
    - SFT
      [x] 使用packing与否（不同的SFT processor）的loss影响？
      [x] No packing
      [ ] Packing without neat packing
      [x] Packing with neat packing
    - PrertainDatasetProcessor 对 loss 的影响？
      [ ] No packing
      [ ] Packing without neat packing
      [ ] Packing with neat packing （ref：https://github.com/hiyouga/LLaMA-Factory/issues/5601）
      [ ] 考虑到我们的预处理已经把长文本切段落了？（ref： 文本分割、预训练数据标注规范，需要确认），如何恢复超长（>= 32k token）文本的训练？
      [ ] 在不同的数据集配比（预训练语料）下，是否结论仍然成立？

    ```python
    class PretrainDatasetProcessor(DatasetProcessor):
        def preprocess_dataset(self, examples: dict[str, list[Any]]) -> dict[str, list[Any]]:
            # build grouped texts with format X1 X2 X3 ... if packing is enabled
            eos_token = "<|end_of_text|>" if self.data_args.template == "llama3" else self.tokenizer.eos_token
            text_examples = [messages[0]["content"] + eos_token for messages in examples["_prompt"]]

            if not self.data_args.packing:
                if getattr(self.tokenizer, "add_bos_token", False):
                    text_examples = [self.tokenizer.bos_token + example for example in text_examples]

                result = self.tokenizer(
                    text_examples, add_special_tokens=False, truncation=True, max_length=self.data_args.cutoff_len
                )
            else:
                tokenized_examples = self.tokenizer(text_examples, add_special_tokens=False)
                concatenated_examples = {k: list(chain(*tokenized_examples[k])) for k in tokenized_examples.keys()}
                total_length = len(concatenated_examples[list(concatenated_examples.keys())[0]])
                block_size = self.data_args.cutoff_len
                total_length = (total_length // block_size) * block_size
                result = {
                    k: [t[i : i + block_size] for i in range(0, total_length, block_size)]
                    for k, t in concatenated_examples.items()
                }
                if getattr(self.tokenizer, "add_bos_token", False):
                    for i in range(len(result["input_ids"])):
                        result["input_ids"][i][0] = self.tokenizer.bos_token_id

            return result
    ```
    
    ```python
    class SupervisedDatasetProcessor(DatasetProcessor):
        def _encode_data_example(
            self,
            prompt: list[dict[str, str]],
            response: list[dict[str, str]],
            system: Optional[str],
            tools: Optional[str],
            images: list["ImageInput"],
            videos: list["VideoInput"],
            audios: list["AudioInput"],
        ) -> tuple[list[int], list[int]]:
            messages = self.template.mm_plugin.process_messages(prompt + response, images, videos, audios, self.processor)
            input_ids, labels = self.template.mm_plugin.process_token_ids(
                [ ], [ ], images, videos, audios, self.tokenizer, self.processor
            )
            encoded_pairs = self.template.encode_multiturn(self.tokenizer, messages, system, tools)
            total_length = len(input_ids) + (1 if self.template.efficient_eos else 0)
            if self.data_args.mask_history:
                encoded_pairs = encoded_pairs[::-1]  # high priority for last turns

            for turn_idx, (source_ids, target_ids) in enumerate(encoded_pairs):
                if total_length >= self.data_args.cutoff_len:
                    break

                source_len, target_len = infer_seqlen(
                    len(source_ids), len(target_ids), self.data_args.cutoff_len - total_length
                )
                source_ids = source_ids[:source_len]
                target_ids = target_ids[:target_len]
                total_length += source_len + target_len

                if self.data_args.train_on_prompt:
                    source_label = source_ids
                elif self.template.efficient_eos:
                    source_label = [self.tokenizer.eos_token_id] + [IGNORE_INDEX] * (source_len - 1)
                else:
                    source_label = [IGNORE_INDEX] * source_len

                if self.data_args.mask_history and turn_idx != 0:  # train on the last turn only
                    target_label = [IGNORE_INDEX] * target_len
                else:
                    target_label = target_ids

                if self.data_args.mask_history:  # reversed sequences
                    input_ids = source_ids + target_ids + input_ids
                    labels = source_label + target_label + labels
                else:
                    input_ids += source_ids + target_ids
                    labels += source_label + target_label

            if self.template.efficient_eos:
                input_ids += [self.tokenizer.eos_token_id]
                labels += [self.tokenizer.eos_token_id]

            return input_ids, labels 
            
        def preprocess_dataset(self, examples: dict[str, list[Any]]) -> dict[str, list[Any]]:
            # build inputs with format <bos> X Y <eos> and labels with format <ignore> ... <ignore> Y <eos>
            # for multiturn examples, we only mask the prompt part in each prompt-response pair.
            model_inputs = defaultdict(list)
            for i in range(len(examples["_prompt"])):
                if len(examples["_prompt"][i]) % 2 != 1 or len(examples["_response"][i]) != 1:
                    logger.warning_rank0(
                        "Dropped invalid example: {}".format(examples["_prompt"][i] + examples["_response"][i])
                    )
                    continue

                input_ids, labels = self._encode_data_example(
                    prompt=examples["_prompt"][i],
                    response=examples["_response"][i],
                    system=examples["_system"][i],
                    tools=examples["_tools"][i],
                    images=examples["_images"][i] or [ ],
                    videos=examples["_videos"][i] or [ ],
                    audios=examples["_audios"][i] or [ ],
                )
                model_inputs["input_ids"].append(input_ids)
                model_inputs["attention_mask"].append([1] * len(input_ids))
                model_inputs["labels"].append(labels)
                model_inputs["images"].append(examples["_images"][i])
                model_inputs["videos"].append(examples["_videos"][i])
                model_inputs["audios"].append(examples["_audios"][i])

            return model_inputs

    class PackedSupervisedDatasetProcessor(SupervisedDatasetProcessor):
        def preprocess_dataset(self, examples: dict[str, list[Any]]) -> dict[str, list[Any]]:
            # TODO: use position_ids to achieve packing
            # build inputs with format <bos> X1 Y1 <eos> <bos> X2 Y2 <eos>
            # and labels with format <ignore> ... <ignore> Y1 <eos> <ignore> ... <ignore> Y2 <eos>
            valid_num = 0
            batch_input_ids, batch_labels, batch_images, batch_videos, batch_audios = [ ], [ ], [ ], [ ], [ ]
            lengths = [ ]
            length2indexes = defaultdict(list)
            for i in range(len(examples["_prompt"])):
                if len(examples["_prompt"][i]) % 2 != 1 or len(examples["_response"][i]) != 1:
                    logger.warning_rank0(
                        "Dropped invalid example: {}".format(examples["_prompt"][i] + examples["_response"][i])
                    )
                    continue

                input_ids, labels = self._encode_data_example(
                    prompt=examples["_prompt"][i],
                    response=examples["_response"][i],
                    system=examples["_system"][i],
                    tools=examples["_tools"][i],
                    images=examples["_images"][i] or [ ],
                    videos=examples["_videos"][i] or [ ],
                    audios=examples["_audios"][i] or [ ],
                )
                length = len(input_ids)
                if length > self.data_args.cutoff_len:
                    logger.warning_rank0(f"Dropped lengthy example with length {length} > {self.data_args.cutoff_len}.")
                else:
                    lengths.append(length)
                    length2indexes[length].append(valid_num)
                    batch_input_ids.append(input_ids)
                    batch_labels.append(labels)
                    batch_images.append(examples["_images"][i] or [ ])
                    batch_videos.append(examples["_videos"][i] or [ ])
                    batch_audios.append(examples["_audios"][i] or [ ])
                    valid_num += 1

            model_inputs = defaultdict(list)
            knapsacks = greedy_knapsack(lengths, self.data_args.cutoff_len)
            for knapsack in knapsacks:
                packed_input_ids, packed_attention_masks, packed_labels = [ ], [ ], [ ]
                packed_images, packed_videos, packed_audios = [ ], [ ], [ ]
                for i, length in enumerate(knapsack):
                    index = length2indexes[length].pop()
                    packed_input_ids += batch_input_ids[index]
                    packed_labels += batch_labels[index]
                    packed_images += batch_images[index]
                    packed_videos += batch_videos[index]
                    packed_audios += batch_audios[index]
                    if self.data_args.neat_packing:
                        packed_attention_masks += [i + 1] * len(batch_input_ids[index])  # start from 1
                    else:
                        packed_attention_masks += [1] * len(batch_input_ids[index])

                if len(packed_input_ids) < self.data_args.cutoff_len + 1:  # avoid flash_attn drops attn mask
                    pad_length = self.data_args.cutoff_len - len(packed_input_ids) + 1
                    packed_input_ids += [self.tokenizer.pad_token_id] * pad_length
                    packed_labels += [IGNORE_INDEX] * pad_length
                    if self.data_args.neat_packing:
                        packed_attention_masks += [0] * pad_length
                    else:
                        packed_attention_masks += [1] * pad_length  # more efficient flash_attn

                if len(packed_input_ids) != self.data_args.cutoff_len + 1:
                    raise ValueError("The length of packed example should be identical to the cutoff length.")

                model_inputs["input_ids"].append(packed_input_ids)
                model_inputs["attention_mask"].append(packed_attention_masks)
                model_inputs["labels"].append(packed_labels)
                model_inputs["images"].append(packed_images or None)
                model_inputs["videos"].append(packed_videos or None)
                model_inputs["audios"].append(packed_audios or None)

            return model_inputs
    ```

### 并行
- Naive DDP
- Deepspeed
- Deepspeed megatron
一些参数
- --tokenized_path $TOKENIZED_PATH  ## 缓存tokenizer处理后的dataset

### experiments checklist
- [x] GPU 效率检查（1. 理论上的batch size计算；2. 功耗、利用率）
- [ ] length 分布，在tokenizer过程中获取长度分布
- [ ] dynamic_len  VS packing: 效率对比？性能对比？在不同的数据集配比下，是否结论仍然成立？
- [ ] packing时候长短文本loss是否需要平衡长度的影响？
- [ ] Learning rate schedule的调研：业界最佳实践？不同schedule的loss对比和效果对比？在不同的数据集配比（预训练语料）下，是否结论仍然成立？
- [ ] 如何快速验证模型的性能，减少人工评测：底线思维，不满足底线的模型产出不认可
  - [ ] Prompt editing：定向替换垂直任务SFT数据中的一些文本，查看模型是否过拟合
  - [ ] 内容替换：如会议中替换一个章节的讨论，课堂中替换一个问答片段
  - [ ] 格式替换：json  md   文本，few shot，查看格式遵循的能力是否被退化了（格式是否需要支持few shot？避免业务未来的不同需求都要反复搞）
  - [ ] 量化之后和原始版本的输出相似度越高，说明模型越稳定（对参数精度损失不敏感）？

##### remark 运行脚本
- 单机多卡

    ```
    NPROC_PER_NODE=8
    NNODES=1
    NODE_RANK=0
    MASTER_ADDR=localhost
    MASTER_PORT=6000

    MODEL_PATH=/data_share/LLM/Base_model/Qwen2.5-0.5B-Instruct
    DATASET=exp1.0
    OUTPUT_PATH=/data_share/zhangsiheng/data/sft/exp1.0

    DS_CONFIG_PATH=/data/LLaMA-Factory/examples/deepspeed/ds_z2_config.json

    DISTRIBUTED_ARGS="
        --nproc_per_node $NPROC_PER_NODE \
        --nnodes $NNODES \
        --node_rank $NODE_RANK \
        --master_addr $MASTER_ADDR \
        --master_port $MASTER_PORT
      "
    torchrun $DISTRIBUTED_ARGS /data/LLaMA-Factory/src/train.py \
        --deepspeed $DS_CONFIG_PATH \
        --stage sft \
        --do_train \
        --use_fast_tokenizer \
        --flash_attn auto \
        --model_name_or_path $MODEL_PATH \
        --dataset $DATASET \
        --template qwen \
        --finetuning_type full \
        --output_dir $OUTPUT_PATH \
        --overwrite_cache \
        --overwrite_output_dir \
        --warmup_steps 100 \
        --weight_decay 0.1 \
        --per_device_train_batch_size 16 \
        --gradient_accumulation_steps 4 \
        --ddp_timeout 9000 \
        --learning_rate 5e-6 \
        --lr_scheduler_type cosine \
        --logging_steps 1 \
        --cutoff_len 8192 \
        --save_steps 1000 \
        --plot_loss \
        --num_train_epochs 1 \
        --bf16
    ```

- 多机多卡