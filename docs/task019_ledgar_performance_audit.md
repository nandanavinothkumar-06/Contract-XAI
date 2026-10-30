# Task 019: LEDGAR Performance Audit

## Objective
Investigate the extremely slow training performance (~1.15 it/s) and ~60 hour runtime on a single Google Colab T4 GPU for the LEDGAR Legal-BERT experiment, preserving the exact data counts (846,274 provisions) and 12,608 unique labels.

## 1. Why Trainer reports 527,777 steps
The current setup configures `num_train_epochs = 3` and `per_device_train_batch_size = 8`.
With a verified training split of exactly `674,068` provisions, the expected steps should be exactly `252,777` steps:
`ceil(674,068 / 8) = 84,259 steps per epoch * 3 epochs = 252,777 steps total`.
The reported figure of `527,777` strongly indicates the runtime evaluated an outdated configuration—specifically, the earlier buggy split where all `844,443` usable provisions fell into `train` and the epoch count was increased to `5`:
`ceil(844,443 / 8) = 105,556 steps per epoch * 5 epochs = 527,780 steps`.

## 2. Calculated Expected Steps (Correct Split)
- **Dataset Size (Train)**: 674,068
- **Batch Size**: 8
- **Gradient Accumulation Steps**: 1
- **Epochs**: 3
- **Mathematical Expectation**: `ceil(674,068 / 8) * 3 = 252,777` steps.

## Configuration Analysis

| Metric | Current Value | Source |
| :--- | :--- | :--- |
| **3. per_device_train_batch_size** | `8` | `src/models/run_task019_experiments.py:501` |
| **4. gradient_accumulation_steps** | `1` | `src/models/config.py:25` |
| **5. Effective Batch Size** | `8` | Computed (`8 * 1`) |
| **6. Number of Epochs** | `3` | `src/models/run_task019_experiments.py:500` |
| **7. Max Sequence Length** | `512` | `src/models/run_task019_experiments.py:419` |
| **8. Padding Type** | **Static** (`"max_length"`) | `src/models/run_task019_experiments.py:420` |
| **9. Tokenization Repetition** | **Yes (Endless)** | On-the-fly inside `__getitem__` |

## Technical Bottlenecks Identified

1. **Static Padding (`padding="max_length"`)**:
   Every single provision is padded out to exactly 512 tokens, regardless of whether the text is 10 words or 500 words. This forces the GPU to perform matrix multiplications on pure empty space padding for the vast majority of sequences, crippling throughput.

2. **Synchronous On-The-Fly Tokenization**:
   `LazyLedgarDataset` tokenizes text dynamically inside `__getitem__()`. This forces the CPU to re-tokenize the exact same text string completely from scratch `3` times (once per epoch). This chokes the data loading pipeline and creates a severe CPU bottleneck before the GPU can even receive the data.

3. **Missing FP16 (Mixed Precision)**:
   The `TrainingArguments` in `src/models/training.py` do not enable `fp16=True`. Training is operating entirely in standard FP32. Enabling FP16 on a Tesla T4 GPU unlocks Tensor Cores, halving VRAM requirements and yielding nearly a 2x throughput boost.

4. **Single-Threaded DataLoader**:
   `dataloader_num_workers` is left at the default `0`, meaning all disk reads and on-the-fly tokenizations are executing synchronously on the main thread.

5. **Logging Overhead**:
   `report_to` is left as default, attempting to reach Weights & Biases (W&B) and other integrations, which can cause network IO latency during rapid step execution.

## Safe Performance Optimizations (Recommended Next Steps)
These modifications will dramatically accelerate training while strictly preserving all `846,274` provisions, the `12,608` label space, and the verified `contract_id` group-aware splits.

1. **Implement Dynamic Padding**: 
   Remove `padding="max_length"` from the tokenizer configuration. Replace it with HuggingFace's `DataCollatorWithPadding(tokenizer)`. This will dynamically pad each batch only to the longest sequence *in that specific batch*, massively reducing wasted FLOPs.
2. **Pre-tokenize via `datasets.Dataset.map()`**: 
   Discard `LazyLedgarDataset` completely. Convert the Pandas DataFrames to HuggingFace `Dataset` objects and use `.map()` with `batched=True` to tokenize the entire corpus once. Save the tokenized cache to disk. This eliminates all tokenization overhead from the actual training loop.
3. **Enable FP16**: 
   Update `TrainingConfig` and `prepare_trainer` to accept and set `fp16=True` in `TrainingArguments` to unlock T4 Tensor Cores.
4. **Optimize DataLoader & Batching**: 
   Set `dataloader_num_workers=2` (or 4). Optionally, increase effective batch size through `gradient_accumulation_steps=2` or `4` to ensure stable learning curves on multilabel classification.
5. **Disable W&B**: 
   Set `report_to="none"` in `TrainingArguments` to prevent network telemetry overhead.
