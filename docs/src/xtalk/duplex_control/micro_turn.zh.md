# micro_turn.py

## 功能、类与核心方法

MicroTurnAssembler 持有累计前缀与上次发出前缀，首次非空文本后启动时钟。_accept_asr 更新前缀、状态和版本；flush 生成不可变快照、仅发送新增后缀、等待模型完成，输入继续接收；_clock 采用官方串行 tick，shutdown 取消待处理任务。LLMAgentLoop 启动持续 ASR；声学 VADSpeechEnd 会让 ASR 定稿当前用户片段（`TurnASRPauseRequested`，保留 ASR 状态），VADSpeechStart 再恢复采集——本模块替换掉了官方 `TurnTakingManager`，它原本是这两个边界的唯一发布者。

## 使用与边界

由 Service 的 duplex_enabled 布尔开关注册。原生模式保持既有配置；官方模型、长会话、音频质量与 FDB 需远端 conda 验收。
