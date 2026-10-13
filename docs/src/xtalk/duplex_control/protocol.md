# protocol.py

## Purpose, classes, and core methods

Defines the DuplexCascade protocol without system backchannels. Input serialization appends EOS and encodes an empty string as no voice plus EOS. Complete-output parsing validates the five control tokens, EOS, answer text, and extra tokens with stable error codes. The observer publishes success or error events with the same correlation. A1 complete-output observation remains available; A3 uses WireMicroTurnParser for online streams and RuntimeAdapter for execution.

## Class design and method contracts

ControlToken is a string enum. ParsedSystemMicroTurn is an immutable result containing control_token, response_text, and raw_output. ProtocolParseError stores code and raw_output.

serialize_user_micro_turn encodes only an empty string as silence and preserves whitespace. parse_system_micro_turn requires an initial control token and terminal EOS. Finish-speaking requires a nonblank answer; the other four states allow whitespace only. Additional angle-bracket token content is rejected. Original text is preserved.

Error codes: missing_eos, missing_control_token, unknown_control_token, unexpected_token, missing_response_text, unexpected_response_text. observe_system_micro_turn waits for event dispatch and returns the parsed result on success or None for protocol errors. Invalid parameter types raise TypeError.

## A2/A3 update

WireMicroTurnParser.feed buffers fragmented markers and returns an ordered list of WireControl and WireText events. WireControl pairs the released spelling with its paper semantics; WireText carries answer text with the control context that precedes it. Every released marker executes in arrival order, so adjacent, repeated or reordered control tokens stay valid. Unknown angle-bracket spellings remain plain speech, and an unfinished turn stays valid text. WIRE_EOS ends the micro-turn; WIRE_NO_VOICE and WIRE_IM_START never become speech. finish records the stop or length termination reason. WIRE_CONTROLS maps the released tokenizer strings to the five paper semantics, and the A1 complete-output parser keeps its strict error codes as the paper-format reference.
