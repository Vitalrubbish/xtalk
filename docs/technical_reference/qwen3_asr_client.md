# Local Qwen3-ASR HTTP adapter

## Purpose and class design

`Qwen3ASRClient` in `src/xtalk/models/asr/qwen3asr_client.py` implements the ASR contract: 16 kHz mono PCM16 byte input and cumulative transcripts. Each instance owns a service session ID and independent streaming state. An external service performs inference. Async calls use the ASR base class executor wrapper.

## Core methods

- `recognize_stream`: sends base64 audio and the temporary `is_final` flag as JSON. Successful cumulative text replaces the cache, including empty and shortened revisions. Missing or non-string `text` raises a protocol error; HTTP failures propagate.
- `recognize`: uses a temporary cloned session for a complete buffer and releases it on success or failure. Repeated calls remain independent and preserve an existing streaming session.
- `clone`: copies configuration into an independent connection pool and empty session.
- `reset`: clears local text and requests remote session deletion.
- `close`: releases the session and connection pool.
- `stream_chunk_bytes_hint`: calculates preferred PCM bytes from `chunk_ms`.

## Service protocol and verification

The service exposes `POST /v1/session`, `POST /v1/recognize`, and `DELETE /v1/session/{id}`. Recognition requests contain `session_id`, `audio`, and `is_final`; response `text` contains the cumulative transcript. Temporary flush preserves the session; reset marks its end.

`tests/test_qwen3_asr_client.py` uses fake transport to verify cumulative, empty and shortened revisions, HTTP failures, actual clone isolation, reset, temporary flush, repeated one-shot recognition and temporary session cleanup. Model and GPU behavior are checked separately on the remote server.
