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
WIRE_IM_START = "<|im_start|>"
WIRE_CONTROLS = {
    "<|user is talking|>": ControlToken.USER_IS_SPEAKING,
    "<|user finish talking|>": ControlToken.USER_FINISH_SPEAKING,
    "<|user interruption|>": ControlToken.USER_IS_INTERRUPTING,
    "<|user backchannel|>": ControlToken.USER_BACKCHANNEL,
    "<|user is thinking|>": ControlToken.USER_IS_THINKING,
}
# Released markers that never become speech or a semantic decision.
_WIRE_SKIP = (WIRE_NO_VOICE, WIRE_IM_START)
_WIRE_TOKENS = tuple(sorted((WIRE_EOS, *_WIRE_SKIP, *WIRE_CONTROLS), key=len, reverse=True))
_INCOMPLETE = object()


@dataclass(frozen=True)
class WireControl:
    """One control token observed in the streamed assistant output.

    Parameters
    ----------
    control : ControlToken
        Semantic state selected by the official weights.
    wire_token : str
        Exact released spelling that produced the state.
    """

    control: ControlToken
    wire_token: str


@dataclass(frozen=True)
class WireText:
    """One plain-text fragment safe to forward to the existing TTS chain.

    Parameters
    ----------
    text : str
        Text between control tokens.
    wire_token : str
        Most recent control spelling, empty before the first control token.
    """

    text: str
    wire_token: str


class WireMicroTurnParser:
    """Tokenize streamed official-weight output into ordered control and text events.

    The official server reacts to every control token it decodes and forwards
    all remaining text to speech; it never validates message structure. This
    parser mirrors that behavior: repeated, adjacent or out-of-order control
    tokens are applied in arrival order and are never raised as errors.
    """

    def __init__(self) -> None:
        self.raw_output = ""
        self.text = ""
        self.control: ControlToken | None = None
        self.wire_token = ""
        self.ended = False
        self.finish_reason = "stop"
        self._pending = ""

    def feed(self, chunk: str) -> list[WireControl | WireText]:
        """Consume a raw fragment and return its ordered control and text events.

        Parameters
        ----------
        chunk : str
            Decoded model fragment with special tokens preserved.

        Returns
        -------
        list[WireControl | WireText]
            Newly completed control tokens and answer text, in arrival order.
        """

        self.raw_output += chunk
        self._pending += chunk
        events: list[WireControl | WireText] = []
        while self._pending and not self.ended:
            index = self._pending.find("<")
            if index < 0:
                self._emit_text(events, self._pending)
                self._pending = ""
                break
            if index > 0:
                self._emit_text(events, self._pending[:index])
                self._pending = self._pending[index:]
                continue
            match = self._match(self._pending)
            if match is _INCOMPLETE:
                break
            if match is None:
                # Not a released marker: official weights render it as plain text.
                end = self._pending.find(">")
                if end >= 0:
                    self._emit_text(events, self._pending[: end + 1])
                    self._pending = self._pending[end + 1 :]
                else:
                    self._emit_text(events, "<")
                    self._pending = self._pending[1:]
                continue
            self._pending = self._pending[len(match) :]
            if match in _WIRE_SKIP:
                continue
            if match == WIRE_EOS:
                self.ended = True
                break
            control = WIRE_CONTROLS[match]
            self.control = control
            self.wire_token = match
            events.append(WireControl(control, match))
        if self.ended:
            self._pending = ""
        return events

    def finish(self, finish_reason: str = "stop") -> None:
        """Record the service termination reason without rejecting the output.

        Parameters
        ----------
        finish_reason : str
            ``stop`` when the model emitted ``<|im_end|>``; ``length`` when the
            per-micro-turn token budget ended first. Both are valid endings.
        """

        self.finish_reason = finish_reason

    def _emit_text(self, events: list[WireControl | WireText], text: str) -> None:
        """Append answer text and expose it with the current control context."""
        self.text += text
        events.append(WireText(text, self.wire_token))

    @staticmethod
    def _match(pending: str) -> object:
        """Return a released marker, ``_INCOMPLETE``, or ``None`` for plain text."""
        for token in _WIRE_TOKENS:
            if pending.startswith(token):
                return token
        if any(token.startswith(pending) for token in _WIRE_TOKENS):
            return _INCOMPLETE
        return None
