# micro_turn.py

## 功能、类与核心方法

MicroTurnAssembler 持有累计前缀与上次发出前缀，LLMAgentLoop 启动持续 ASR 与唯一时钟。_accept_asr 更新前缀、状态和版本；flush 先同步请求 `TurnASRReadRequested`，再生成本拍快照、仅发送新增后缀、等待模型完成，音频继续接收。无新增或尚未识别首词时发空 user 文本，模型服务将其编码为 `<|no voice|>`；不新增结果轮询时钟。_clock 继续串行 tick，shutdown 取消待处理任务。直接注入文本但未启动音频会话时仍可由首条文本启动时钟。声学 VADSpeechEnd 发布 `TurnASRPauseRequested`，VADSpeechStart 再请求恢复；X2 持续接收音频，暂停不结束流。

## 使用与边界

由 Service 的 duplex_enabled 布尔开关注册。原生模式保持既有配置；官方模型、长会话、音频质量与 FDB 需远端 conda 验收。
