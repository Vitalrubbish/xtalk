"""Immutable identifiers shared by DuplexCascade requests and observations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DuplexCorrelation:
    """Associate one micro-turn request with its optional response.

    Parameters
    ----------
    session_id : str
        Session that owns this micro-turn.
    turn_id : int | None
        Current user turn, if assigned.
    segment_id : int | None
        Current ASR segment, if assigned.
    prefix_version : int | None
        Visible prefix revision, if assigned.
    request_id : str
        Unique request identifier, if assigned.
    response_id : str
        Reserved response identifier, if assigned.
    """

    session_id: str
    turn_id: int | None = None
    segment_id: int | None = None
    prefix_version: int | None = None
    request_id: str = ""
    response_id: str = ""


@dataclass(frozen=True)
class PrefixSnapshot:
    """Preserve the visible cumulative prefix and its unsent delta.

    Parameters
    ----------
    session_id : str
        Owning session.
    turn_id, segment_id, prefix_version : int
        ASR scope and monotonic visible-prefix revision.
    text, previous_text, delta_text : str
        Current prefix, previous emitted prefix, and newly available input.
    revision_kind, speech_state : str
        Deterministic transport metadata; never a semantic turn decision.
    received_monotonic : float
        Timestamp of the latest contributing ASR event.
    request_id : str
        Unique micro-turn request.
    """

    session_id: str
    turn_id: int
    segment_id: int
    prefix_version: int
    text: str
    previous_text: str
    delta_text: str
    revision_kind: str
    speech_state: str
    received_monotonic: float
    request_id: str
