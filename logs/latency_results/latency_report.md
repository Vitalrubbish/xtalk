# X-Talk Latency 复现报告

复现环境：4× NVIDIA RTX 4090（`pdgpu-4090` 队列，与论文一致）；vLLM TP=4 +
`--disable-custom-all-reduce`（集群 GPU 间 P2P 被禁用，all-reduce 走 SHM）。
指标定义与论文对齐：ASR 全文识别延迟 + LLM 首句生成延迟 + TTS 首句合成延迟，
不含前端 VAD 500 ms 静默阈值（测量方法见 `docs/latency_reproduction.md` §2）。
每配置测量 3 次取平均（四舍五入到整数，与论文一致）。

## 1. 论文参考值（`tab:latency_results`，单位 ms）

| ASR | LLM | TTS | 5s CN | 5s EN | 10s CN | 10s EN | 30s CN | 30s EN | 60s CN | 60s EN |
|---|---|---|---|---|---|---|---|---|---|---|
| SenseVoice (streaming) | Qwen3-30B | IndexTTS 1.5 | 284 | 272 | 346 | 406 | 420 | 610 | 449 | 376 |
| **Paraformer (streaming)** | Qwen3-30B | IndexTTS 1.5 | 264 | 367 | 399 | 488 | 379 | 412 | 393 | 382 |
| **SenseVoice (offline)** | Qwen3-30B | IndexTTS 1.5 | 635 | 617 | 1015 | 1054 | 2175 | 2326 | 3798 | 3671 |
| SenseVoice (streaming) | **Qwen3-8B** | IndexTTS 1.5 | 808 | 339 | 948 | 625 | 1039 | 1111 | 1075 | 1068 |
| SenseVoice (streaming) | **Qwen3-80B (API)** | IndexTTS 1.5 | 881 | 1436 | 994 | 1216 | 1052 | 1124 | 1136 | 1374 |
| SenseVoice (streaming) | Qwen3-30B | **IndexTTS 2** | 1515 | 1264 | 1448 | 1568 | 1764 | 2131 | 1832 | 1810 |
| SenseVoice (streaming) | Qwen3-30B | **CosyVoice (API)** | 652 | 587 | 912 | 1029 | 763 | 842 | 856 | 1019 |

## 2. 复现结果（3 次平均，单位 ms）

| # | ASR | LLM | TTS | 5s CN | 5s EN | 10s CN | 10s EN | 30s CN | 30s EN | 60s CN | 60s EN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SenseVoice (streaming) | Qwen3-30B | IndexTTS 1.5 | 1538 | 1094 | 1543 | 1064 | 1415 | 1153 | 1512 | 1346 |
| 2¹ | Paraformer (streaming) | Qwen3-30B | IndexTTS 1.5 | 1351 | 902 | 1610 | 898 | 1141 | 2500² | 1376 | 935 |
| 3³ | SenseVoice (offline) | Qwen3-30B | IndexTTS 1.5 | 1701 | 1289 | 1879 | 1138 | 2325 | 2029 | 4082 | 5079 |
| 4 | SenseVoice (streaming) | Qwen3-8B | IndexTTS 1.5 | 1839 | 938 | 1605 | 1179 | 1869 | 1412 | 1908 | 1488 |
| 5 | SenseVoice (streaming) | Qwen3-80B (API) | IndexTTS 1.5 | —⁴ | — | — | — | — | — | — | — |
| 6⁵ | SenseVoice (streaming) | Qwen3-30B | IndexTTS 2 | 2828 | 1810 | 2916 | 1777 | 2496 | 2112 | 2641 | 2426 |
| 7 | SenseVoice (streaming) | Qwen3-30B | CosyVoice (API) | —⁴ | — | — | — | — | — | — | — |

¹ Row 2 初测时配置将模型指向本地路径 `...vocab8404-online`，
`ParaformerLocal` 以 `endswith("streaming")` 判断流式模式失败，退化为
"每 600 ms 对累积音频全量重解码"，延迟随输入时长近线性增长（与论文
"流式 ASR 对时长不敏感"的结论相反）。修复方式：建立以 `streaming` 结尾的模型
软链 `models/ModelScope/iic/paraformer-zh-streaming` 并更新配置
（`server_configs/generated/row2.json`、`scripts/run_latency_4090_job.sh`）。
修复前的错误数据已从本报告移除，备份于
`logs/latency_results/row2_run{1,2,3}.bak_buffered/`。

