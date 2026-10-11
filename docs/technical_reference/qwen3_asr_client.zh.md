# 本地 Qwen3-ASR HTTP 适配器

## 功能与类设计

`src/xtalk/models/asr/qwen3asr_client.py` 的 `Qwen3ASRClient` 实现 ASR 契约：接收 16 kHz 单声道 PCM16 字节，返回累计转写。每个实例按服务端 session ID 隔离流式状态；模型推理由外部服务负责。异步调用复用 ASR 基类的线程执行包装。

## 核心方法

- `recognize_stream`：通过 JSON 发送 base64 音频与临时 `is_final` 标记；成功返回的累计文本覆盖缓存，包括空字符串和缩短的修订。缺失或非字符串 `text` 属于协议错误，HTTP 错误直接抛出。
- `recognize`：在临时 clone 会话中识别完整音频，完成或失败后释放临时会话；连续调用互不累积，也不改变正在进行的流式会话。
- `clone`：复制配置，创建独立连接池与空会话状态。
- `reset`：清空本地文本并请求删除远端会话。
- `close`：释放会话和连接池。
- `stream_chunk_bytes_hint`：按 `chunk_ms` 返回首选 PCM 字节数。

## 服务协议与验证

服务提供 `POST /v1/session`、`POST /v1/recognize`、`DELETE /v1/session/{id}`。识别请求包含 `session_id`、`audio` 和 `is_final`；响应 `text` 为当前累计文本。临时 flush 保留会话，真实结束由 reset 决定。

`tests/test_qwen3_asr_client.py` 用模拟传输验证累计/空/缩短修订、HTTP 失败、实际 clone 隔离、reset、临时 flush、连续一次性识别及临时会话释放。模型与 GPU 效果在远端另行复测。
