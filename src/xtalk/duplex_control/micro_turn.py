"""Aggregate cumulative ASR prefixes at serialized DuplexCascade boundaries."""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from xtalk.serving.event_bus import EventBus, EventDispatchMode
from xtalk.serving.events import (
    ASRResultFinal,
    ASRResultPartial,
    DuplexMicroTurnReady,
    LLMAgentLoop,
    TurnASRPauseRequested,
    TurnASRReadRequested,
    TurnASRStartRequested,
    VADSpeechEnd,
    VADSpeechStart,
)
from xtalk.serving.interfaces import Manager
from .state import PrefixSnapshot


class MicroTurnAssembler(Manager):
    """Buffer ASR updates independently of one serialized LLM clock.

    Parameters
    ----------
    event_bus : EventBus
        Session event bus.
    session_id : str
        Owning session.
    config : dict | None
        Positive duplex_micro_turn_seconds (default 0.6) and automatic clock flag.
    """

    def __init__(self, event_bus: EventBus, session_id: str, config: dict[str, Any] | None = None) -> None:
        self.event_bus = event_bus
        self.session_id = session_id
        self.config = config or {}
        self.interval = float(self.config.get("duplex_micro_turn_seconds", 0.6))
        if not math.isfinite(self.interval) or self.interval <= 0:
            raise ValueError("duplex_micro_turn_seconds must be positive and finite")
        self._prefix = ""
        self._sent_prefix = ""
        self._turn_id = 0
        self._segment_id = 0
        self._version = 0
        self._revision = "SILENCE"
        self._speech_state = "SPEAKING"
        self._received = time.monotonic()
        self._seen_text = False
        self._closed = False
        self._task: asyncio.Task | None = None
        self._flush_lock = asyncio.Lock()
        self._audio_started = False
        self._audio_paused = False

    @Manager.event_handler(LLMAgentLoop)
    async def _start_audio(self, event: LLMAgentLoop) -> None:
        """Start continuous ASR independently of VAD semantic decisions."""
        if event.session_id != self.session_id or self._audio_started or self._closed:
            return
        self._audio_started = True
        await self.event_bus.publish(TurnASRStartRequested(session_id=self.session_id),
                                     mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        if self._task is None and self.config.get("duplex_auto_tick", True):
            self._task = asyncio.create_task(self._clock())

    @Manager.event_handler(VADSpeechEnd)
    async def _pause_audio(self, event: VADSpeechEnd) -> None:
        """Release buffered decoder text only for ASR paths using acoustic VAD.

        Continuous X2 input ignores acoustic boundaries. Buffered ASR backends
        retain pause finalization without treating a pause as semantic handover.
        """
        if not self.config.get("acoustic_vad_enabled", True):
            return
        if event.session_id != self.session_id or self._closed or self._audio_paused:
            return
        if event.origin == "text" or not self._audio_started:
            return
        self._audio_paused = True
        await self.event_bus.publish(TurnASRPauseRequested(session_id=self.session_id))

    @Manager.event_handler(VADSpeechStart)
    async def _resume_audio(self, event: VADSpeechStart) -> None:
        """Resume the ASR consumer after a pause so no audio is dropped."""
        if not self.config.get("acoustic_vad_enabled", True):
            return
        if event.session_id != self.session_id or self._closed or not self._audio_paused:
            return
        self._audio_paused = False
        await self.event_bus.publish(TurnASRStartRequested(session_id=self.session_id))

    @Manager.event_handler(ASRResultPartial)
    @Manager.event_handler(ASRResultFinal)
    async def _accept_asr(self, event: ASRResultPartial | ASRResultFinal) -> None:
        """Replace only the visible prefix; events never trigger immediate LLM calls."""
        if event.session_id != self.session_id or self._closed:
            return
        final = isinstance(event, ASRResultFinal)
        state = "ENDED" if final else ("PAUSING" if event.speech_pause else "SPEAKING")
        new_scope = (event.turn_id, event.segment_id) != (self._turn_id, self._segment_id)
        if new_scope:
            self._prefix = ""
            self._sent_prefix = ""
            self._turn_id, self._segment_id = event.turn_id, event.segment_id
        if event.text == self._prefix and state == self._speech_state and not new_scope:
            return
        previous = self._prefix
        self._prefix = event.text
        self._received = event.monotonic_timestamp
        self._speech_state = state
        self._version += 1
        self._revision = "REWRITE" if not event.text.startswith(previous) else ("FINALIZE" if final else "APPEND")
        if event.text.strip():
            self._seen_text = True
            if self._task is None and self.config.get("duplex_auto_tick", True):
                self._task = asyncio.create_task(self._clock())

    async def flush(self) -> PrefixSnapshot | None:
        """Publish the latest input and wait for its system micro-turn to complete.

        Returns
        -------
        PrefixSnapshot | None
            Immutable input, or None before session input starts / after shutdown.
        """
        async with self._flush_lock:
            if self._closed or not (self._seen_text or self._audio_started):
                return None
            await self.event_bus.publish(TurnASRReadRequested(session_id=self.session_id),
                                         mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
            if self._closed:
                return None
            previous = self._sent_prefix
            rewritten = not self._prefix.startswith(previous)
            delta = self._prefix if rewritten else self._prefix[len(previous):]
            revision = "REWRITE" if rewritten else (self._revision if delta or self._revision == "FINALIZE" else "SILENCE")
            snapshot = PrefixSnapshot(
                session_id=self.session_id, turn_id=self._turn_id, segment_id=self._segment_id,
                prefix_version=self._version, text=self._prefix, previous_text=previous,
                delta_text=delta, revision_kind=revision, speech_state=self._speech_state,
                received_monotonic=self._received, request_id=uuid4().hex,
            )
            self._sent_prefix = self._prefix
            self._revision = "SILENCE"
            await self.event_bus.publish(DuplexMicroTurnReady(**asdict(snapshot)),
                                         mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
            return snapshot

    async def _clock(self) -> None:
        """Mirror the official tick schedule without a backlog of obsolete inputs."""
        next_tick = time.monotonic() + self.interval
        while not self._closed:
            await asyncio.sleep(max(0.001, next_tick - time.monotonic()))
            next_tick = max(time.monotonic(), next_tick + self.interval)
            await self.flush()

    async def shutdown(self) -> None:
        """Cancel the clock and any generation awaited by its current tick."""
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
