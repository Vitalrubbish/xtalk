"""index-tts-vllm API server 启动包装器。

背景：集群镜像中 torchaudio 2.9 的 ``torchaudio.load`` 强制委托给
torchcodec，而镜像里的 torchcodec 0.15.0（PyPI 版）按 CUDA 13 构建，
在 CUDA 12.8 环境因缺 ``libnvrtc.so.13`` 无法加载，导致 IndexTTS 服务在
注册参考语音时崩溃（进而 vLLM 引擎关闭连带杀掉整个作业进程组）。

本包装器在启动 api_server 前将 ``torchaudio.load`` 替换为 soundfile 实现
（返回与 torchaudio 相同的 ``(channels_first_tensor, sample_rate)``），
绕开 torchcodec。对 WAV 参考语音功能等价。

用法（cwd 需为 index-tts-vllm 仓库根目录，以便 ``import patch_vllm`` 生效）::

    python itts_serve.py api_server.py --model_dir <dir> --port 11996
    python itts_serve.py api_server_v2.py --model_dir <dir> --port 11997
"""

import runpy
import sys

import soundfile as sf
import torch
import torchaudio


def _load_with_soundfile(uri, *args, **kwargs):
    """``torchaudio.load`` 的 soundfile 替代实现。"""
    audio, sr = sf.read(uri, dtype="float32", always_2d=True)
    return torch.from_numpy(audio.T.copy()), sr


torchaudio.load = _load_with_soundfile

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    import os

    server = sys.argv[1]
    sys.argv = [server] + sys.argv[2:]
    # 模拟直接运行脚本的行为：把脚本所在目录加入 sys.path
    sys.path.insert(0, os.path.dirname(os.path.abspath(server)))
    runpy.run_path(server, run_name="__main__")
