#!/usr/bin/env bash
# X-Talk 论文 latency 表格复现：4090 队列作业脚本（在 vc-submit 容器内运行）
#
# 用法（在容器内）：
#   MODE=dataset bash scripts/run_latency_4090_job.sh          # 生成测试数据集（只需一次）
#   ROW=1 bash scripts/run_latency_4090_job.sh                 # 跑配置 1（3 次）
#   ROW=all bash scripts/run_latency_4090_job.sh               # 依次跑配置 1/2/3/4/6
#
# 可用环境变量：
#   XTALK_ROOT  仓库根目录（默认 /hpc_stor03/sjtu_home/xuan.zhang/xtalk）
#   ROW         1|2|3|4|6|all（默认 1）；配置 5/7 需要 API key，不在本脚本范围内
#   RUNS        每组配置重复次数（默认 3，与论文一致）
#   MODE        test（默认）| dataset
#
# GPU 布局（4×4090 24GB）：
#   GPU0-3  LLM vLLM TP=4（--disable-custom-all-reduce，集群 P2P 被禁用）
#   GPU0    IndexTTS 1.5/2（与 LLM 共卡）
#   GPU1    Qwen3-Embedding-0.6B（与 LLM 共卡）
#   CPU     sherpa-onnx offline WebSocket server（SenseVoice）
set -euo pipefail

XTALK_ROOT="${XTALK_ROOT:-/hpc_stor03/sjtu_home/xuan.zhang/xtalk}"
ROW="${ROW:-1}"
RUNS="${RUNS:-3}"
MODE="${MODE:-test}"

MODELS="$XTALK_ROOT/models"
ITTS_REPO="$XTALK_ROOT/index-tts-vllm"
SENSEVOICE="$MODELS/sherpa-onnx/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
SHERPA_BIN="$MODELS/sherpa-onnx-server/sherpa-onnx-offline-websocket-server"
VOICE="$ITTS_REPO/examples/voice_03.wav"
DATASET="$XTALK_ROOT/logs/tests/latency"
TEMPLATE="$XTALK_ROOT/logs/test_templates/latency"
OUT_ROOT="$XTALK_ROOT/logs/latency_results"
CFG_DIR="$XTALK_ROOT/server_configs/generated"
WORK=/tmp/latency_job
LOGD="$XTALK_ROOT/logs/job_logs"

