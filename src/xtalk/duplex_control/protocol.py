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


WIRE_EOS = "<|im_end|>"
WIRE_NO_VOICE = "<|no voice|>"
WIRE_CONTROLS = {
    "<|user is talking|>": ControlToken.USER_IS_SPEAKING,
    "<|user finish talking|>": ControlToken.USER_FINISH_SPEAKING,
    "<|user interruption|>": ControlToken.USER_IS_INTERRUPTING,
    "<|user backchannel|>": ControlToken.USER_BACKCHANNEL,
    "<|user is thinking|>": ControlToken.USER_IS_THINKING,
}


class WireMicroTurnParser:
    """Validate streamed official-weight output and hold fragmented special tokens.

    Parameters
    ----------
    continuation_allowed : bool
        Whether an existing answer can accept a plain-text system micro-turn.
    """

    def __init__(self, continuation_allowed: bool = False) -> None:
        self.continuation_allowed = continuation_allowed
        self.raw_output = ""
        self.control: ControlToken | None = None
        self.wire_token = ""
        self.text = ""
        self._pending = ""
        self._header_done = False
        self.ended = False

    def feed(self, chunk: str) -> str:
        """Consume a raw fragment and return only newly validated answer text.

        Parameters
        ----------
        chunk : str
            Decoded model fragment with special tokens preserved.

        Returns
        -------
        str
            Incremental text safe to forward to the existing TTS chain.
        """
        self.raw_output += chunk
        self._pending += chunk
        if self.ended:
            if self._pending.strip():
                self._fail("trailing_output")
            self._pending = ""
            return ""
        if not self._header_done:
            if not self._pending:
                return ""
            if self._pending.startswith("<"):
                if ">" not in self._pending:
                    return ""
                end = self._pending.index(">") + 1
                marker = self._pending[:end]
                self.control = WIRE_CONTROLS.get(marker)
                if self.control is None:
                    # An empty continuation still needs a valid active answer.
                    if marker == WIRE_EOS and self.continuation_allowed:
                        self._header_done = True
                    else:
                        self._fail("unknown_control_token")
                else:
                    self.wire_token = marker
                    self._pending = self._pending[end:]
                    self._header_done = True
            elif self.continuation_allowed:
                self._header_done = True
            else:
                self._fail("missing_control_token")
        answer = self.control is ControlToken.USER_FINISH_SPEAKING or (
            self.control in (None, ControlToken.USER_BACKCHANNEL) and self.continuation_allowed)
        if not answer:
            if WIRE_EOS.startswith(self._pending):
                if self._pending == WIRE_EOS:
                    self.ended = True
                    self._pending = ""
                return ""
            if self._pending.startswith(WIRE_EOS) and not self._pending[len(WIRE_EOS):].strip():
                self.ended = True
                self._pending = ""
                return ""
            self._fail("unexpected_response_text")
        start = self._pending.find("<")
        if start < 0:
            output, self._pending = self._pending, ""
        else:
            output, self._pending = self._pending[:start], self._pending[start:]
            if self._pending.startswith(WIRE_EOS):
                tail = self._pending[len(WIRE_EOS):]
                if tail.strip():
                    self._fail("trailing_output")
                self.ended = True
                self._pending = ""
            elif not WIRE_EOS.startswith(self._pending):
                self._fail("unexpected_token")
        self.text += output
        return output

    def finish(self, finish_reason: str = "stop") -> None:
        """Validate a complete micro-turn or an official token-budget truncation.

        Parameters
        ----------
        finish_reason : str
            Service termination reason; length permits an unfinished answer only.
        """
        if self._pending or not self._header_done:
            self._fail("missing_eos")
        if not self.ended and not (
            finish_reason == "length" and bool(self.text) and (
                self.control is ControlToken.USER_FINISH_SPEAKING or
                self.control in (None, ControlToken.USER_BACKCHANNEL) and self.continuation_allowed)):
            self._fail("missing_eos")
        if self.control is ControlToken.USER_FINISH_SPEAKING and not self.text.strip():
            self._fail("missing_response_text")

    def _fail(self, code: str) -> None:
        """Raise an error preserving the complete raw output seen so far."""
        raise ProtocolParseError(code, self.raw_output, code)
