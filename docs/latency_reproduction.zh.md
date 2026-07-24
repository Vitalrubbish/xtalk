# Latency 表格复现指南

本文说明如何用仓库自带的官方设施（`scripts/test.py` + 服务配置）复现论文中的
latency 表格（`arXiv-2512.18706v1/sec/5_latency_of_xtalk.tex`，`tab:latency_results`）。
目标环境为 4× NVIDIA RTX 4090（`pdgpu-4090` 队列，与论文硬件一致）。

## 1. 论文实验设定

论文表格共 7 组配置 × 8 个负载（5s / 10s / 30s / 60s 输入语音 × 中文 / 英文），
数值单位为 ms，每个配置每个负载测 3 次取平均。默认（基线）配置为
**SenseVoice(streaming) + Qwen3-30B + IndexTTS 1.5**，其余每行只替换一个组件：

| # | ASR | LLM | TTS |
|---|-----|-----|-----|
| 1（基线） | SenseVoice (streaming) | Qwen3-30B | IndexTTS 1.5 |
| 2 | Paraformer (streaming) | Qwen3-30B | IndexTTS 1.5 |
| 3 | SenseVoice (offline) | Qwen3-30B | IndexTTS 1.5 |
| 4 | SenseVoice (streaming) | Qwen3-8B | IndexTTS 1.5 |
| 5 | SenseVoice (streaming) | Qwen3-80B (API) | IndexTTS 1.5 |
| 6 | SenseVoice (streaming) | Qwen3-30B | IndexTTS 2 |
| 7 | SenseVoice (streaming) | Qwen3-30B | CosyVoice (API) |

论文原始硬件为 4× RTX 4090。测量口径：端到端延迟 = **ASR 全文识别延迟 +
LLM 首句生成延迟 + TTS 首句合成延迟**；前端 VAD 的 500ms 句末静音门限不计入。
采样参数：主模型 temperature=0.1，Thinker/Rewriter temperature=0.7。

## 2. 延迟口径与官方测量设施的对应关系

官方测试脚本 `scripts/test.py` 的 `--input` 模式会：

1. 在子进程中以内嵌 uvicorn 启动完整 X-Talk 服务（`EmbeddedServer`）；
2. 模拟前端 WebSocket 客户端，按 `timestamp.txt` 调度、以 32ms/帧实时节拍推送
   16kHz PCM 音频，并用 `PlaybackSimulator` 按 48kHz 模拟 TTS 播放；
3. 通过服务端 `RecordingManager` 录制 48kHz 双声道 WAV（左=用户，右=AI 播放时间轴）；
4. 用 `extract_active_segments`（阈值 `max(300, 2%峰值)`、桥接 ≤1s 静音、
   丢弃 <80ms 段）提取两侧活跃语音段，计算

   `latency_ms = AI 首个语音段起点 − 用户语音段终点`

   写入 `<out>/eval.json`。

该口径与论文一致：录音时钟为服务端单调时钟，用户段终点是**声学结束**（不含
VAD 500ms redemption），AI 段起点是**播放时间轴上的起点**，因此测得的正是
「ASR 全文 + LLM 首句 + TTS 首句」链路的总耗时。

若需分解各子项延迟做交叉验证，可使用 `LatencyManager`
（`src/xtalk/serving/modules/latency_manager.py`）经 `latency_metrics` 消息上报的
`asr_latency_ms`（VAD end→ASR final）、`llm_sentence_ms`（ASR final→LLM 首句）、
`tts_first_chunk_ms`（首句→首个 TTS chunk）。

## 3. 环境准备

### 3.1 安装依赖

```bash
pip install -e ".[testing,sherpa-onnx-asr,index-tts,silero-vad]"
# Paraformer 行另需：pip install -e ".[paraformer-local]"
# CosyVoice(API) 行另需：pip install -e ".[ali]"
```

### 3.2 模型清单（本机 `models/` 已具备）

