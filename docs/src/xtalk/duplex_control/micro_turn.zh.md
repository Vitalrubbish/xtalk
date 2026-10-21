# micro_turn.py

## 功能、类与核心方法

`MicroTurnAssembler` 持有累计 ASR 前缀与已经发给模型的前缀。`LLMAgentLoop` 启动连续 ASR 与唯一 micro-turn 时钟。每次 flush 先同步请求 `TurnASRReadRequested`，再基于最新前缀生成本拍快照、只发送新增后缀并等待推理完成，音频继续接收。无新增或尚未识别首词时发送空 user 文本，模型服务将其编码为 `<|no voice|>`；不存在独立的结果轮询时钟。直接注入文本但未启动音频会话时，首条文本仍可启动时钟。

声学 VAD 事件只作为 ASR 片段边界：`VADSpeechEnd` 发布 `TurnASRPauseRequested`，`VADSpeechStart` 请求恢复，连续 ASR 在暂停期间继续接收音频且不关闭流。shutdown 取消待处理 tick。

## 使用与边界

由 `duplex_enabled` 布尔开关注册；原生模式保持既有配置。官方权重、长会话、音频质量与所选评测集需远端 conda 验收。
