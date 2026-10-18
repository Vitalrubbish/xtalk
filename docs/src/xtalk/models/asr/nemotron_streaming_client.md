# Nemotron 客户端

`NemotronStreamingClient` 复用 X2StreamingClient 的连续 ASR HTTP 传输接口，不复用或回退 X2 模型。`_text` 验证 session/generation UUID、前缀版本和追加单调；`reset` 释放远端流再清空文本；`clone` 创建同类型独立 HTTP 客户端。空音频读取 GET result，is_final 仅暂停提示，finish_stream 才 EOF。16kHz mono PCM16，chunk_ms 默认为 80，模型保持 160ms。失败直接上报，不保留旧前缀伪装成功。
