# test_turn_detector_manager.py

## 功能、类与核心方法

验证自然播放结束与提前停止的区别，并通过真实 EventBus 检查 TTSChunkReady 保持监听、TTSStarted 关闭监听、TTSPlaybackFinished 恢复监听。

## 运行

~~~bash
conda run -n paratalker-dev env PYTHONPATH=src python -m unittest tests.test_turn_detector_manager -v
~~~

本地使用现有 conda 环境；真实模型服务与集群链路在远端单独验收。
