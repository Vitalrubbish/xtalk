# service.py

## 功能、类与核心方法

duplex_manager_classes 选择单一 assembler/adapter，保留原生 ASR、TTS、coordinator 与 playback。移除 LLMAgentContextManager、LLMAgentConsumptionManager、TurnTakingManager、TurnDetectorManager、多说话人语义 gate 和 DirectAudioManager，防止模型判断旁路；此模式针对当前单用户 MVP。函数对重复配置保持幂等。

## 使用与边界

由 Service 的 duplex_enabled 布尔开关注册。原生模式保持既有配置；官方模型、长会话、音频质量与所选评测集需远端 conda 验收。
