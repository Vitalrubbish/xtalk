# input_gateway.py

负责接收 WebSocket 的 PCM 和控制消息，转换成会话事件。

`InputGateway` 管理连接、采样率和文本任务；将会话配置传给 `TextMsgHandler`。音频帧继续通过音频事件独立送入 ASR。

`TextMsgHandler` 使用分发表处理 JSON 消息。`_handle_vad_speech_start()` 和 `_handle_vad_speech_end()` 仅在 `acoustic_vad_enabled` 为真时发布声学边界；X2 duplex 的旧客户端信号直接忽略，不触发 ASR 暂停或重启。文本提交仍使用内部合成边界来串行中止音频、交付文字和恢复输入，不依赖声学检测。

服务端按连续 ASR 能力确定配置；缺省为启用，以兼容普通 X-Talk 和 Qwen 对照。音频持续接收与 micro-turn 的文本读取均不等待声学边界。
