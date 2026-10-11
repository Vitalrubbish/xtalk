# `src/xtalk/models/asr/qwen3asr_client.py`

`Qwen3ASRClient` 连接独立的 Qwen3-ASR HTTP 服务，维护本实例的会话 ID 和累计转写缓存。`recognize_stream` 接收 PCM16 字节并应用完整、缩短或空转写；协议错误与 HTTP 失败抛出。`recognize` 使用临时 clone，不累积前次完整音频，也不改写当前流式会话。`clone`、`reset`、`close` 管理状态隔离和资源释放，`stream_chunk_bytes_hint` 给出首选块大小。

协议与设计详见 [本地适配器](../../../../technical_reference/qwen3_asr_client.zh.md)，回归说明见 [测试文档](../../../../tests/test_qwen3_asr_client.zh.md)。
