from typing import Any
from ..event_bus import EventBus
from ..interfaces import Manager
from ..events import (
    VADSpeechStart,
    VADSpeechEnd,
    TurnLLMAgentStartRequested,
    TurnLLMAgentStopRequested,
    TurnASRStartRequested,
    TurnASRPauseRequested,
    TurnASREndRequested,
    TurnDetectorStartGeneration,
    TurnDetectorStopSpeaking,
    ASRResultFinal,
    TTSPlaybackFinished,
)


class TurnTakingManager(Manager):
    def __init__(
        self, event_bus: EventBus, session_id: str, config: dict[str, Any] | None = None
    ):
        self.event_bus = event_bus
        self.session_id = session_id

    @Manager.event_handler(TurnDetectorStartGeneration)
    async def _on_turn_detector_start_generation(
        self, event: TurnDetectorStartGeneration
    ):
        # TODO: utilize event.semantic
        await self.event_bus.publish(TurnASREndRequested(session_id=self.session_id))

    @Manager.event_handler(TurnDetectorStopSpeaking)
    async def _on_turn_detector_stop_speaking(self, event: TurnDetectorStopSpeaking):
        # TODO: utilize event.semantic
        await self.event_bus.publish(
            TurnLLMAgentStopRequested(
                session_id=self.session_id,
            ),
            wait_for_completion=True,
        )

    @Manager.event_handler(VADSpeechStart)
    async def _on_vad_start(self, _event: VADSpeechStart):
        """VAD start: stop LLM and notify ASR to start."""
        await self.event_bus.publish(TurnASRStartRequested(session_id=self.session_id))

    @Manager.event_handler(VADSpeechEnd)
    async def _on_vad_end(self, _event: VADSpeechEnd):
        """VAD end: finalize the turn."""
        await self.event_bus.publish(TurnASRPauseRequested(session_id=self.session_id))

    @Manager.event_handler(ASRResultFinal)
    async def _on_asr_final(self, event: ASRResultFinal):
        """ASR final result triggers LLM generation."""
        await self.event_bus.publish(
            TurnLLMAgentStartRequested(
                session_id=self.session_id,
                text=event.text,
            )
        )

    @Manager.event_handler(TTSPlaybackFinished)
    async def _on_tts_playback_finished(self, _event: TTSPlaybackFinished) -> None:
        """Frontend playback finished - stop LLM agent to clean up."""
        # TODO: check whether this event handler is necessary
        await self.event_bus.publish(
            TurnLLMAgentStopRequested(
                session_id=self.session_id,
                reason="playback_finished",
            )
        )

    async def shutdown(self):
        return
