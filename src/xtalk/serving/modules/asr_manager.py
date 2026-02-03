from typing import Optional, Any
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
    ASRResultFinal,  # emit when turn about to move to next stage like text generation
)
from ...log_utils import logger


class ByteQueue:
    def __init__(self, max_bytes: int = 0):
        # max_byte==0 indicates no cap
        if max_bytes < 0:
            raise ValueError("max_bytes must be a non-negative int")
        self._max_bytes = max_bytes
        self._buffer = bytearray()
        self._lock = asyncio.Lock()

    async def put(self, data: bytes) -> None:
        async with self._lock:
            self._buffer.extend(data)
            # Remove bytes from front if exceeding capacity
            if self._max_bytes > 0 and len(self._buffer) > self._max_bytes:
                excess = len(self._buffer) - self._max_bytes
                self._buffer = self._buffer[excess:]

    async def get(self, max_bytes: Optional[int] = None) -> bytes:
        async with self._lock:
            if max_bytes is None:
                # Return all bytes
                result = bytes(self._buffer)
                self._buffer.clear()
            else:
                # Return at most max_bytes
                bytes_to_return = min(max_bytes, len(self._buffer))
                result = bytes(self._buffer[:bytes_to_return])
                self._buffer = self._buffer[bytes_to_return:]
            return result

    def __len__(self) -> int:
        return len(self._buffer)


class AudioConsumer:
    SAMPLE_RATE = 16000
    PRE_BUFFER_SECS = 1

    def __init__(
        self,
        event_bus: EventBus,
        session_id: str,
        pipeline: Pipeline,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._asr_model = pipeline.get_asr_model()
        self._session_id = session_id
        # Cache for recognition used in _recognize_and_publish
        self._recognized_text = ""
        # Assume PCM 16bit mono
        bytes_per_second = self.SAMPLE_RATE * 1 * (16 / 8)
        # Store audio before ASR starts; make sure ASR do not leave alone the first words
        self._pre_buffer = ByteQueue(self.PRE_BUFFER_SECS * bytes_per_second)
        # For ASR consumption
        self._audio_queue = ByteQueue()
        # Indicate whether consumer is running and _audio_queue should accept audio
        self._consumer_running_event = asyncio.Event()
        # Indicate whether consumer is idle; useful for waiting consumer to process its current loop after stop
        self._consumer_idle_event = asyncio.Event()
        self._consumer_idle_event.set()
        # Start audio consumer task immediately
        self._audio_consumer_task = asyncio.create_task(self._audio_consumer())

    async def accept_audio_frame(self, audio_frame: bytes):
        # Add audio_frame to pre-buffer if consumer not started; add audio_frame to recognition queue if started
        if not self._consumer_running():
            await self._pre_buffer.put(audio_frame)
        else:
            await self._audio_queue.put(audio_frame)

    async def start(self):
        # Pump pre-buffer to recognition queue; start consumer
        # Break start-once invariance warning
        if self._consumer_running():
            logger.warning(f"AudioConsumer started repeatedly")
        await self._audio_queue.put(await self._pre_buffer.get())
        self._start_consumer()

    async def pause(self):
        # Do one recognition; stop consumer
        audio = await self._audio_queue.get()
        await self._stop_consumer()
        # Sentence end but not end of recognition
        await self._recognize_and_publish(audio, is_asr_end=False, is_final_chunk=True)

    async def end(self):
        # Do one recognition, publish ASRResultFinal, and clean up states (including reset ASR)
        audio = await self._audio_queue.get()
        await self._stop_consumer()
        await self._recognize_and_publish(audio, is_asr_end=True, is_final_chunk=True)
        await self._reset_states()

    async def _audio_consumer(self):
        while True:
            self._consumer_idle_event.set()
            if not self._consumer_running_event.is_set():
                await self._consumer_running_event.wait()
            self._consumer_idle_event.clear()
            # TODO: publish audio on condition

    # Helpers
    def _consumer_running(self):
        return self._consumer_running_event.is_set()

    def _start_consumer(self):
        self._consumer_running_event.set()

    async def _stop_consumer(self):
        # Must stop after the current chunk is processed in consumer
        self._consumer_running_event.clear()
        await self._consumer_idle_event.wait()

    async def _recognize_and_publish(
        self, audio: bytes, is_asr_end: bool = False, is_final_chunk: bool = False
    ):
        # Do ASR recognition once and publish result ASRResultPartal/Final based on is_asr_end; if not final, may use cache to determine whether to publish
        if is_asr_end and not is_final_chunk:
            raise ValueError("ASR ends but chunk is not final chunk")
        recognized_text = await self._asr_model.async_recognize_stream(
            audio, is_final=is_final_chunk
        )
        if is_asr_end:
            self._recognized_text = recognized_text
            self._publish_event(
                ASRResultFinal(
                    session_id=self._session_id,
                    text=recognized_text,
                    display_text=recognized_text,
                )
            )
        else:
            if recognized_text == self._recognized_text:
                return
            self._recognized_text = recognized_text
            self._publish_event(
                ASRResultPartial(
                    session_id=self._session_id,
                    text=recognized_text,
                    display_text=recognized_text,
                )
            )

    async def _publish_event(self, event: BaseEvent):
        await self._event_bus.publish(event)

    async def _reset_states(self):
        self._recognized_text = ""
        await self._pre_buffer.get()
        await self._audio_queue.get()
        self._consumer_running_event.clear()
        self._consumer_idle_event.set()


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