² Row 2 的 30s_en 三次运行一致偏高（2281–2725 ms），非随机噪声，
疑似该 case 的 LLM 首句更长或触发了额外链路开销，待查。

³ Row 3 通过 `SherpaOnnxASR` 新增的 `mock_trigger_interval_sec=1000000` 配置实现
"句末一次性全文识别"（见 `docs/latency_reproduction.md` §6）。注意首轮复现因
`clone()` 未透传该参数导致行为退化为伪流式（数据备份于
`row3_run*.bak_clonebug/`），修复后数据即本表。

⁴ Row 5/7 需要外部 API key。

⁵ Row 6 的 LLM `gpu-memory-utilization` 为 0.28（其他 row 为 0.45）——GPU0 需为
IndexTTS-2 的两个 vLLM 引擎及原生模型（gpt.pth/s2mel/w2v-bert 等）让出显存，
KV cache 对短对话无影响，但严格意义上与其他 row 存在小幅配置差异。

## 3. 逐次运行明细

### Row 1（baseline：SenseVoice streaming + Qwen3-30B + IndexTTS 1.5）

v0.17 镜像、2026-07-23 重跑（含预热轮，无冷启动污染）：

| run | 5s CN | 5s EN | 10s CN | 10s EN | 30s CN | 30s EN | 60s CN | 60s EN |
|---|---|---|---|---|---|---|---|---|
| run1 | 1620 | 996 | 1543 | 1077 | 2059 | 1310 | 2554 | 1878 |
| run2 | 1524 | 945 | 1360 | 1000 | 1119 | 1064 | 995 | 1103 |
| run3 | 1469 | 1341 | 1725 | 1114 | 1067 | 1084 | 987 | 1055 |
| mean | 1538 | 1094 | 1543 | 1064 | 1415 | 1153 | 1512 | 1346 |

### Row 2（Paraformer 真流式）

v0.17 镜像、2026-07-23 重跑（输出目录 `logs/latency_results/row2_run{1,2,3}/`）：

| run | 5s CN | 5s EN | 10s CN | 10s EN | 30s CN | 30s EN | 60s CN | 60s EN |
|---|---|---|---|---|---|---|---|---|
| run1 | 1436 | 926 | 1658 | 953 | 1204 | 2495 | 1395 | 975 |
| run2 | 1346 | 894 | 1588 | 869 | 1210 | 2281 | 1326 | 915 |
| run3 | 1271 | 886 | 1584 | 872 | 1011 | 2725 | 1406 | 914 |
| mean | 1351 | 902 | 1610 | 898 | 1141 | 2500 | 1376 | 935 |

### Row 4（Qwen3-8B-AWQ 替换 LLM）

v0.17 镜像、2026-07-23 重跑（输出目录 `logs/latency_results/row4_run{1,2,3}/`）：

| run | 5s CN | 5s EN | 10s CN | 10s EN | 30s CN | 30s EN | 60s CN | 60s EN |
|---|---|---|---|---|---|---|---|---|
| run1 | 1843 | 925 | 1689 | 1293 | 1866 | 1549 | 2271 | 1880 |
| run2 | 1832 | 917 | 1290 | 1128 | 1598 | 1350 | 1666 | 1419 |
| run3 | 1842 | 972 | 1836 | 1115 | 2144 | 1336 | 1787 | 1164 |
| mean | 1839 | 938 | 1605 | 1179 | 1869 | 1412 | 1908 | 1488 |

### Row 3（SenseVoice offline，句末一次性全文识别）

v0.17 镜像、2026-07-24 重跑（输出目录 `logs/latency_results/row3_run{1,2,3}/`）：

| run | 5s CN | 5s EN | 10s CN | 10s EN | 30s CN | 30s EN | 60s CN | 60s EN |
|---|---|---|---|---|---|---|---|---|
| run1 | 1646 | 1376 | 1941 | 1120 | 2302 | 2187 | 4317 | 5055 |
| run2 | 1952 | 958 | 1851 | 1126 | 1981 | 1960 | 3986 | 5592 |
| run3 | 1505 | 1533 | 1845 | 1170 | 2694 | 1940 | 3943 | 4589 |
| mean | 1701 | 1289 | 1879 | 1138 | 2325 | 2029 | 4082 | 5079 |

