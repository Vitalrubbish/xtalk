# __init__.py

## Purpose, classes, and core methods

Public protocol package entry point. It exports the input silence marker, end marker, five control states, parse results, exceptions, and DuplexCorrelation. Callers import concrete implementations from the protocol and timeline modules.

## Public symbols

NO_VOICE, EOS, ControlToken, ParsedSystemMicroTurn, ProtocolParseError, DuplexCorrelation; serialize_user_micro_turn, parse_system_micro_turn, observe_system_micro_turn.
