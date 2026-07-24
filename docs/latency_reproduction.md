# Latency Table Reproduction Guide

This document explains how to reproduce the paper's latency table
(`arXiv-2512.18706v1/sec/5_latency_of_xtalk.tex`, `tab:latency_results`) using the
repository's official facilities (`scripts/test.py` + service configs). The target
environment is 4× NVIDIA RTX 4090 (`pdgpu-4090` queue, identical to the paper).

## 1. Experiment Setup in the Paper

The table covers 7 configurations × 8 workloads (5s / 10s / 30s / 60s input speech ×
CN / EN), values in ms, each measured 3 times and averaged. The default (baseline)
configuration is **SenseVoice(streaming) + Qwen3-30B + IndexTTS 1.5**; every other row
varies exactly one component:

| # | ASR | LLM | TTS |
|---|-----|-----|-----|
| 1 (baseline) | SenseVoice (streaming) | Qwen3-30B | IndexTTS 1.5 |
| 2 | Paraformer (streaming) | Qwen3-30B | IndexTTS 1.5 |
| 3 | SenseVoice (offline) | Qwen3-30B | IndexTTS 1.5 |
| 4 | SenseVoice (streaming) | Qwen3-8B | IndexTTS 1.5 |
| 5 | SenseVoice (streaming) | Qwen3-80B (API) | IndexTTS 1.5 |
| 6 | SenseVoice (streaming) | Qwen3-30B | IndexTTS 2 |
| 7 | SenseVoice (streaming) | Qwen3-30B | CosyVoice (API) |

The paper used 4× RTX 4090. Latency is defined as **ASR full-text recognition latency
+ LLM first-sentence generation latency + TTS first-sentence synthesis latency**; the
frontend VAD's fixed 500 ms end-of-utterance silence threshold is excluded. Sampling:
main model temperature=0.1, Thinker/Rewriter temperature=0.7.

## 2. Metric Alignment with the Official Test Harness

In `--input` mode, `scripts/test.py`:

1. Starts a full embedded X-Talk service in a subprocess (`EmbeddedServer`, uvicorn);
2. Drives a simulated frontend WebSocket client that pushes 16 kHz PCM audio in real
   time (32 ms per frame) per the `timestamp.txt` schedule, and simulates TTS playback
   at 48 kHz (`PlaybackSimulator`);
3. Records a 48 kHz stereo WAV via the server-side `RecordingManager`
   (left = user, right = AI playback timeline);
4. Extracts active speech segments with `extract_active_segments`
   (threshold `max(300, 2% of peak)`, bridge gaps ≤ 1 s, drop segments < 80 ms) and
   computes

   `latency_ms = start of first AI segment − end of user segment`

   into `<out>/eval.json`.

This matches the paper's metric: the recording clock is the server's monotonic clock,
the user segment ends at the **acoustic endpoint** (excluding the VAD 500 ms
redemption), and the AI segment starts on the **playback timeline**, so the measured
value is exactly the "ASR full-text + LLM first sentence + TTS first sentence" chain.

For a per-stage breakdown, use the `latency_metrics` messages reported by
`LatencyManager` (`src/xtalk/serving/modules/latency_manager.py`):
`asr_latency_ms` (VAD end → ASR final), `llm_sentence_ms` (ASR final → LLM first
sentence), `tts_first_chunk_ms` (first sentence → first TTS chunk).

## 3. Prerequisites

### 3.1 Dependencies

```bash
pip install -e ".[testing,sherpa-onnx-asr,index-tts,silero-vad]"
# Row 2 (Paraformer) also needs: pip install -e ".[paraformer-local]"
# Row 7 (CosyVoice API) also needs: pip install -e ".[ali]"
```

### 3.2 Models (already present under `models/`)

- `models/Qwen3-30B-A3B-AWQ-4Bit/` — LLM (quantized variant, AWQ-4bit)
- `models/Qwen3-Embedding-0.6B/` — embeddings (for retrieval callbacks)
- `models/IndexTTS-1.5-vLLM/` — TTS (rows 1–5, 7)
- `models/IndexTTS-2-vLLM/` — TTS (row 6)
- `models/sherpa-onnx/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17` — SenseVoice
- `models/sherpa-onnx-server/` — prebuilt sherpa-onnx WebSocket server binaries

Still needed:

