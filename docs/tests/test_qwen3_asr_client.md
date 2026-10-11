# `tests/test_qwen3_asr_client.py`

`Qwen3ASRClientTests` uses `_FakeASRService` and `_FakeResponse` to simulate session creation, cumulative transcripts and deletion without a GPU. Tests call `clone` to check actual isolation and cover reset, temporary flush, empty and shortened revisions, HTTP/protocol errors, and one-shot session cleanup on success and failure.

Run `PYTHONPATH=src python -m unittest discover -s tests -p test_qwen3_asr_client.py -v`. Model-service integration runs separately on the remote server; these tests do not certify GPU inference or playback.
