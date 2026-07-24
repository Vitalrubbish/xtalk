# xtalk latency 复现环境（vc-submit 用）
#
# 基础镜像已包含：CUDA 12.8.1 + Python 3.11 + torch 2.9.1(cu128) + vllm 0.16.0
# + funasr/modelscope/onnxruntime 等。本 Dockerfile 在其上补齐：
#   1. sudo（超算容器以普通用户启动，便于容器内补装工具，见 image-use.md）
#   2. xtalk 源码及测试链路所需 extras
#
# 构建与推送（命名规范见 image-use.md；registry 不允许覆盖已有 tag，需递增）：
#   docker build -t docker.v2.aispeech.com/sjtu/sjtu_yukai-xuanzhang-xtalk:v0.17 .
#   docker push docker.v2.aispeech.com/sjtu/sjtu_yukai-xuanzhang-xtalk:v0.17
FROM docker.v2.aispeech.com/sjtu/sjtu_yukai-xuanzhang-xtalk:v0.13

RUN apt-get update && apt-get install -y --no-install-recommends \
        sudo \
        espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# 将 xtalk 源码装入镜像（保底环境）。正式任务优先使用共享文件系统上挂载的
# 仓库目录，在作业脚本中执行 pip install -e <挂载路径> --no-deps 覆盖此处版本。
WORKDIR /opt/xtalk
COPY . /opt/xtalk
RUN SETUPTOOLS_SCM_PRETEND_VERSION=0.1.0 \
        pip install --no-cache-dir -e \
        ".[testing,sherpa-onnx-asr,index-tts,silero-vad,paraformer-local,ali]" \
    && chmod -R a+rwX /opt/xtalk

# index-tts-vllm 服务端（api_server.py）的额外依赖
# （index-tts-vllm 仓库代码走共享文件系统挂载，不在镜像内）
RUN pip install --no-cache-dir \
        munch==4.0.0 \
        WeTextProcessing \
        descript-audiotools==0.7.2

# protobuf 3.19（被 descript-audiotools 的 <3.20 约束拉入）过旧，会导致
# chromadb/opentelemetry 导入失败；按 index-tts-vllm/overrides.txt 升级到
# 5.29.6（vLLM 0.16 / gRPC 同样要求）。pip 会对 audiotools 的约束给出警告，
# 可忽略——audiotools 仅 IndexTTS-2 的 s2mel/dac 使用，若其运行时不兼容再
# 单独处理。
RUN pip install --no-cache-dir protobuf==5.29.6

# 避免 ~/.local 用户站点包穿透文件系统挂载污染镜像环境（image-use.md 注意事项）
ENV PYTHONNOUSERSITE=True
