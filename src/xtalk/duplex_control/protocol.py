"""Parse the five control tokens of DuplexCascade without system backchannels."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .state import DuplexCorrelation

if TYPE_CHECKING:
    from xtalk.serving.event_bus import EventBus

NO_VOICE = "<no voice>"
EOS = "<EOS>"
_TOKEN_PATTERN = re.compile(r"<[^<>]+>")


class ControlToken(str, Enum):
    """Allowed system control tokens in the DuplexCascade A protocol."""

    USER_IS_SPEAKING = "<user is speaking>"
    USER_FINISH_SPEAKING = "<user finish speaking>"
    USER_IS_INTERRUPTING = "<user is interrupting>"
    USER_BACKCHANNEL = "<user backchannel>"
    USER_IS_THINKING = "<user is thinking>"


@dataclass(frozen=True)
class ParsedSystemMicroTurn:
    """One validated system micro-turn and its optional answer text.

    Parameters
    ----------
    control_token : ControlToken
        LLM-selected control state.
    response_text : str
        Answer text after the finish-speaking token. Empty for other states.
    raw_output : str
        Complete unmodified model output.
    """

    control_token: ControlToken
    response_text: str
    raw_output: str


class ProtocolParseError(ValueError):
    """Report a stable error code and the unmodified invalid model output.

    Parameters
    ----------
    code : str
        Error category for structured protocol events.
    raw_output : str
        Complete model output that failed validation.
    message : str
        Human-readable explanation of the validation failure.
    """

    def __init__(self, code: str, raw_output: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.raw_output = raw_output


def serialize_user_micro_turn(text: str) -> str:
    """Encode one visible user micro-turn, including an empty silent window.

    Parameters
    ----------
    text : str
        Text already visible to the runtime at the current micro-turn boundary.

    Returns
    -------
    str
        User text or the silence marker followed by the end marker.
    """

    if not isinstance(text, str):
        raise TypeError("micro-turn text must be a string")
    return f"{text if text else NO_VOICE}{EOS}"


def parse_system_micro_turn(raw_output: str) -> ParsedSystemMicroTurn:
    """Validate one complete system micro-turn without choosing a state.

    Parameters
    ----------
    raw_output : str
        Complete LLM output, starting with one control token and ending in EOS.

    Returns
    -------
    ParsedSystemMicroTurn
        Raw control token and answer text when the output follows the protocol.

    Raises
    ------
    ProtocolParseError
        Raised for missing markers, unsupported or repeated control tokens,
        non-answer text after a wait state, or a malformed answer.
    """

    if not isinstance(raw_output, str):
        raise TypeError("system micro-turn must be a string")
    if not raw_output.endswith(EOS):
        raise ProtocolParseError("missing_eos", raw_output, "system micro-turn must end with <EOS>")

    body = raw_output[: -len(EOS)]
    marker = _TOKEN_PATTERN.match(body)
    if marker is None:
        raise ProtocolParseError("missing_control_token", raw_output, "system micro-turn must start with a control token")
    try:
        control_token = ControlToken(marker.group())
    except ValueError as exc:
        raise ProtocolParseError("unknown_control_token", raw_output, "unsupported system control token") from exc

    content = body[marker.end() :]
    if _TOKEN_PATTERN.search(content):
        raise ProtocolParseError("unexpected_token", raw_output, "system micro-turn contains an additional token")
    if control_token is ControlToken.USER_FINISH_SPEAKING:
        if not content.strip():
            raise ProtocolParseError("missing_response_text", raw_output, "finish-speaking state requires answer text")
    elif content.strip():
        raise ProtocolParseError("unexpected_response_text", raw_output, "wait-state micro-turn cannot contain answer text")

    return ParsedSystemMicroTurn(control_token, content, raw_output)


async def observe_system_micro_turn(
    event_bus: EventBus,
    correlation: DuplexCorrelation,
    raw_output: str,
) -> ParsedSystemMicroTurn | None:
    """Parse one complete model output and publish its protocol observation.

    Parameters
    ----------
    event_bus : EventBus
        Session event bus used for observational events.
    correlation : DuplexCorrelation
        Identifiers assigned to the originating micro-turn.
    raw_output : str
        Complete raw model output.

    Returns
    -------
    ParsedSystemMicroTurn | None
        Validated micro-turn, or None after publishing a protocol error.
    """

    from xtalk.serving.event_bus import EventDispatchMode
    from xtalk.serving.events import DuplexProtocolError, DuplexProtocolParsed

    identifiers = dict(
        session_id=correlation.session_id,
        request_id=correlation.request_id,
        response_id=correlation.response_id,
        turn_id=correlation.turn_id,
        segment_id=correlation.segment_id,
        prefix_version=correlation.prefix_version,
    )
    try:
        parsed = parse_system_micro_turn(raw_output)
    except ProtocolParseError as exc:
        await event_bus.publish(
            DuplexProtocolError(
                **identifiers,
                raw_output=exc.raw_output,
                error_code=exc.code,
                reason=str(exc),
            ),
            mode=EventDispatchMode.WAIT_UNTIL_COMPLETE,
        )
        return None

    await event_bus.publish(
        DuplexProtocolParsed(
            **identifiers,
            state_token=parsed.control_token.value,
            response_text=parsed.response_text,
            raw_output=parsed.raw_output,
        ),
        mode=EventDispatchMode.WAIT_UNTIL_COMPLETE,
    )
    return parsed