- `models/Qwen3-30B-A3B-AWQ-4Bit/` —— LLM（论文用量化变体，AWQ-4bit）
- `models/Qwen3-Embedding-0.6B/` —— Embedding（检索回调所需）
- `models/IndexTTS-1.5-vLLM/` —— TTS（配置 1–5、7）
- `models/IndexTTS-2-vLLM/` —— TTS（配置 6）
- `models/sherpa-onnx/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17` —— SenseVoice
- `models/sherpa-onnx-server/` —— sherpa-onnx WebSocket server 预编译二进制

尚需获取：

- Qwen3-8B 量化变体（配置 4，需下载，vLLM 部署）
- Qwen3-Next-80B-A3B-Instruct 官方 API key（配置 5）
- CosyVoice-v3-flash DashScope API key（配置 7）
- Paraformer 流式模型（配置 2，FunASR `paraformer-zh-streaming`，首次运行自动下载）
- TTS 参考语音（用于生成测试音频与 TTS 服务，见
  <https://github.com/xcc-zach/xtalk/releases/tag/audio-v0.1>）

## 4. 服务部署（4×4090 GPU 分配）

论文实验中 LLM 以 TP=4 部署（4× RTX 4090），复现环境与其一致。采用相同的
TP=4 布局（AWQ-4bit 权重约 17GB，TP=4 后每卡仅约 4.5GB，TTS/embedding 可与
LLM 共卡）：

| GPU | 服务 | 启动方式 |
|-----|------|----------|
| GPU0–3 | Qwen3-30B-A3B-AWQ-4Bit（vLLM，TP=4） | `vllm serve models/Qwen3-30B-A3B-AWQ-4Bit --port 8000 --tensor-parallel-size 4 --max-model-len 32768 --disable-custom-all-reduce` |
| GPU0（共卡） | IndexTTS 1.5 / 2（index-tts-vllm HTTP 服务） | 参见 <https://github.com/Ksuriuri/index-tts-vllm>，默认端口 11996 |
| GPU1（共卡） | Qwen3-Embedding-0.6B | `vllm serve models/Qwen3-Embedding-0.6B --port 8002` |
| CPU | sherpa-onnx offline WebSocket server（SenseVoice） | `models/sherpa-onnx-server/bin/sherpa-onnx-offline-websocket-server --sense-voice=<模型路径>/model.int8.onnx --tokens=<模型路径>/tokens.txt --port 6006` |

注意事项：

- 模型在网络盘上加载很慢，建议先 `cp -r` 到本地 SSD（如 `/tmp`）再启动 vLLM。
- 配置 2（Paraformer）用 FunASR 本地流式，可放 CPU 或与 LLM 共卡。
- 配置 5、7 走外部 API，对应 GPU 可空出。
- 本地 4×2080 Ti 节点（11GB/卡，sm_75）仅用于调试流程：30B-AWQ（约 17GB
  权重）单卡放不下，且 Turing 架构不支持 vLLM AWQ Marlin 内核（需 sm_80+），
  因此调试期建议用小型非量化模型（如 Qwen3-8B/4B）做 LLM 替身，只验证
  test.py 流程、数据集与录音口径，延迟数字不作数；80B 行走官方 API，不占用
  本地 GPU。正式运行通过 vc-submit 提交到 A10 队列；下述 NCCL 相关环境变量
  应写进提交脚本的作业环境中。

### 4.1 TP=4 NCCL 死锁：根因分析与解决方案

**现象**：在 A10 节点上以 vLLM 0.16.0 启动时，只要 TP>1（TP=2/3/4 均如此），
进程即在 NCCL 初始化 / 首次集合通信阶段挂起（死锁）；只有 TP=1 正常。TP=1
完全不经过 NCCL，说明问题出在多卡集合通信环境本身，而非 TP=4 特有的拓扑或
显存因素。节点驱动为 570.144（最高支持 CUDA 12.8），A10 为 PCIe 卡、无 NVLink。

