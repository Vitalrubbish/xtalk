# service.py

## Purpose, classes, and core methods

duplex_manager_classes selects one assembler/adapter and retains native ASR, TTS, coordinator and playback. It replaces LLMAgentContextManager, LLMAgentConsumptionManager, TurnTakingManager, TurnDetectorManager, the multi-speaker semantic gate and DirectAudioManager so model decisions have one execution path. This mode targets the current single-user MVP. Repeated configuration is idempotent.

## Usage and boundaries

Registered by the Boolean duplex_enabled service switch. Native mode keeps its configuration; official weights, long sessions, audio quality and FDB require remote conda acceptance.