- Qwen3-8B quantized variant (row 4; download and serve with vLLM)
- Official API key for Qwen3-Next-80B-A3B-Instruct (row 5)
- DashScope API key for CosyVoice-v3-flash (row 7)
- Paraformer streaming model (row 2; FunASR `paraformer-zh-streaming`, auto-downloaded)
- TTS reference voices (for dataset generation and the TTS service, see
  <https://github.com/xcc-zach/xtalk/releases/tag/audio-v0.1>)

## 4. Service Deployment (4×4090 layout)

The paper deployed the LLM with TP=4 on 4× RTX 4090, and our reproduction
environment is identical. The same TP=4 layout is used (AWQ-4bit weights ≈ 17 GB,
so only ~4.5 GB per GPU under TP=4; TTS/embedding can share GPUs with the LLM):

| GPU | Service | How to start |
|-----|---------|--------------|
| GPU0–3 | Qwen3-30B-A3B-AWQ-4Bit (vLLM, TP=4) | `vllm serve models/Qwen3-30B-A3B-AWQ-4Bit --port 8000 --tensor-parallel-size 4 --max-model-len 32768 --disable-custom-all-reduce` |
| GPU0 (shared) | IndexTTS 1.5 / 2 (index-tts-vllm HTTP server) | see <https://github.com/Ksuriuri/index-tts-vllm>, default port 11996 |
| GPU1 (shared) | Qwen3-Embedding-0.6B | `vllm serve models/Qwen3-Embedding-0.6B --port 8002` |
| CPU | sherpa-onnx offline WebSocket server (SenseVoice) | `models/sherpa-onnx-server/bin/sherpa-onnx-offline-websocket-server --sense-voice=<model>/model.int8.onnx --tokens=<model>/tokens.txt --port 6006` |

Notes:

- Loading models from a network filesystem is slow; `cp -r` to local SSD (e.g. `/tmp`)
  before starting vLLM.
- Row 2 (Paraformer) runs locally via FunASR; CPU or sharing an LLM GPU works.
- Rows 5 and 7 use external APIs; the corresponding GPUs stay free.
- The local 4×2080 Ti node (11 GB per GPU, sm_75) is for debugging the pipeline
  only: the 30B-AWQ (~17 GB weights) does not fit on a single card, and Turing does
  not support vLLM's AWQ Marlin kernels (needs sm_80+). Use a small non-quantized
  stand-in LLM (e.g. Qwen3-8B/4B) during debugging to validate the test.py flow,
  dataset, and recording metric only — latency numbers there are meaningless; the
  80B row uses the official API and needs no local GPU. Production runs are
  submitted to the A10 queue via vc-submit — bake the NCCL environment variables
  below into the job environment.

### 4.1 TP=4 NCCL Deadlock: Root-Cause Analysis and Fixes

**Symptom**: on the A10 nodes with vLLM 0.16.0, any TP>1 (TP=2/3/4 alike) hangs
during NCCL init / the first collective (deadlock); only TP=1 works. TP=1 never
touches NCCL, so the problem is the multi-GPU collective-communication environment
itself, not anything TP=4-specific (topology or memory). The node driver is 570.144
(max CUDA 12.8), and A10 is a PCIe card without NVLink.

**Verified facts** (measured on the 4×2080 Ti debug node with the same image stack
as A10: `pytorch 2.9.1+cu128 / vllm 0.16.0 / CUDA 12.8.1`):

1. The image is cu128 throughout, matching driver 570.144 (CUDA 12.8) — the CUDA
   version-mismatch hypothesis is **ruled out**;
2. Bare NCCL multi-GPU all_reduce works (verified with torchrun on 3 GPUs, using
   SHM/direct transports) — **the NCCL library itself is fine**;
3. `torch.cuda.can_device_access_peer` returns **False for every GPU pair** —
   **GPU-to-GPU P2P is completely disabled** (PCIe ACS / IOMMU blocking).

**Root cause**: vLLM's custom all-reduce strictly requires GPU-to-GPU P2P
(`cudaDeviceEnablePeerAccess`); with P2P disabled, any TP>1 deadlocks at the first
collective. Native NCCL collectives automatically fall back to SHM/socket
transports and are unaffected — which explains both why TP=1 works (no collectives)
and why bare NCCL works (no P2P needed).

**Fixes (in priority order)**:

1. **Disable vLLM's custom all-reduce (the root fix, verified)**: add
   `--disable-custom-all-reduce` to `vllm serve` (already in the launch command
   above); all-reduce falls back to native NCCL (SHM transport). Note: vLLM 0.16
   auto-disables custom all-reduce when P2P is unavailable, but setting the flag
   explicitly skips the potentially-hanging P2P self-test — verified on the 2080 Ti
   debug node: with TP=2 + this flag the server came up in 35 s and served
   completions.
2. **NCCL environment variables** (usually unnecessary since NCCL already falls
   back; use only if connection setup misbehaves, set in the vc-submit job env):
   - `NCCL_P2P_DISABLE=1`: explicitly disable P2P;
   - `NCCL_CUMEM_ENABLE=0`: work around cuMem allocator hangs on older drivers;
   - `NCCL_IB_DISABLE=1`: disable RDMA transport if IB is misconfigured.
3. **Diagnostics** (to localize the hang if it reappears):
   - `NCCL_DEBUG=INFO NCCL_DEBUG_SUBSYS=INIT` to see which init step stalls;
   - a minimal torch script (torchrun multi-GPU all_reduce) to test NCCL without
     vLLM;
   - `torch.cuda.can_device_access_peer` to check P2P availability;
   - `--enforce-eager` on the vLLM side to rule out CUDA-graph capture hangs.

**Fallback**: the TP=1 layout (LLM alone on GPU3, TTS/embedding on GPU0/GPU2,
sherpa-onnx on CPU) is currently the only verified-working setup — functionally
equivalent, but LLM first-sentence latency will be higher than the paper's TP=4
setup, which must be noted when reporting results.

## 5. Building the Test Dataset

Template layout (see `docs/tutorial/testing.md`):

```plaintext
logs/test_templates/latency/
├── tts_config.json          # TTS config used for audio generation (IndexTTS)
└── <case>/timestamp.txt     # one line per case: 0:<input text>
```

8 cases total: `5s_cn / 5s_en / 10s_cn / 10s_en / 30s_cn / 30s_en / 60s_cn / 60s_en`,
each a single-turn single utterance whose audio length matches its nominal duration
(synthesize with IndexTTS, then verify actual durations).

Generate the dataset (requires the IndexTTS service to be running):

```bash
python scripts/test.py --create logs/test_templates/latency --out logs/tests/latency
```

## 6. Server Config Key Points per Row

Config file structure: `docs/tutorial/config_the_service.md`; the shared parts
(LLM/embedding/baseline TTS) can follow
`docs/tutorial/sample_config_for_fully_local_deployment.md`. Key mappings (grounded in
`src/xtalk/speech/asr/` and `src/xtalk/speech/tts/`):

- **Rows 1 / 5 / 6 / 7 ASR — SenseVoice pseudo-streaming** (the paper's "streaming"
  row):
  ```json
  "asr": {"type": "SherpaOnnxASR", "params": {"port": 6006, "mode": "offline", "mock_window_size": 5}}
  ```
  SenseVoice is a non-streaming model; the paper's pseudo-streaming is the
  `MockStreamRecognizer` (`src/xtalk/speech/utils.py`) cumulative full-context
  re-inference: re-recognize the full buffer every 2 s, pin the stable prefix once the
  cache reaches `window_size`. `SherpaOnnxASR` with `mode="offline"` connects to the
  offline WebSocket server and simulates streaming via MockStreamRecognizer
  (`sherpa_onnx_asr.py:94-101`).

- **Row 2 ASR — Paraformer streaming**:
  ```json
  "asr": {"type": "ParaformerLocal", "params": {"device": "cuda:1"}}
  ```
  FunASR `paraformer-zh-streaming`, true streaming (600 ms chunks).

- **Row 3 ASR — SenseVoice original non-streaming** (the paper's "offline" row):
  ```json
  "asr": {"type": "SherpaOnnxASR", "params": {"port": 6006, "mode": "offline", "mock_window_size": 5, "mock_trigger_interval_sec": 1000000}}
  ```
  `MockStreamRecognizer` re-triggers recognition every 2 s mid-utterance by default
  (`trigger_interval_sec`, `utils.py:18`), but the paper's offline behavior is
  "one-shot recognition at sentence end" (this row's ~3.7 s latency at 60 s input is
  exactly that full-buffer decode). `SherpaOnnxASR` now exposes
  `mock_trigger_interval_sec` (`sherpa_onnx_asr.py`, forwarded to
  `MockStreamRecognizer`; default 2 keeps the original behavior): set it very large
  so nothing triggers before `is_final`, and a single full-buffer recognition runs at
  utterance end. No other source change is needed.

- **Row 4 LLM — Qwen3-8B**: quantized variant + vLLM; just point `llm_agent`'s
  `base_url`/`model` at the new service.

- **Row 5 LLM — Qwen3-80B(API)**: fill `DefaultAgent`'s `model` dict with the
  OpenAI-compatible API endpoint (`api_key`/`base_url`/`model`).

- **Row 6 TTS — IndexTTS 2**: `"tts": {"type": "IndexTTS2", "params": {"port": <port>, "voices": [...]}}`,
  served by index-tts-vllm loading `models/IndexTTS-2-vLLM`.

- **Row 7 TTS — CosyVoice(API)**: `"tts": {"type": "CosyVoice", "params": {"api_key": ..., "model": "cosyvoice-v3-flash", "voice": "longanyang"}}`.

Also: the sample configs contain no backend `vad` field, so tests must run with
`--with-vad` (client-side Silero VAD, default 500 ms redemption, matching the paper).

## 7. Running and Aggregating

For each of the 7 configurations, run 3 times:

```bash
python scripts/test.py \
  --config server_configs/<cfg_i>.json \
  --input logs/tests/latency \
  --out logs/latency_results/cfg<i>_run<j> \
  --with-vad
```

Read `latency_ms` from each `eval.json`, average the 3 runs per configuration, and
arrange into the paper's 7 × 8 table. Notes:

- Keep exactly one input per case so `latency_ms` maps to one duration tier;
- Delete stale output directories before rerunning to avoid reading old results;
- The first run includes model warm-up — do a warm-up pass before timing officially.

## 8. Known Differences and Expected Gaps

- **Hardware**: the reproduction environment (4× RTX 4090, `pdgpu-4090` queue) is
  identical to the paper, so absolute values are directly comparable. The only
  difference: GPU-to-GPU P2P is disabled on the cluster, so vLLM needs
  `--disable-custom-all-reduce` (all-reduce over SHM, negligible performance
  impact). Key trends to validate: latency is insensitive to input duration under
  streaming ASR, grows nearly linearly under offline ASR, and increases with
  IndexTTS 2 / 80B / CosyVoice swaps.
- **Reference voices**: the official ReferenceVoice.zip CDN is unreachable from
  the cluster; use `examples/voice_03.wav` bundled with index-tts-vllm instead
  (latency testing is insensitive to the reference voice).
- **External dependencies**: rows 5 and 7 need working API keys; without them those
  rows cannot be reproduced.
- **Row 3**: previously needed a source tweak; `SherpaOnnxASR` now exposes
  `mock_trigger_interval_sec`, so it is reproducible by configuration alone
  (see §6).

## 9. Building the Image and Submitting via vc-submit

vc-submit requires a docker image (conventions in `image-use.md`). The `Dockerfile`
at the repo root builds on the existing base image
`sjtu_yukai-xuanzhang-xtalk:v0.13` (CUDA 12.8.1 + torch 2.9.1 cu128 + vllm 0.16.0 +
funasr etc.), adding sudo, the xtalk test-chain extras, and the index-tts-vllm
server dependencies (munch, WeTextProcessing, descript-audiotools).

Build and push (on the debug machine):

```bash
docker build -t docker.v2.aispeech.com/sjtu/sjtu_yukai-xuanzhang-xtalk:v0.15 .
docker push docker.v2.aispeech.com/sjtu/sjtu_yukai-xuanzhang-xtalk:v0.15
```

Notes:

- `.dockerignore` excludes `models/`, `.git`, caches and other large directories;
  the baked `/opt/xtalk` code is only a fallback. Containers run as a non-root user
  and cannot write the image's site-packages, so the job script overrides the code
  with `PYTHONPATH=<mounted repo>/src` pointing at the shared-filesystem checkout.
- The image sets `PYTHONNOUSERSITE=True` so `~/.local` on the mounted filesystem
  cannot pollute the environment (see `image-use.md`).
- Known warning: installing xtalk downgrades langchain-core to 0.3.x, which
  conflicts with langgraph 1.x in the base image; neither xtalk nor vLLM depends on
  langgraph, so it is safe to ignore.

Submission example (`pdgpu-4090` queue, 4 GPUs; the job script is
`scripts/run_latency_4090_job.sh`, supporting `MODE=dataset` for dataset
generation and `ROW=1|2|3|4|6|all` for test runs):

```bash
vc submit --image docker.v2.aispeech.com/sjtu/sjtu_yukai-xuanzhang-xtalk:v0.15 \
  --partition pdgpu-4090 --job xtalk-latency --num-task 1 \
  --cpu-per-task 8 --mem-per-task 64G --gpu-per-task 4 \
  JOB=1:1 /hpc_stor03/sjtu_home/xuan.zhang/xtalk/logs/xtalk_latency.JOB.log \
  --cmd "MODE=dataset bash /hpc_stor03/sjtu_home/xuan.zhang/xtalk/scripts/run_latency_4090_job.sh"
```

- The shared filesystem mounts inside containers as `/hpc_stor03/sjtu_home/...`
  (per `image-use.md` examples), unlike the debug machine's `/mnt/cloudstorfs/...`;
  paths in the job script must match the actual container mount.
- Models and the repo stay on the shared filesystem, not in the image; point
  `HF_HOME=<shared cache path>` at `.hf_cache` in the job environment.
- The job script is responsible for: copying models to local SSD → starting the
  services → waiting for readiness → running `scripts/test.py` → aggregating
  `eval.json` (script to be written).
