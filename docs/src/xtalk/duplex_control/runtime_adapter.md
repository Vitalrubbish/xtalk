# runtime_adapter.py

## Purpose, classes, and core methods

DuplexRuntimeAdapter is the sole online protocol executor. It stores raw micro-turn history, answer identity, generated text and separate heard facts. _handle_micro_turn serializes inference and records protocol evidence; _append_user sends deltas and repairs revised user prefixes; _prompt builds official ChatML. _append_answer keeps one answer/TTS stream; thinking flushes through _finish_answer, interruption or user talking stops unplayed output through _stop_answer. Plain continuation and user backchannel retain the stream. _heard records monotonic playback confirmations; shutdown cancels inference before stopping output. ASR final never independently invokes the model; duplicate requests are rejected.

## Usage and boundaries

Registered by the Boolean duplex_enabled service switch. Native mode keeps its configuration; official weights, long sessions, audio quality and FDB require remote conda acceptance.

Older prefix versions produce stale_prefix. Silent windows at the same version can continue an answer; ASR arriving during inference is consumed at the next call, matching official serial generation.

A recognized streamed control token executes stop/close immediately; waiting for EOS only validates the complete micro-turn and adds no interruption delay.

Protocol observations preserve the pre-action response ID so stop/close controls still correlate with their original answer.
