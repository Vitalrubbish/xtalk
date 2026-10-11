# service.py

## 功能、类与核心方法

Service 在启用 duplex_timeline_enabled 时自动注册单个 DuplexTimelineRecorder。stop 先关闭其他 manager、等待 EventBus 收尾，再在 finally 中关闭记录器，从而保留关闭阶段事件。此入口只提供观测能力，A2/A3 的调度与协议执行仍未注册。

## 类与核心方法

Service 持有模型 clone、EventBus、manager 和 gateway；DefaultService 使用标准 manager 组合。__init__ 在布尔开关严格为 True 时自动注册记录器，原型只登记类，实时 WebSocket 会话才创建文件。_instantiate_manager 根据构造函数注入 models/config 并应用订阅覆盖；clone 复制配置与类列表；stop 把记录器放在生产者和 EventBus 之后关闭。手动注册记录器也能启用观测。
