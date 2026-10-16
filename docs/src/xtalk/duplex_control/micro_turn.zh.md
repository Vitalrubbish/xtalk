# micro_turn.py

## 功能、类与核心方法

MicroTurnAssembler 持有累计前缀与上次发出前缀，LLMAgentLoop 启动持续 ASR 与唯一时钟。_accept_asr 更新前缀、状态和版本；flush 先同步请求 `TurnASRReadRequested`，再生成本拍快照、仅发送新增后缀、等待模型完成，音频继续接收。无新增或尚未识别首词时发空 user 文本，模型服务将其编码为 `<|no voice|>`；不新增结果轮询时钟。_clock 继续串行 tick，shutdown 取消待处理任务。直接注入文本但未启动音频会话时仍可由首条文本启动时钟。声学 VADSpeechEnd 发布 `TurnASRPauseRequested`，VADSpeechStart 再请求恢复；X2 持续接收音频，暂停不结束流。

## 使用与边界

由 Service 的 duplex_enabled 布尔开关注册。原生模式保持既有配置；官方模型、长会话、音频质量与 FDB 需远端 conda 验收。


X2 duplex 的会话能力 `acoustic_vad_enabled=false` 由服务端按连续 ASR 能力确定。禁用声学 VAD 检测、声学开始/结束信号及 pause/resume 调度；保持会话级连续 PCM 与每拍文本读取。浏览器在握手后创建关闭 VAD 的输入设备，旧客户端声学信号在网关被忽略。Qwen 与内部文本提交边界保持原行为。验证覆盖残留 VAD 信号不触发 ASR 控制、静音和播放期间连续输入、同一解码会话及握手能力。