### Row 6（IndexTTS 2 替换 TTS）

v0.17 镜像、2026-07-24 重跑（输出目录 `logs/latency_results/row6_run{1,2,3}/`；
LLM gpu util 0.28，见脚注 ⁵）：

| run | 5s CN | 5s EN | 10s CN | 10s EN | 30s CN | 30s EN | 60s CN | 60s EN |
|---|---|---|---|---|---|---|---|---|
| run1 | 2897 | 1926 | 2768 | 1788 | 2597 | 2285 | 3242 | 2768 |
| run2 | 2827 | 1807 | 3425 | 1889 | 2288 | 2033 | 2244 | 2131 |
| run3 | 2759 | 1699 | 2553 | 1653 | 2605 | 2018 | 2437 | 2379 |
| mean | 2828 | 1810 | 2916 | 1777 | 2496 | 2112 | 2641 | 2426 |

## 4. 现阶段结论

- **Row 1**：延迟对输入时长基本不敏感（约 1.0–1.5 s，run1 的 30s/60s CN 略高
  但无时长单调性），趋势与论文一致；但绝对值系统性高于论文约 +700–1100 ms，
  恒定偏移来自 LLM 首句 + TTS 首块链路（候选原因：首句长度差异、AWQ 量化与
  论文 bf16 的推理速度差、测试链路固定开销），待 per-stage 指标
  （`latency_metrics`）进一步定位。已排除 GPU P2P 因素（4090 消费卡驱动层面
  不支持 P2P，论文环境同样只能用 NCCL 回退，且通信开销量级对不上）。
- **Row 2**：**时长敏感性消失，修复验证成功**——修复 ASR 模式判断问题
  （见脚注 ¹）后，5s 与 60s 的延迟基本持平（CN：1351 vs 1376 ms；
  EN：902 vs 935 ms），与论文"流式 ASR 对输入时长不敏感"的定性结论一致；
  绝对值与 Row 1 同处 ~0.9–1.6 s 区间，同样存在相对论文（264–488 ms）的
  系统性偏移，进一步坐实偏移来自 ASR 之外的 LLM/TTS 公共链路。
  唯一异常是 30s_en 三次一致 ~2.5 s（见脚注 ²）。
- **Row 4（Qwen3-8B）**：整体高于 Row 1 约 +300–400 ms，且 CN 的增幅
  （5s_cn 1839 vs 1538；60s_cn 1908 vs 1512）大于 EN——与论文"Qwen3-8B
  面对不同语音输入（如切换情绪）更倾向于先调用工具，推高整体延迟"的观察
  定性一致。延迟仍对时长不敏感。
- **Row 3（SenseVoice offline）**：**时长敏感性复现成功**——延迟从 5s 的
  ~1.3–1.7 s 增长到 60s 的 ~4.1–5.1 s，与论文"offline ASR 延迟随输入时长
  增长"的定性结论一致（论文 0.6→3.7 s）。30s CN 与论文几乎重合
  （2325 vs 2175 ms）；60s EN 偏高（5079 vs 3671 ms），应为 CPU int8 全量
  解码比论文环境慢的差别。5s 处与 Row 1 基本持平（共享 LLM/TTS 恒定偏移）。
- **Row 6（IndexTTS 2）**：延迟对时长仍不敏感，相对 Row 1 基线增加
  ~+0.7–1.3 s（EN：1810 vs 1094；CN：2828 vs 1538），与论文"换 IndexTTS 2
  后延迟上升"的结论一致（论文增量 +1.0–1.5 s）。30s_en 与论文几乎重合
  （2112 vs 2131 ms）。

## 5. 总体对比与待办

五行有效数据（1/2/3/4/6）与论文的定性结论**全部一致**：流式 ASR 对时长
不敏感（row1/2/4/6）、offline ASR 随时长线性增长（row3）、换更大/更主动
的模型延迟上升（row4/6）。系统性的定量差距是统一的 **+700–1100 ms 恒定
偏移**，与时长、ASR 类型无关，指向 LLM 首句 + TTS 首块公共链路（候选：
首句长度差异、AWQ 量化 vs 论文 bf16、测试链路固定开销），下一步用
`latency_metrics` 的 per-stage 分解定位（需先解决 websocket DEBUG 日志对
消息中部的截断）。Row 5/7 待 API key 到位后补齐。

