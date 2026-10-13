# runtime_adapter.py

## Purpose, classes, and core methods

DuplexRuntimeAdapter is the sole online protocol executor. It stores micro-turn history as user text plus the exact assistant token ids returned by the model service, together with answer identity, generated text and separate heard facts. _handle_micro_turn serializes inference, decodes every response to im_end and records protocol evidence; _append_user sends deltas and repairs revised user prefixes; _request_history builds the wire history that the service flattens into official ChatML. _append_answer keeps one answer/TTS stream and filters periods for speech only; thinking flushes through _finish_answer. _apply_control executes every decoded control token in arrival order and observes each one with its pre-action response ID, so repeated or adjacent markers stay valid. finish talking opens the speaking window; user is talking and user interruption reset unplayed output through _reset_speaking only while that window is open, mirroring the released tts_speaking_flag. Plain continuation and user backchannel retain the stream. _heard records monotonic playback confirmations; shutdown cancels inference before stopping output. ASR final never independently invokes the model; duplicate requests are rejected.

## Usage and boundaries

Registered by the Boolean duplex_enabled service switch. Native mode keeps its configuration; official weights, long sessions, audio quality and FDB require remote conda acceptance.

Older prefix versions produce stale_prefix. Silent windows at the same version can continue an answer; ASR arriving during inference is consumed at the next call, matching official serial generation.

Control tokens are applied in arrival order and the text that follows them flows to speech. An interruption that arrives before the speaking window opens leaves playback untouched.

Protocol observations preserve the pre-action response ID so stop controls still correlate with their original answer.
