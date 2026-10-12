# test_duplex_runtime.py

## 功能、类与核心方法

测试 WireMicroTurnParser 与 DuplexRuntimeTests：逐字符分片、控制含义、回答续写、预算截断、首次文本启动、空窗口、增量、final 去重、慢推理聚合、修订、打断保留已播事实、错误、关闭取消、过期版本拒绝、原生 TTS/播放结算和 Service 单一控制链路。使用真实 EventBus，模型服务为确定性模拟。

~~~bash
conda run -n paratalker-dev env PYTHONPATH=src python -m unittest tests.test_duplex_runtime -v
~~~

新增分片打断测试：只有 control marker 时立即停播，延迟 EOS 不推迟动作。

新增 user backchannel + 同一 micro-turn 回答续写测试，验证 marker 分片与单一 response/TTS；控制等待状态在活动回答期间缺失 EOS 仍拒绝。
