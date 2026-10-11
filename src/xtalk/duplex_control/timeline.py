"""Record session events on one monotonic DuplexCascade timeline."""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TextIO

from xtalk.serving.event_bus import EventBus
from xtalk.serving.events import (
    ASRResultFinal,
    ASRResultPartial,
    DuplexProtocolError,
    DuplexProtocolParsed,
    Event,
    LLMAgentResponseFinish,
    LLMAgentResponseUpdate,
    LLMFirstChunk,
    LLMFirstSentence,
    ConsumeLLMAgentGenerationRequested,
    TurnTTSDeliveryStartRequested,
    TurnTTSFlushRequested,
    TurnTTSStopRequested,
    TurnTTSTextAppendRequested,
    ResponseFinish,
    ResponseUpdate,
    TTSChunkReady,
    TTSFinished,
    TTSPlaybackFinished,
    TTSPlaybackStopped,
    TTSResponseClosed,
    TTSStarted,
    TTSStopped,
    TurnLLMAgentStopRequested,
    TurnTTSStartRequested,
)
from xtalk.serving.interfaces import Manager


@dataclass(frozen=True)
class TimelineRecord:
    """One event snapshot with original identifiers and event timestamps.

    Empty identifiers mean the publishing component has not assigned them.
    The record never guesses a response from adjacent events.
    """

    sequence: int
    recorded_monotonic: float
    event_type: str
    timestamp: float
    monotonic_timestamp: float
    session_id: str
    turn_id: int | None
    segment_id: int | None
    prefix_version: int | None
    request_id: str
    response_id: str
    state_token: str
    reason: str
    text: str
    raw_output: str
    error_code: str

    @classmethod
    def from_event(cls, event: Event, sequence: int = 0) -> TimelineRecord:
        """Take a serialization-safe snapshot of one published event.

        Parameters
        ----------
        event : Event
            Event published by the session event bus.
        sequence : int, optional
            Session-local order assigned by the recorder.

        Returns
        -------
        TimelineRecord
            Immutable snapshot without audio bytes or model objects.
        """

        payload = vars(event)
        return cls(
            sequence=sequence,
            recorded_monotonic=time.monotonic(),
            event_type=event.event_type,
            timestamp=event.timestamp,
            monotonic_timestamp=event.monotonic_timestamp,
            session_id=event.session_id,
            turn_id=payload.get("turn_id", None),
            segment_id=payload.get("segment_id", None),
            prefix_version=payload.get("prefix_version", None),
            request_id=payload.get("request_id", ""),
            response_id=payload.get("response_id", "") or "",
            state_token=payload.get("state_token", ""),
            reason=payload.get("reason", ""),
            text=payload.get("response_text", payload.get("text", "")),
            raw_output=payload.get("raw_output", ""),
            error_code=payload.get("error_code", ""),
        )


class DuplexTimelineRecorder(Manager):
    """Observe ASR, protocol, generation, and playback events for a session.

    Parameters
    ----------
    event_bus : EventBus
        Session event bus whose events are observed.
    session_id : str
        Session identifier.
    config : dict[str, Any] | None, optional
        Service configuration. The output directory defaults to a
        duplex_timeline subdirectory of data_dir.
    """

    def __init__(
        self,
        event_bus: EventBus,
        session_id: str,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.event_bus = event_bus
        self.session_id = session_id
        self.config = config or {}
        self._sequence = 0
        self._closed = False
        self.records: deque[TimelineRecord] = deque(
            maxlen=max(1, int(self.config.get("duplex_timeline_history", 1000)))
        )
        directory = Path(
            self.config.get("duplex_timeline_dir")
            or Path(self.config.get("data_dir", "data")) / "duplex_timeline"
        )
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{session_id}.jsonl"
        self._output: TextIO = self.path.open("a", encoding="utf-8")

    @Manager.event_handler(ASRResultPartial, priority=-200)
    @Manager.event_handler(ASRResultFinal, priority=-200)
    @Manager.event_handler(DuplexProtocolParsed, priority=-200)
    @Manager.event_handler(DuplexProtocolError, priority=-200)
    @Manager.event_handler(ConsumeLLMAgentGenerationRequested, priority=-200)
    @Manager.event_handler(LLMFirstSentence, priority=-200)
    @Manager.event_handler(TurnTTSDeliveryStartRequested, priority=-200)
    @Manager.event_handler(TurnTTSFlushRequested, priority=-200)
    @Manager.event_handler(TurnTTSStopRequested, priority=-200)
    @Manager.event_handler(TurnTTSTextAppendRequested, priority=-200)
    @Manager.event_handler(LLMFirstChunk, priority=-200)
    @Manager.event_handler(LLMAgentResponseUpdate, priority=-200)
    @Manager.event_handler(LLMAgentResponseFinish, priority=-200)
    @Manager.event_handler(TurnTTSStartRequested, priority=-200)
    @Manager.event_handler(TTSChunkReady, priority=-200)
    @Manager.event_handler(TTSStarted, priority=-200)
    @Manager.event_handler(TTSStopped, priority=-200)
    @Manager.event_handler(TTSFinished, priority=-200)
    @Manager.event_handler(TTSPlaybackStopped, priority=-200)
    @Manager.event_handler(TTSPlaybackFinished, priority=-200)
    @Manager.event_handler(ResponseUpdate, priority=-200)
    @Manager.event_handler(ResponseFinish, priority=-200)
    @Manager.event_handler(TTSResponseClosed, priority=-200)
    @Manager.event_handler(TurnLLMAgentStopRequested, priority=-200)
    async def _record_event(self, event: Event) -> None:
        """Append one structured event without changing its control flow."""

        if self._closed or event.session_id != self.session_id:
            return
        self._sequence += 1
        record = TimelineRecord.from_event(event, self._sequence)
        self.records.append(record)
        self._output.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        self._output.flush()

    async def shutdown(self) -> None:
        """Flush and close this session's JSONL timeline."""

        if self._closed:
            return
        self._closed = True
        for _, handlers in self.__event_handlers_meta__:
            for handler in handlers:
                self.event_bus.unsubscribe(handler["event_type"], self._record_event)
        self._output.close()