**已验证的事实**（在 4×2080 Ti 调试节点上，使用与 A10 相同的镜像栈
`pytorch 2.9.1+cu128 / vllm 0.16.0 / CUDA 12.8.1` 实测）：

1. 镜像为 cu128 全栈，与驱动 570.144（CUDA 12.8）匹配——**CUDA 版本错配的
   嫌疑排除**；
2. 裸 NCCL 多卡 all_reduce 正常（torchrun 3 卡实测通过，走 SHM/direct 传输）——
   **NCCL 库本身没有问题**；
3. `torch.cuda.can_device_access_peer` 对任意 GPU 对均返回 **False**——
   **GPU 间 P2P 被完全禁用**（PCIe ACS / IOMMU 阻断）。

**根因结论**：vLLM 的自定义 all-reduce 强依赖 GPU 间 P2P
（`cudaDeviceEnablePeerAccess`），P2P 被禁用时 TP>1 在首次集合通信挂死；
而 NCCL 原生通信会自动退化为 SHM/socket 传输，不受影响。这同时解释了
TP=1 正常（无集合通信）和裸 NCCL 正常（不走 P2P）两个现象。

**解决方案（按优先级）**：

1. **禁用 vLLM 自定义 all-reduce（根治，已实测验证）**：`vllm serve` 加
   `--disable-custom-all-reduce`（已写入上表启动命令），all-reduce 回退到
   NCCL 原生实现（SHM 传输）。注：vLLM 0.16 在检测到 P2P 不可用时会自动禁用
   custom all-reduce，但显式指定该参数可跳过可能挂起的 P2P 自检——2080 Ti
   调试节点实测：TP=2 + 该参数后服务 35s 内正常启动并返回推理结果。
2. **NCCL 环境变量**（通常不需要，NCCL 已自动退化；仅在建连异常时按需使用，
   写进 vc-submit 作业环境）：
   - `NCCL_P2P_DISABLE=1`：显式禁用 P2P；
   - `NCCL_CUMEM_ENABLE=0`：规避 cuMem 分配器在旧驱动上的挂起问题；
   - `NCCL_IB_DISABLE=1`：IB 配置有误时禁用 RDMA 传输。
3. **诊断手段**（死锁复现时定位用）：
   - `NCCL_DEBUG=INFO NCCL_DEBUG_SUBSYS=INIT` 观察初始化卡在哪一步；
   - 用最小 torch 脚本（torchrun 多卡 all_reduce）脱离 vLLM 验证 NCCL 层；
   - 用 `torch.cuda.can_device_access_peer` 检查 P2P 是否可用；
   - vLLM 侧加 `--enforce-eager` 排除 CUDA graph 捕获阶段的挂起。

**兜底方案**：TP=1 布局（LLM 独占 GPU3，TTS/embedding 分占 GPU0/GPU2，
sherpa-onnx 在 CPU）是目前唯一已验证可运行的方案——功能上等价，但 LLM 首句
延迟会高于论文的 TP=4 设定，汇总数据时需在报告中注明。

## 5. 制作测试数据集

模板目录结构（详见 `docs/tutorial/testing.md`）：

```plaintext
logs/test_templates/latency/
├── tts_config.json          # 用于生成音频的 TTS 配置（IndexTTS）
└── <case>/timestamp.txt     # 每 case 一行：0:<输入文本>
```

共 8 个 case：`5s_cn / 5s_en / 10s_cn / 10s_en / 30s_cn / 30s_en / 60s_cn / 60s_en`，
每 case 单轮一句，文本时长与名义时长对应（可用 IndexTTS 合成后按实际音频时长校验）。

生成数据集（需 IndexTTS 服务已在运行）：

```bash
python scripts/test.py --create logs/test_templates/latency --out logs/tests/latency
```

## 6. 各配置的 server config 要点

配置文件结构见 `docs/tutorial/config_the_service.md`，公共部分（LLM/embedding/TTS
基线）可复用 `docs/tutorial/sample_config_for_fully_local_deployment.md` 的写法。
关键映射（以 `src/xtalk/speech/asr/`、`src/xtalk/speech/tts/` 源码为准）：

