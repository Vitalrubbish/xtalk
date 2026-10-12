# protocol.py

## Purpose, classes, and core methods

Defines the DuplexCascade protocol without system backchannels. Input serialization appends EOS and encodes an empty string as no voice plus EOS. Complete-output parsing validates the five control tokens, EOS, answer text, and extra tokens with stable error codes. The observer publishes success or error events with the same correlation. A1 complete-output observation remains available; A3 uses WireMicroTurnParser for online streams and RuntimeAdapter for execution.

## Class design and method contracts

ControlToken is a string enum. ParsedSystemMicroTurn is an immutable result containing control_token, response_text, and raw_output. ProtocolParseError stores code and raw_output.

serialize_user_micro_turn encodes only an empty string as silence and preserves whitespace. parse_system_micro_turn requires an initial control token and terminal EOS. Finish-speaking requires a nonblank answer; the other four states allow whitespace only. Additional angle-bracket token content is rejected. Original text is preserved.

Error codes: missing_eos, missing_control_token, unknown_control_token, unexpected_token, missing_response_text, unexpected_response_text. observe_system_micro_turn waits for event dispatch and returns the parsed result on success or None for protocol errors. Invalid parameter types raise TypeError.

## A2/A3 update

WireMicroTurnParser.feed buffers fragmented markers and returns valid answer text only. finish validates EOS, empty answers and stop/length termination. Runtime execution treats a complete interruption marker as an immediate terminal boundary before finish: it cancels the stream, preserves the raw marker for observation and internally closes only the prompt-history representation. Plain text is allowed for answer continuations; user backchannel may also precede continuation text for the current answer; speaking/thinking prohibit text and system backchannel is rejected. Budget truncation is accepted only for answer fragments and preserves raw truncated history. WIRE_CONTROLS maps released tokenizer strings to the five paper semantics.
