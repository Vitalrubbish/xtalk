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
        self._has_bytes_event = asyncio.Event()

    async def put(self, data: bytes) -> None:
        async with self._lock:
            self._buffer.extend(data)
            # Remove bytes from front if exceeding capacity
            if self._max_bytes > 0 and len(self._buffer) > self._max_bytes:
                excess = len(self._buffer) - self._max_bytes
                self._buffer = self._buffer[excess:]
            self._has_bytes_event.set()

    async def get(self, max_bytes: Optional[int] = None) -> bytes:
        # May return empty bytes
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
            self._has_bytes_event.clear()
            return result

    async def wait(self):
        """Wait until queue is non-empty"""
        await self._has_bytes_event.wait()

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
        self._asr_model.reset()
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
        # TODO: better turn behavior
        self._turn_id = 1

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
        # Stop consumer, do one recognition and publish
        await self._stop_consumer()
        audio = await self._audio_queue.get()
        # Sentence end but not end of recognition
        await self._recognize_and_publish(audio, is_asr_end=False, is_final_chunk=True)

    async def end(self):
        # Stop consumer, do one recognition, publish ASRResultFinal, clean up states (including reset ASR) and increment turn
        await self._stop_consumer()
        audio = await self._audio_queue.get()
        await self._recognize_and_publish(audio, is_asr_end=True, is_final_chunk=True)
        await self._reset_states()
        self._turn_id += 1

    async def _audio_consumer(self):
        while True:
            self._consumer_idle_event.set()
            if not self._consumer_running_event.is_set():
                await self._consumer_running_event.wait()
            self._consumer_idle_event.clear()
            # Publish audio on condition:
            # Await until queue is not empty
            await self._audio_queue.wait()
            # Accumulate to proper chunk bytes, send for recognition at least 1 bytes
            least_bytes_to_send = self._asr_model.stream_chunk_bytes_hint() or 1
            if len(self._audio_queue) < least_bytes_to_send:
                continue
            audio = await self._audio_queue.get()
            await self._recognize_and_publish(audio)

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
        recognized_text = self._recognized_text
        # Do not do recognition for empty audio
        if len(audio) > 0:
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
                    turn_id=self._turn_id,
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
                    turn_id=self._turn_id,
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
        self._asr_model.reset()


class ASRManager(Manager):
    def __init__(
        self,
        event_bus: EventBus,
        session_id: str,
        pipeline: Pipeline,
        config: dict[str, Any] | None = None,
    ):
        self._audio_consumer = AudioConsumer(event_bus, session_id, pipeline, config)

    @Manager.event_handler(EnhancedAudioFrameReceived)
    async def _handle_audio_frame(self, event: EnhancedAudioFrameReceived):
        audio_frame = event.audio_data
        await self._audio_consumer.accept_audio_frame(audio_frame)

    @Manager.event_handler(TurnASRStartRequested)
    async def _handle_asr_start(self, _):
        await self._audio_consumer.start()

    @Manager.event_handler(TurnASREndRequested)
    async def _handle_asr_end(self, _):
        await self._audio_consumer.end()

    @Manager.event_handler(TurnASRPauseRequested)
    async def _handle_asr_pause(self, _):
        await self._audio_consumer.pause()

    async def shutdown(self):
        return
