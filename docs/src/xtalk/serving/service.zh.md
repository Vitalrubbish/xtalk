# service.py

## 功能、类与核心方法

Service 在启用 duplex_timeline_enabled 时自动注册单个 DuplexTimelineRecorder。stop 先关闭其他 manager、等待 EventBus 收尾，再在 finally 中关闭记录器，从而保留关闭阶段事件。duplex_enabled 开关注册 A2/A3 的调度与在线协议执行。

## 类与核心方法

Service 持有模型 clone、EventBus、manager 和 gateway；DefaultService 使用标准 manager 组合。__init__ 在布尔开关严格为 True 时自动注册记录器，原型只登记类，实时 WebSocket 会话才创建文件。_instantiate_manager 根据构造函数注入 models/config 并应用订阅覆盖；clone 复制配置与类列表；stop 把记录器放在生产者和 EventBus 之后关闭。手动注册记录器也能启用观测。

## A2/A3 更新

duplex_enabled 严格为 True 时调用 duplex_manager_classes 替换语义控制链路；原型只登记，clone 后为会话创建 assembler、adapter。模型地址由 duplex_model_url 指定；stop 按 assembler、adapter、原生 TTS 顺序关闭，记录器最后关闭。


X2 duplex 的会话能力 `acoustic_vad_enabled=false` 由服务端按连续 ASR 能力确定。禁用声学 VAD 检测、声学开始/结束信号及 pause/resume 调度；保持会话级连续 PCM 与每拍文本读取。浏览器在握手后创建关闭 VAD 的输入设备，旧客户端声学信号在网关被忽略。Qwen 与内部文本提交边界保持原行为。验证覆盖残留 VAD 信号不触发 ASR 控制、静音和播放期间连续输入、同一解码会话及握手能力。