PIDS=()
cleanup() {
  echo "[job] cleaning up background services..."
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT

log() { echo "[job $(date +%H:%M:%S)] $*"; }

wait_http() { # url name timeout_s
  local url=$1 name=$2 timeout=${3:-900} i
  for ((i=0; i<timeout; i+=5)); do
    if curl -sf "$url" > /dev/null 2>&1; then log "$name ready"; return 0; fi
    sleep 5
  done
  echo "[job] ERROR: $name not ready after ${timeout}s" >&2; return 1
}

wait_tcp() { # port name timeout_s
  local port=$1 name=$2 timeout=${3:-300} i
  for ((i=0; i<timeout; i+=3)); do
    if (echo > "/dev/tcp/127.0.0.1/$port") 2>/dev/null; then log "$name ready"; return 0; fi
    sleep 3
  done
  echo "[job] ERROR: $name not ready after ${timeout}s" >&2; return 1
}

stage() { # src dst — 拷贝模型到本地 SSD（原子操作 + 源签名校验；若上次任务在
  # 拷贝中途被驱逐留下残缺目录、或源文件在拷贝后发生过更新（如 LFS 重新下载），
  # 签名不一致会触发重新拷贝。排除 .git 以节省 /tmp 空间——IndexTTS-2 的 .git
  # 含 ~7G LFS 对象，会加剧容器内存压力）
  local src=$1 dst=$2 sig
  sig=$(find "$src" -type f -printf '%T@\n' 2>/dev/null | sort -n | tail -1)
  if [ ! -e "$dst/.staged_ok" ] || [ "$(cat "$dst/.staged_ok" 2>/dev/null)" != "$sig" ]; then
    log "staging $src -> $dst"
    rm -rf "$dst" "$dst.tmp"
    mkdir -p "$dst.tmp"
    tar -C "$src" --exclude='./.git' -cf - . | tar -C "$dst.tmp" -xf - \
      && echo "$sig" > "$dst.tmp/.staged_ok" && mv "$dst.tmp" "$dst"
    log "staged $dst ($(du -sh "$dst" 2>/dev/null | cut -f1)), /tmp free: $(df -h /tmp | awk 'NR==2{print $4}')"
  fi
}

start_sherpa() {
  log "starting sherpa-onnx offline server (CPU, port 6006)"
  "$SHERPA_BIN" \
    --sense-voice-model="$SENSEVOICE/model.int8.onnx" \
    --tokens="$SENSEVOICE/tokens.txt" \
    --sense-voice-use-itn=true \
    --num-threads=8 --port=6006 \
    --log-file="$LOGD/sherpa.log" &
  PIDS+=($!)
  wait_tcp 6006 sherpa 300
}

start_llm() { # model_dir served_name [gpu_util]
  local model_dir=$1 name=$2 util=${3:-0.45}
  log "starting vLLM LLM ($name, TP=4, port 8000, gpu_util=$util)"
  CUDA_VISIBLE_DEVICES=0,1,2,3 vllm serve "$model_dir" \
    --served-model-name "$name" \
    --port 8000 --tensor-parallel-size 4 \
    --disable-custom-all-reduce \
    --enable-auto-tool-choice --tool-call-parser hermes \
    --default-chat-template-kwargs '{"enable_thinking": false}' \
    --override-generation-config '{"max_new_tokens": 256}' \
    --max-model-len 32768 --gpu-memory-utilization "$util" \
    > "$LOGD/llm.log" 2>&1 &
  PIDS+=($!)
  wait_http http://127.0.0.1:8000/v1/models "LLM($name)" 1800
}

start_embedding() {
  log "starting vLLM embedding (GPU1, port 8002)"
  CUDA_VISIBLE_DEVICES=1 vllm serve "$WORK/models/emb" \
    --served-model-name qwen3-emb \
    --port 8002 --gpu-memory-utilization 0.1 \
    --max-model-len 8192 \
    > "$LOGD/emb.log" 2>&1 &
  PIDS+=($!)
  wait_http http://127.0.0.1:8002/v1/models embedding 900
}

start_tts() { # 1.5|2
  local ver=$1
  # 按版本分日志文件：并行任务（如 row3 用 1.5、row6 用 2）曾互相覆盖
  # 共享的 tts.log，导致排障时看不到另一方的启动进度
  if [ "$ver" = "2" ]; then
    log "starting IndexTTS-2 server (GPU0, port 11997, gpu_util=0.08)"
    stage "$MODELS/IndexTTS-2-vLLM" "$WORK/models/itts2"
    (cd "$ITTS_REPO" && CUDA_VISIBLE_DEVICES=0 python "$XTALK_ROOT/scripts/itts_serve.py" api_server_v2.py \
      --model_dir "$WORK/models/itts2" --host 127.0.0.1 --port 11997 \
      --gpu_memory_utilization 0.08 > "$LOGD/tts_v2.log" 2>&1) &
  else
    log "starting IndexTTS-1.5 server (GPU0, port 11996)"
    stage "$MODELS/IndexTTS-1.5-vLLM" "$WORK/models/itts"
    (cd "$ITTS_REPO" && CUDA_VISIBLE_DEVICES=0 python "$XTALK_ROOT/scripts/itts_serve.py" api_server.py \
      --model_dir "$WORK/models/itts" --host 127.0.0.1 --port 11996 \
      --gpu_memory_utilization 0.12 > "$LOGD/tts_v1.5.log" 2>&1) &
  fi
  PIDS+=($!)
  sleep 15
  log "tts_v${ver}.log head:"; head -20 "$LOGD/tts_v${ver}.log" 2>/dev/null || true
  if [ "$ver" = "2" ]; then wait_http http://127.0.0.1:11997/health "IndexTTS-2" 1800
  else wait_http http://127.0.0.1:11996/health "IndexTTS-1.5" 900; fi
}

gen_config() { # row — 生成 server config JSON 到 $CFG_DIR/row<N>.json
  local row=$1 asr tts llm_model="qwen3-30b"
  case "$row" in
    1|6) asr='"asr": {"type": "SherpaOnnxASR", "params": {"port": 6006, "mode": "offline", "mock_window_size": 5}}' ;;
    2)   asr='"asr": {"type": "ParaformerLocal", "params": {"device": "cuda:2", "model": "'"$MODELS/ModelScope/iic/paraformer-zh-streaming"'", "vad_model": null, "punc_model": null}}' ;;
    3)   asr='"asr": {"type": "SherpaOnnxASR", "params": {"port": 6006, "mode": "offline", "mock_window_size": 5, "mock_trigger_interval_sec": 1000000}}' ;;
    4)   asr='"asr": {"type": "SherpaOnnxASR", "params": {"port": 6006, "mode": "offline", "mock_window_size": 5}}'; llm_model="qwen3-8b" ;;
    *)   echo "unsupported row: $row" >&2; return 1 ;;
  esac
  case "$row" in
    6) tts='"tts": {"type": "IndexTTS2", "params": {"port": 11997, "voices": [{"name": "voice_03", "path": "'"$VOICE"'"}]}}' ;;
    *) tts='"tts": {"type": "IndexTTS", "params": {"port": 11996, "voices": [{"name": "voice_03", "path": "'"$VOICE"'"}]}}' ;;
  esac
  mkdir -p "$CFG_DIR"
  cat > "$CFG_DIR/row${row}.json" <<EOF
{
  $asr,
  "llm_agent": {
    "type": "DefaultAgent",
    "params": {
      "model": {"api_key": "none", "base_url": "http://127.0.0.1:8000/v1", "model": "$llm_model"},
      "voice_names": ["voice_03"],
      "emotions": ["happy", "angry", "sad", "fear", "disgust", "depressed", "surprised", "calm", "normal"]
    }
  },
  "embeddings": {
    "type": "OpenAIEmbeddings",
    "params": {"api_key": "none", "base_url": "http://127.0.0.1:8002/v1", "model": "qwen3-emb"}
  },
  $tts
}
EOF
  log "config written: $CFG_DIR/row${row}.json"
}

