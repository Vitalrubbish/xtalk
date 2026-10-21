# micro_turn.py

## Purpose, classes, and core methods

`MicroTurnAssembler` stores the cumulative ASR prefix and the prefix already emitted to the model. `LLMAgentLoop` starts continuous ASR and the single micro-turn clock. Each flush awaits `TurnASRReadRequested` before snapshotting the latest prefix, sending only its delta and awaiting inference. Empty deltas, including windows before the first recognized word, become `<|no voice|>` in the model service. There is no separate result-polling clock. Text-only injection can still start the clock on its first text.

Acoustic VAD events are used only as ASR segment boundaries: `VADSpeechEnd` publishes `TurnASRPauseRequested`, `VADSpeechStart` requests resumption, and continuous ASR keeps consuming audio across pauses without closing its stream. Shutdown cancels pending ticks.

## Usage and boundaries

Registered by the Boolean `duplex_enabled` service switch. Native mode keeps its existing configuration. Official weights, long sessions, audio quality and the selected evaluation set require remote conda acceptance.