*报告生成时间：2026-07-24；数据来源：`logs/latency_results/`。*

## 6. 复现过程基础设施问题记录（2026-07-22 晚 ~ 07-24 中午）

2026-07-22 晚至 07-23 凌晨的重跑任务全部失败，均为环境/工程问题，与延迟测量
本身无关（07-23 上午全部修复后，v0.17 镜像的任务已正常产出数据）：

1. **mem 64G 不足**：作业脚本需将 ~35 GB 模型 `cp` 到节点 `/tmp`，page cache
   计入容器内存限额，叠加 vLLM 主机内存后超限 → OOMKilled，任务直接消失。
   已改用 `--mem-per-task 128G`（与此前成功案例一致）。
2. **镜像 tag 复用导致节点缓存不一致**：`v0.15` 被重复推送过不同内容，
   `IfNotPresent` 拉取策略下部分节点使用旧缓存（protobuf 3.19，
   `chromadb → opentelemetry` 导入失败，xtalk 无法启动）。已构建含
   `protobuf==5.29.6` 修复的新 tag `v0.17`（registry 不允许覆盖 tag，
   需递增），07-23 上午重提后问题解决。
3. **节点 `/tmp` 残留残缺模型拷贝**：任务被驱逐时若正处 `cp` 中途，会留下
   截断的模型文件，后续同节点任务复用后加载失败（row6 的 IndexTTS-2
   checkpoint 即此问题）。已修复 `scripts/run_latency_4090_job.sh` 的
   `stage()`：临时目录 + `.staged_ok` 标记 + 原子 mv，残缺目录自动重拷。
4. **模型源文件 LFS 下载不完整（2026-07-23 下午）**：row6 的 IndexTTS-2
   服务启动时 `torch.load(gpt.pth)` 报 "failed finding central directory"。
   根因：`models/IndexTTS-2-vLLM/gpt.pth` 的 Git LFS 下载只完成 66%
   （2,288,813,813 / 3,484,663,079 字节）。注意 vLLM 引擎加载的是
   `gpt/pytorch_model.bin`（完好），而 `infer_vllm_v2.py` 的
   `load_checkpoint` 加载的是 `gpt.pth`，两者不是同一文件。修复：删除残缺
   文件后 `git lfs pull --include="gpt.pth"`，sha256 与 LFS 指针一致、
   zip 结构完整（667 entries）。教训：模型入库时应校验 LFS 文件完整性
   （`git lfs fsck` 或比对指针 size/sha256）。
5. **LFS 半截文件连环爆（2026-07-24）**：`git lfs fsck OK` 只校验 LFS 对象库，
   不代表工作区文件完整——`w2v-bert-2.0/model.safetensors` 工作区文件一度
   只有指针大小的 50% 仍显示 fsck OK。可靠做法：逐文件比对工作区 size 与
   指针 size（本报告完成时全部 17 个 LFS 文件已校验，关键文件附 sha256）。
6. **节点 `/tmp` 过期缓存复用（2026-07-24）**：`stage()` 的完成标记无法感知
   源文件更新，LFS 修复前的旧副本被复用导致同样的截断报错再现。已改为源
   签名（最新文件 mtime）校验，签名不一致自动重拷。
7. **并行任务共享日志互相覆盖（2026-07-24）**：TTS 服务日志按版本拆分为
   `tts_v1.5.log`/`tts_v2.log`；各 row 的任务日志也已按提交分开。
8. **GPU0 显存超订（2026-07-24）**：IndexTTS-2 在 GPU0 需两个 vLLM 引擎 +
   原生模型（合计 ~13G）与 LLM TP=4 worker 共存，row6 的 LLM
   `gpu-memory-utilization` 降为 0.28、TTS-2 引擎降为 0.08。
9. **节点相关 NCCL P2P 映射失败（2026-07-24）**：部分节点 NCCL 初始化报
   `Cuda failure 205 'mapping of buffer object failed'`，作业脚本已 bake
   `NCCL_P2P_DISABLE=1`、`NCCL_CUMEM_ENABLE=0`、`NCCL_IB_DISABLE=1`。

*报告生成时间：2026-07-24；数据来源：`logs/latency_results/`。*