setup_env() {
  cd "$XTALK_ROOT"
  export HF_HOME="$XTALK_ROOT/.hf_cache"
  export PYTHONNOUSERSITE=True
  # 容器以普通用户运行，无法写镜像内 site-packages；用 PYTHONPATH 直接指向
  # 挂载仓库的 src（src-layout），覆盖镜像内 baked 的 xtalk 安装
  export PYTHONPATH="$XTALK_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
  # NCCL 加固（docs/latency_reproduction.md §4.1）：集群 GPU 间 P2P 被禁，
  # 部分节点上 NCCL 仍尝试 P2P/cuMem 传输并在初始化时报
  # "Cuda failure 205 'mapping of buffer object failed'"（节点相关，
  # 曾导致 TP=4 LLM 启动失败）；以下变量对正常节点无副作用
  export NCCL_P2P_DISABLE=1
  export NCCL_CUMEM_ENABLE=0
  export NCCL_IB_DISABLE=1
  mkdir -p "$WORK/models" "$LOGD"
  stage "$MODELS/Qwen3-Embedding-0.6B" "$WORK/models/emb"
}

run_row() { # row
  local row=$1 llm_dir llm_name tts_ver="1.5" llm_util="0.45"
  case "$row" in
    4) llm_dir="$WORK/models/llm8b"; llm_name="qwen3-8b"
       stage "$MODELS/HuggingFace/Qwen3-8B-AWQ" "$llm_dir" ;;
    *) llm_dir="$WORK/models/llm30b"; llm_name="qwen3-30b"
       stage "$MODELS/Qwen3-30B-A3B-AWQ-4Bit" "$llm_dir" ;;
  esac
  # row6 的 IndexTTS-2 在 GPU0 上还需 ~13G（两个 vLLM 引擎 + gpt.pth/s2mel/
  # w2v-bert 等原生模型），LLM 显存配额降到 0.28 给 TTS 让位（KV cache 对短
  # 对话仍绰绰有余；注意与其他 row 的 0.45 存在小幅配置差异，报告需注明）
  [ "$row" = "6" ] && { tts_ver="2"; llm_util="0.28"; }

  start_sherpa
  start_llm "$llm_dir" "$llm_name" "$llm_util"
  start_embedding
  start_tts "$tts_ver"
  gen_config "$row"

  # warmup：引擎（vLLM/IndexTTS）首个真实请求有冷启动开销（NCCL SHM 通道
  # 建立、CUDA graph 首次回放、内核调优），会污染正式计时第一个 case 的
  # 数据（实测首轮 10s_cn 高达 11.2s）。先用单个 5s case 完整跑一遍预热，
  # 结果丢弃；引擎常驻，之后 3 轮正式测试不受影响。
  log "warmup run (results discarded)"
  local wds="$WORK/warmup_dataset"
  rm -rf "$wds" "$WORK/warmup_out"
  mkdir -p "$wds"
  cp -r "$DATASET/5s_en" "$wds/"
  python scripts/test.py --config "$CFG_DIR/row${row}.json" \
    --input "$wds" --out "$WORK/warmup_out" --with-vad \
    > "$LOGD/warmup_row${row}.log" 2>&1 || log "warmup failed (ignored)"

  for ((i=1; i<=RUNS; i++)); do
    local out="$OUT_ROOT/row${row}_run${i}"
    log "row $row run $i/$RUNS -> $out"
    rm -rf "$out"
    python scripts/test.py --config "$CFG_DIR/row${row}.json" \
      --input "$DATASET" --out "$out" --with-vad \
      > "$LOGD/test_row${row}_run${i}.log" 2>&1 || { echo "[job] ERROR: test failed, see $LOGD/test_row${row}_run${i}.log"; return 1; }
    python - "$out/eval.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
