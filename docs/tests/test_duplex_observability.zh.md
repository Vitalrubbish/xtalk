# test_duplex_observability.py

## 功能、类与核心方法

使用模拟 PCM TTS 和异步文本流运行生成、TTS、协调器、播放的真实事件链。验证交付回执字段、并发响应隔离、预分配 ID、已播反馈新请求、抢占字段及 Service 日志开关和 shutdown 尾部。

## 运行

~~~bash
conda run -n paratalker-dev env PYTHONPATH=src python -m unittest tests.test_duplex_observability -v
~~~

本地使用现有 conda 环境；真实模型服务与集群链路在远端单独验收。
