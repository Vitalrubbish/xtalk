# micro_turn.py

## Purpose, classes, and core methods

MicroTurnAssembler stores cumulative and emitted prefixes. LLMAgentLoop starts continuous ASR and the single clock. Each flush awaits `TurnASRReadRequested` before snapshotting the latest prefix, sending only its delta and awaiting inference. Empty deltas, including windows before the first recognized word, become `<|no voice|>` in the model service. There is no separate result-polling clock. Text-only injection can still start the clock on its first text. VAD boundaries preserve their existing request path; X2 continues consuming across pauses without closing its stream. Shutdown cancels pending ticks.

## Usage and boundaries

Registered by the Boolean duplex_enabled service switch. Native mode keeps its configuration; official weights, long sessions, audio quality and FDB require remote conda acceptance.


X2 duplex 的会话能力 `acoustic_vad_enabled=false` 由服务端按连续 ASR 能力确定。禁用声学 VAD 检测、声学开始/结束信号及 pause/resume 调度；保持会话级连续 PCM 与每拍文本读取。浏览器在握手后创建关闭 VAD 的输入设备，旧客户端声学信号在网关被忽略。Qwen 与内部文本提交边界保持原行为。验证覆盖残留 VAD 信号不触发 ASR 控制、静音和播放期间连续输入、同一解码会话及握手能力。
