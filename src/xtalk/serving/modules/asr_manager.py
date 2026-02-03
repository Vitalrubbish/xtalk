from collections import deque
from typing import Deque, Optional, Any
import asyncio
from ..interfaces import Manager
from ..event_bus import EventBus
from ...pipelines import Pipeline
from ..events import (
    BaseEvent,
    EnhancedAudioFrameReceived,
    TurnASRStartRequested,
    TurnASREndRequested,
    TurnASRPauseRequested,
    ASRResultPartial,
    ASRResultFinal,  # emit when ASR recognition cache is to be cleared and turn move to generation stage
)


class ByteQueue(asyncio.Queue):
    def __init__(self, max_bytes: int):
        if max_bytes < 0:
            raise ValueError("max_bytes must be a non-negative int")
        super().__init__(maxsize=0)

    async def put(self, data: bytes) -> None:
        pass

    async def get(self, max_bytes: Optional[int] = None) -> bytes:
        pass


class AudioConsumer:
    SAMPLE_RATE = 16000

    def __init__(
        self,
        event_bus: EventBus,
        session_id: str,
        pipeline: Pipeline,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._asr_model = pipeline.get_asr_model()
        self.pre_buffer = asyncio.Queue()

    async def accept_audio_frame(self, audio_frame: bytes):
        # Add audio_frame to pre-buffer if not started; add audio_frame to recognition queue if started
        pass

    async def start(self):
        # Pump pre-buffer to recognition queue; start consumer
        pass

    async def pause(self):
        # Do one recognition; stop adding frames to recognition queue and stop consumer
        pass

    async def end(self):
        # Do one recognition, publish ASRResultFinal, and clean up states (including reset ASR)
        pass

    async def _publish_event(self, event: BaseEvent):
        await self._event_bus.publish(event)


class ASRManager(Manager):
    def __init__(
        self,
        event_bus: EventBus,
        session_id: str,
        pipeline: Pipeline,
        config: dict[str, Any] | None = None,
    ):
        self.event_bus = event_bus
        self.pipeline = pipeline

    @Manager.event_handler(EnhancedAudioFrameReceived)
    async def _handle_audio_frame(self):
        # TODO: constantly pad frames to prebuffer/ for recognition
        pass

    @Manager.event_handler(TurnASRStartRequested)
    async def _handle_asr_start(self):
        # TODO
        pass

    @Manager.event_handler(TurnASREndRequested)
    async def _handle_asr_end(self):
        # TODO: stop consumer
        pass

    @Manager.event_handler(TurnASRPauseRequested)
    async def _handle_asr_pause(self):
        # TODO
        pass
