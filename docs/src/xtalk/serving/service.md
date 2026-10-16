# service.py

## Purpose, classes, and core methods

Service automatically registers one DuplexTimelineRecorder when duplex_timeline_enabled is true. stop shuts down other managers, drains EventBus, and closes recorders in finally so shutdown events remain observable. The duplex_enabled switch registers A2/A3 scheduling and online protocol execution.

## Classes and core methods

Service owns model clones, EventBus, managers, and gateways. DefaultService supplies the standard stack. __init__ registers the recorder when the Boolean flag is exactly True; prototypes register classes while live WebSocket sessions create files. _instantiate_manager injects models/config and subscription overrides. clone copies configuration and registrations. stop closes recorders after producers and EventBus. Manual recorder registration also enables observation.

## A2/A3 update

When duplex_enabled is Boolean True, duplex_manager_classes replaces semantic control managers. Prototypes register classes; cloned sessions create an assembler/adapter. duplex_model_url selects the model service; shutdown stops the assembler, adapter and native TTS in order, with the recorder last.


X2 duplex 的会话能力 `acoustic_vad_enabled=false` 由服务端按连续 ASR 能力确定。禁用声学 VAD 检测、声学开始/结束信号及 pause/resume 调度；保持会话级连续 PCM 与每拍文本读取。浏览器在握手后创建关闭 VAD 的输入设备，旧客户端声学信号在网关被忽略。Qwen 与内部文本提交边界保持原行为。验证覆盖残留 VAD 信号不触发 ASR 控制、静音和播放期间连续输入、同一解码会话及握手能力。
