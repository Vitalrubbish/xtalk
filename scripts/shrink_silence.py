"""压缩测试音频中的长静音段。

背景：测试数据集中的长 case（30s/60s）音频在句间存在超过客户端 VAD
redemption（500ms）的静音，导致 VAD 把单轮输入切成多轮，latency 测量
（用户语音结束 → AI 语音开始的配对）失效或失真。本脚本把音频中超过
``--max-silence`` 的静音段压缩到该长度，使整段音频对 VAD 呈现为单个语句。

用法::

    python scripts/shrink_silence.py <audio.wav> [--max-silence 0.25] [--out <path>]
"""

from __future__ import annotations

import argparse

import numpy as np
import soundfile as sf


def shrink_silence(
    audio: np.ndarray,
    sample_rate: int,
    *,
    max_silence_sec: float = 0.25,
    threshold_ratio: float = 0.02,
    min_silence_sec: float = 0.05,
) -> np.ndarray:
    """Compress silence gaps longer than ``max_silence_sec``.

    Args:
        audio: Mono audio samples.
        sample_rate: Sample rate of ``audio``.
        max_silence_sec: Maximum allowed silence gap duration in seconds.
        threshold_ratio: Silence threshold as a fraction of peak amplitude.
        min_silence_sec: Minimum gap length to be treated as silence.

    Returns:
        Audio with long silences compressed.
    """
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak <= 0:
        return audio
    threshold = peak * threshold_ratio
    is_speech = np.abs(audio) > threshold

    # 找语音/静音边界
    changes = np.diff(is_speech.astype(np.int8))
    boundaries = np.concatenate(
        ([0], np.nonzero(changes)[0] + 1, [len(audio)])
    )
    segments = []  # (start, end, is_speech)
    for i in range(len(boundaries) - 1):
        segments.append((boundaries[i], boundaries[i + 1], bool(is_speech[boundaries[i]])))

    max_len = int(max_silence_sec * sample_rate)
    min_len = int(min_silence_sec * sample_rate)
    pieces = []
    for start, end, speech in segments:
        length = end - start
        if not speech and length > max_len and length >= min_len:
            # 保留静音段的前半部分作为自然停顿
            pieces.append(audio[start : start + max_len])
        else:
            pieces.append(audio[start:end])
    return np.concatenate(pieces)


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", help="input wav path")
    parser.add_argument("--out", help="output path (default: overwrite input)")
    parser.add_argument("--max-silence", type=float, default=0.25)
    args = parser.parse_args()

    audio, sr = sf.read(args.audio, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    before = len(audio) / sr
    out = shrink_silence(audio, sr, max_silence_sec=args.max_silence)
    after = len(out) / sr
    sf.write(args.out or args.audio, out, sr, subtype="PCM_16")
    print(f"{args.audio}: {before:.1f}s -> {after:.1f}s")


if __name__ == "__main__":
    main()