print(f"[job] latency_ms = {d.get('latency_ms')}, cases = {d.get('cases')}")
EOF
  done
}

# ---------------- main ----------------
log "XTALK_ROOT=$XTALK_ROOT ROW=$ROW RUNS=$RUNS MODE=$MODE"
setup_env

if [ "$MODE" = "dataset" ]; then
  start_tts 1.5
  mkdir -p "$TEMPLATE"
  cat > "$TEMPLATE/tts_config.json" <<EOF
{"type": "IndexTTS", "params": {"port": 11996, "voices": [{"name": "voice_03", "path": "$VOICE"}]}}
EOF
  rm -rf "$DATASET"
  python scripts/test.py --create "$TEMPLATE" --out "$DATASET"
  log "dataset generated at $DATASET, durations:"
  python - "$DATASET" <<'EOF'
import sys, glob, soundfile as sf
for wav in sorted(glob.glob(sys.argv[1] + '/*/audio_000.wav')):
    info = sf.info(wav)
    print(f"  {wav}: {info.duration:.1f}s")
EOF
  exit 0
fi

if [ "$ROW" = "all" ]; then
  for r in 1 2 3 4 6; do
    run_row "$r"
    cleanup; PIDS=()
    sleep 10
  done
else
  run_row "$ROW"
fi
log "done"
