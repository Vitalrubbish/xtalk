# `src/xtalk/models/asr/qwen3asr_client.py`

`Qwen3ASRClient` connects to an independent Qwen3-ASR HTTP service and holds an instance-specific session ID and cumulative transcript. `recognize_stream` accepts PCM16 bytes and applies full, shortened or empty transcripts. Protocol and HTTP failures propagate. `recognize` uses a temporary clone, keeping one-shot calls independent and preserving an active stream. `clone`, `reset` and `close` manage isolation and cleanup; `stream_chunk_bytes_hint` reports the preferred input size.

See the [adapter design](../../../../technical_reference/qwen3_asr_client.md) and [test documentation](../../../../tests/test_qwen3_asr_client.md).
