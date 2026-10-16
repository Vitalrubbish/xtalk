# X2 client tests

Verify 80 ms input hints, distinct pause/EOF requests and direct online transcript delivery.

F1 uses deferred HTTP results with the real ASRManager and MicroTurnAssembler. Tests cover same-tick delivery without further audio, empty first and unchanged windows, exactly one read per tick with no independent polling, preservation of partial audio, no EOF from reads, and cleanup of in-flight reads on cancellation/shutdown.


X2 duplex 的会话能力 `acoustic_vad_enabled=false` 由服务端按连续 ASR 能力确定。禁用声学 VAD 检测、声学开始/结束信号及 pause/resume 调度；保持会话级连续 PCM 与每拍文本读取。浏览器在握手后创建关闭 VAD 的输入设备，旧客户端声学信号在网关被忽略。Qwen 与内部文本提交边界保持原行为。验证覆盖残留 VAD 信号不触发 ASR 控制、静音和播放期间连续输入、同一解码会话及握手能力。
