# test_duplex_protocol.py

## 功能、类与核心方法

覆盖输入序列化、五种控制状态、回答文本、协议错误码、协议事件观测、JSONL 错误码与序号、生成到播放的关联传递、记录器取消订阅和重复关闭。测试使用 EventBus、临时目录和模拟 stream，不需要模型推理。

## 运行

~~~bash
conda run -n interclarify-dev python -m unittest tests.test_duplex_protocol -v
~~~

本地使用现有 conda 环境；真实模型服务与集群链路在远端单独验收。
