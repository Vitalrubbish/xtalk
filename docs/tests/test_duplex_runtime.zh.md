# test_duplex_runtime.py

## 功能、类与核心方法

测试 WireMicroTurnParser 与 DuplexRuntimeTests：逐字符分片、控制含义、回答续写、预算截断、首次文本启动、空窗口、增量、final 去重、慢推理聚合、修订、打断保留已播事实、错误、关闭取消、过期版本拒绝、原生 TTS/播放结算、Service 单一控制链路，以及 ASR 片段边界（声学语音结束只发一次 pause、语音开始恢复、合成文本输入或消费者未启动时不发 pause）。使用真实 EventBus，模型服务为确定性模拟。

~~~bash
conda run -n paratalker-dev env PYTHONPATH=src python -m unittest tests.test_duplex_runtime -v
~~~

新增打断对齐测试：仅在"正在播报"窗口开启时 reset 未播音频，模型流仍解码到 `<|im_end|>`；assistant 生成 token id 原样进入下一条 prompt；窗口未开启时的 interruption 不改变播放。另检查协议观察保留原始 marker。历史以 user 文本 + assistant token id 保存，`_request_history` 生成线上结构。

新增 user backchannel + 同一 micro-turn 回答续写测试，验证 marker 分片与单一 response/TTS；控制等待状态在活动回答期间缺失 EOS 仍拒绝。

ScriptedClient 在脚本片段不含 `GenerationEnd` 时补一条 stop 结束记录，与真实服务始终上报生成 id 的行为一致。
