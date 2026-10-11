"""DuplexCascade protocol and observation primitives for X-Talk."""

from .protocol import (
    EOS,
    NO_VOICE,
    ControlToken,
    ParsedSystemMicroTurn,
    ProtocolParseError,
    observe_system_micro_turn,
    parse_system_micro_turn,
    serialize_user_micro_turn,
)
from .state import DuplexCorrelation

__all__ = [
    "EOS",
    "NO_VOICE",
    "ControlToken",
    "DuplexCorrelation",
    "ParsedSystemMicroTurn",
    "ProtocolParseError",
    "observe_system_micro_turn",
    "parse_system_micro_turn",
    "serialize_user_micro_turn",
]
