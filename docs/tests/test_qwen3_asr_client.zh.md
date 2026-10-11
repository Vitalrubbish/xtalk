# `tests/test_qwen3_asr_client.py`

`Qwen3ASRClientTests` 通过 `_FakeASRService` 和 `_FakeResponse` 模拟会话注册、累计转写与删除，不依赖 GPU。测试实际调用 `clone` 验证会话隔离，检查 reset、临时 flush、空及缩短修订、HTTP/协议失败，以及独立一次性识别在成功和失败时均释放临时会话。

运行：`PYTHONPATH=src python -m unittest discover -s tests -p test_qwen3_asr_client.py -v`。模型服务联调在远端另行运行，测试通过不代表 GPU 模型或播放已验收。
