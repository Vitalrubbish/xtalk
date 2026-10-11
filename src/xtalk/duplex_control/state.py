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