- **配置 1 / 5 / 6 / 7 的 ASR —— SenseVoice 伪流式**（论文 "streaming" 行）：
  ```json
  "asr": {"type": "SherpaOnnxASR", "params": {"port": 6006, "mode": "offline", "mock_window_size": 5}}
  ```
  SenseVoice 是非流式模型，论文的伪流式即 `MockStreamRecognizer`
  （`src/xtalk/speech/utils.py`）的累积全上下文重推理：每累积 2s 触发一次全量
  重识别，缓存满 `window_size` 后钉死稳定前缀。`SherpaOnnxASR` 的 `mode="offline"`
  正是连接 offline WebSocket server 并用 MockStreamRecognizer 模拟流式
  （`sherpa_onnx_asr.py:94-101`）。

- **配置 2 的 ASR —— Paraformer 流式**：
  ```json
  "asr": {"type": "ParaformerLocal", "params": {"device": "cuda:1"}}
  ```
  FunASR `paraformer-zh-streaming` 真流式（600ms chunk）。

- **配置 3 的 ASR —— SenseVoice 原始非流式**（论文 "offline" 行）：
  ```json
  "asr": {"type": "SherpaOnnxASR", "params": {"port": 6006, "mode": "offline", "mock_window_size": 5, "mock_trigger_interval_sec": 1000000}}
  ```
  `MockStreamRecognizer` 默认每 2s 中途触发重识别（`utils.py:18` 的
  `trigger_interval_sec`），而论文该行的行为是「句末一次性全文识别」（其 60s
  输入约 3.7s 的延迟正是整段一次性识别的耗时）。`SherpaOnnxASR` 已新增
  `mock_trigger_interval_sec` 参数（`sherpa_onnx_asr.py`，透传给
  `MockStreamRecognizer`，默认 2 保持原行为）：设为极大值后非 final 期间不
  触发识别，只在 `is_final` 时对完整音频做一次全量识别，无需再改其他代码。

- **配置 4 的 LLM —— Qwen3-8B**：量化变体 + vLLM，改 `llm_agent` 的
  `base_url`/`model` 指向新服务即可。

- **配置 5 的 LLM —— Qwen3-80B(API)**：`DefaultAgent` 的 `model` 直接填
  OpenAI 兼容的 API 端点（`api_key`/`base_url`/`model`）。

- **配置 6 的 TTS —— IndexTTS 2**：`"tts": {"type": "IndexTTS2", "params": {"port": <port>, "voices": [...]}}`，
  服务同样由 index-tts-vllm 提供（加载 `models/IndexTTS-2-vLLM`）。

- **配置 7 的 TTS —— CosyVoice(API)**：`"tts": {"type": "CosyVoice", "params": {"api_key": ..., "model": "cosyvoice-v3-flash", "voice": "longanyang"}}`。

另外：样例配置不含后端 `vad` 字段，因此运行测试时必须加 `--with-vad`
（客户端 Silero VAD，redemption 默认 500ms，与论文设定一致）。

## 7. 运行与汇总

对每组配置（共 7 组），各跑 3 次：

```bash
python scripts/test.py \
  --config server_configs/<cfg_i>.json \
  --input logs/tests/latency \
  --out logs/latency_results/cfg<i>_run<j> \
  --with-vad
```

从每个 `eval.json` 读取 `latency_ms`，每组配置取 3 次平均，按论文表格格式
（7 行 × 8 列）汇总。注意：

- 每个 case 只放一条输入，使 `eval.json` 的 `latency_ms` 恰好对应该时长档位；
- 每次重跑前删除旧的输出目录，避免误读陈旧结果；
- 首次运行含模型预热，建议先跑一轮 warmup 再正式计时。

## 8. 已知差异与预期差距

