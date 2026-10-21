# runtime_adapter.py

## Purpose and state

DuplexRuntimeAdapter is the sole online protocol executor. It serializes micro-turns and stores user text deltas, exact assistant token IDs, answer identities, and separate heard facts. Session KV reuse defaults to enabled; an explicit diagnostic setting can disable it. Inference arbitration and playback ownership remain shared.

## Core methods

_handle_micro_turn submits identified histories, consumes the complete generation stream, and rejects duplicate requests or stale prefixes. _append_user handles deltas and ASR rewrites; _request_history preserves raw IDs. _apply_control executes markers in arrival order. finish talking opens the speaking window; talking/interruption stop unplayed output while that window is open. User backchannels and ordinary continuation retain the stream.

_append_answer preserves response_id and the TTS session across micro-turns, appends text through the existing playback chain, removes periods from the synthesis copy, and logs request/answer identity. _finish_answer flushes on thinking; _stop_answer stops unplayed content; _heard records monotonic playback confirmations. shutdown cancels inference, stops output, then releases the session cache.

## Boundaries

ASR final independently updates input; the next scheduled call consumes ASR arriving during inference. The model may answer again on an unchanged prefix after thinking; complete generated history remains intact and quality evaluation checks repetition. System backchannels remain disabled. The existing user-backchannel marker describes user behavior.