- **硬件**：复现环境（4× RTX 4090，`pdgpu-4090` 队列）与论文一致，绝对数值
  可直接对比。唯一差异：集群 GPU 间 P2P 被禁用，vLLM 需加
  `--disable-custom-all-reduce`（all-reduce 走 SHM，性能影响很小）。
  重点验证的趋势：流式 ASR 下延迟不随输入时长显著增长；offline ASR 延迟随
  时长近似线性增长；IndexTTS 2 / 80B / CosyVoice 替换后延迟上升。
- **参考语音**：官方 ReferenceVoice.zip 的 CDN 从集群不可达，改用
  index-tts-vllm 仓库自带的 `examples/voice_03.wav`（latency 测试对参考语音
  不敏感）。
- **外部依赖**：配置 5、7 需要可用的 API key；无 key 时这两行无法复现。
- **配置 3**：`SherpaOnnxASR` 已新增 `mock_trigger_interval_sec` 参数，
  可纯配置复现（见第 6 节）。

## 9. 镜像制作与 vc-submit 提交

vc-submit 需指定 docker 镜像（规范见 `image-use.md`）。仓库根目录的
`Dockerfile` 在已有基础镜像 `sjtu_yukai-xuanzhang-xtalk:v0.13`（CUDA 12.8.1 +
torch 2.9.1 cu128 + vllm 0.16.0 + funasr 等）之上补齐 sudo、xtalk 测试链路
extras，以及 index-tts-vllm 服务端依赖（munch、WeTextProcessing、
descript-audiotools）。

构建与推送（在调试机上执行）：

```bash
docker build -t docker.v2.aispeech.com/sjtu/sjtu_yukai-xuanzhang-xtalk:v0.15 .
docker push docker.v2.aispeech.com/sjtu/sjtu_yukai-xuanzhang-xtalk:v0.15
```

注意事项：

- `.dockerignore` 已排除 `models/`、`.git`、缓存等大目录；镜像内 `/opt/xtalk`
  的代码仅作保底。容器以普通用户运行、无法写镜像内 site-packages，因此作业
  脚本用 `PYTHONPATH=<挂载仓库>/src` 覆盖为共享文件系统上的最新代码。
- 镜像已设 `PYTHONNOUSERSITE=True`，避免 `~/.local` 穿透挂载污染环境
  （`image-use.md` 注意事项）。
- 已知告警：安装 xtalk 会把 langchain-core 降为 0.3.x，与基础镜像里的
  langgraph 1.x 不兼容；xtalk 与 vLLM 均不依赖 langgraph，可忽略。

提交示例（`pdgpu-4090` 队列，4 卡；作业脚本见
`scripts/run_latency_4090_job.sh`，支持 `MODE=dataset` 生成数据集和
`ROW=1|2|3|4|6|all` 跑测试）：

```bash
vc submit --image docker.v2.aispeech.com/sjtu/sjtu_yukai-xuanzhang-xtalk:v0.15 \
  --partition pdgpu-4090 --job xtalk-latency --num-task 1 \
  --cpu-per-task 8 --mem-per-task 64G --gpu-per-task 4 \
  JOB=1:1 /hpc_stor03/sjtu_home/xuan.zhang/xtalk/logs/xtalk_latency.JOB.log \
  --cmd "MODE=dataset bash /hpc_stor03/sjtu_home/xuan.zhang/xtalk/scripts/run_latency_4090_job.sh"
```

- 容器内共享文件系统的挂载路径按 `image-use.md` 示例为
  `/hpc_stor03/sjtu_home/...`，与调试机的 `/mnt/cloudstorfs/...` 不同，
  作业脚本内路径需按容器内实际挂载确认。
- 模型与仓库都走共享文件系统挂载，不进镜像；HF 缓存在作业环境中用
  `HF_HOME=<共享缓存路径>` 指向 `.hf_cache`。
- 作业脚本负责：拷贝模型到本地 SSD → 启动各服务 → 等待就绪 → 跑
  `scripts/test.py` → 汇总 `eval.json`（脚本待编写）。
