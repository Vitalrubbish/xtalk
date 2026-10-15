"""Regression tests for ASR turn finalization."""

from __future__ import annotations

import asyncio
import unittest

from xtalk.models import ASR, VAD, Models, SpeakerDiarization
from xtalk.serving.event_bus import EventBus
from xtalk.duplex_control.micro_turn import MicroTurnAssembler
from xtalk.serving.event_bus import EventDispatchMode
from xtalk.serving.events import (
    ASRGateState,
    ASRResultFinal,
    ASRResultPartial,
    AudioFrameReceived,
    EnhancedAudioFrameReceived,
    LLMAgentLoop,
    VADSpeechEnd,
    VADSpeechStart,
)
from xtalk.serving.modules.vad_manager import VADManager
from xtalk.serving.modules.asr_manager import ASRManager, AudioConsumer


class ASRManagerAudioSourceTests(unittest.TestCase):
    """Verify ASR consumes the original microphone audio stream."""

    def test_audio_handler_subscribes_to_raw_frames(self) -> None:
        """Subscribe the ASR audio handler only to raw audio frames."""

        event_types = {
            metadata["event_type"]
            for method_name, handlers in ASRManager.__event_handlers_meta__
            if method_name == "_handle_audio_frame"
            for metadata in handlers
        }

        self.assertEqual(event_types, {AudioFrameReceived})

    def test_asr_events_default_to_unchecked_gate_state(self) -> None:
        """Leave existing ASR events unaccepted until a future gate runs."""

        partial = ASRResultPartial(session_id="session")
        final = ASRResultFinal(session_id="session")

        self.assertIs(partial.gate_state, ASRGateState.UNCHECKED)
        self.assertIs(final.gate_state, ASRGateState.UNCHECKED)


class _BlankFinalASR(ASR):
    """Return a useful partial transcript followed by a blank final result."""

    PARTIAL_TEXT = "已经识别出的文本"

    def recognize(self, audio: bytes) -> str:
        """Return an empty one-shot recognition result."""

        del audio
        return ""

    def recognize_stream(
        self,
        audio: bytes,
        *,
        is_final: bool = False,
        chat_history: str | None = None,
    ) -> str:
        """Return a non-empty partial and whitespace for the final flush."""

        del audio
        del chat_history
        return "   " if is_final else self.PARTIAL_TEXT

    def reset(self) -> None:
        """Reset the stateless test recognizer."""

        return None

    def clone(self) -> "_BlankFinalASR":
        """Return another stateless test recognizer."""

        return _BlankFinalASR()


class _BlockingASR(ASR):
    """Hold a streaming recognition result until the test releases it."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    def recognize(self, audio: bytes) -> str:
        """Return a fixed one-shot recognition result."""

        del audio
        return "stale"

    async def async_recognize_stream(
        self,
        audio: bytes,
        *,
        is_final: bool = False,
        chat_history: str | None = None,
    ) -> str:
        """Wait before returning a result from the superseded audio turn."""

        del audio
        del is_final
        del chat_history
        self.started.set()
        await self.release.wait()
        return "stale"

    def reset(self) -> None:
        """Reset the stateless test recognizer."""

        return None

    def clone(self) -> "_BlockingASR":
        """Return another independently controlled recognizer."""

        return _BlockingASR()


class _RecordingASR(ASR):
    """Record every streaming call and return a growing transcript."""

    def __init__(self) -> None:
        self.calls: list[bool] = []
        self.text = ""
        self.called = asyncio.Event()

    def recognize(self, audio: bytes) -> str:
        """Return the current transcript."""

        del audio
        return self.text

    async def async_recognize_stream(
        self,
        audio: bytes,
        *,
        is_final: bool = False,
        chat_history: str | None = None,
    ) -> str:
        """Grow the transcript and record the boundary flag of this call."""

        del audio
        del chat_history
        self.calls.append(is_final)
        self.text = f"{self.text} w{len(self.calls)}".strip()
        self.called.set()
        return self.text

    def reset(self) -> None:
        """Reset the stateless test recognizer."""

        self.text = ""
        return None

    def clone(self) -> "_RecordingASR":
        """Return an independent recognizer."""

        return _RecordingASR()


class _ScriptedVAD(VAD):
    """Report speech or silence on demand, one frame at a time."""

    def __init__(self) -> None:
        self.speaking = True

    def is_speech(self, frame: bytes) -> bool:
        """Return the scripted state for one frame."""

        del frame
        return self.speaking

    async def async_is_speech(self, frame: bytes) -> bool:
        """Return the scripted state for one frame."""

        del frame
        return self.speaking

    def reset(self) -> None:
        """Keep the scripted state; nothing to reset."""

        return None

    def clone(self) -> "_ScriptedVAD":
        """Return an independent recognizer with the same scripted state."""

        clone = _ScriptedVAD()
        clone.speaking = self.speaking
        return clone


class DuplexSegmentBoundaryTests(unittest.IsolatedAsyncioTestCase):
    """Duplex control must hand the decoder's held-back tail to the ASR."""

    async def test_speech_end_finalizes_the_asr_segment(self) -> None:
        """An acoustic speech end reaches the ASR client as ``is_final=True``.

        That flag is what makes the ASR service release the words its streaming
        decoder still holds back (its revision window). Duplex control replaces
        ``TurnTakingManager``, the released publisher of ``TurnASRPauseRequested``,
        so before this wiring the runtime only ever saw the transcript minus that
        window.
        """

        event_bus = EventBus(enable_history=True)
        asr = _RecordingASR()
        assembler = MicroTurnAssembler(event_bus, "session", {"duplex_auto_tick": False})
        self.addAsyncCleanup(assembler.shutdown)
        manager = ASRManager(event_bus, "session", Models({ASR: asr}))
        self.addAsyncCleanup(manager.shutdown)

        await event_bus.publish(LLMAgentLoop(session_id="session"),
                                mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        await event_bus.publish(
            AudioFrameReceived(session_id="session", audio_data=b"\x00\x00" * 160),
            mode=EventDispatchMode.WAIT_UNTIL_COMPLETE,
        )
        await asyncio.wait_for(asr.called.wait(), 1.0)
        self.assertEqual(asr.calls, [False])

        asr.called.clear()
        await event_bus.publish(VADSpeechEnd(session_id="session", origin="server"),
                                mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        await asyncio.wait_for(asr.called.wait(), 1.0)
        self.assertEqual(asr.calls, [False, True])
        pauses = [
            event for event in event_bus.get_history()
            if isinstance(event, ASRResultPartial) and event.speech_pause
        ]
        self.assertEqual(len(pauses), 1)

    async def test_backend_vad_silence_releases_the_segment(self) -> None:
        """Acoustic silence, not the end of the audio stream, must release the tail.

        The regression this guards: without a backend VAD, ``VADManager`` disables
        itself, the only ``VADSpeechEnd`` comes from the input gateway at the stream
        boundary, and an input file that reserves trailing silence for the answer
        keeps the ASR tail (and the answer) until the file ends. The window is
        ``vad_redemption_ms``, configured to 600 ms, the ASR chunk size.
        """

        event_bus = EventBus(enable_history=True)
        asr = _RecordingASR()
        vad = _ScriptedVAD()
        assembler = MicroTurnAssembler(event_bus, "session", {"duplex_auto_tick": False})
        self.addAsyncCleanup(assembler.shutdown)
        manager = ASRManager(event_bus, "session", Models({ASR: asr}))
        self.addAsyncCleanup(manager.shutdown)
        vad_manager = VADManager(event_bus, "session", Models({VAD: vad}),
                                 {"vad_redemption_ms": 600})
        self.addAsyncCleanup(vad_manager.shutdown)

        async def feed(count: int) -> None:
            """Publish ``count`` 512-sample audio frames through the enhancer path."""

            for _ in range(count):
                await event_bus.publish(
                    EnhancedAudioFrameReceived(
                        session_id="session", audio_data=b"\x00\x00" * 512,
                        sample_rate=16000),
                    mode=EventDispatchMode.WAIT_UNTIL_COMPLETE,
                )

        def events(cls) -> list:
            """Return recorded events of one type."""

            return [event for event in event_bus.get_history() if isinstance(event, cls)]

        await event_bus.publish(LLMAgentLoop(session_id="session"),
                                mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        await event_bus.publish(
            AudioFrameReceived(session_id="session", audio_data=b"\x00\x00" * 512),
            mode=EventDispatchMode.WAIT_UNTIL_COMPLETE,
        )
        await asyncio.wait_for(asr.called.wait(), 1.0)
        self.assertEqual(asr.calls, [False])

        # Eight speech frames (256 ms) open the segment; fifteen silent frames
        # (480 ms) are still inside the 600 ms redemption window.
        asr.called.clear()
        await feed(8)
        vad.speaking = False
        await feed(15)
        self.assertEqual(len(events(VADSpeechStart)), 1)
        self.assertEqual(len(events(VADSpeechEnd)), 0)
        self.assertNotIn(True, asr.calls)

        # Five more silent frames cross the window and release everything at once.
        await feed(5)
        await asyncio.wait_for(asr.called.wait(), 1.0)
        self.assertIn(True, asr.calls)
        self.assertTrue(asr.calls[-1])
        self.assertEqual(len(events(VADSpeechEnd)), 1)


class ASRFinalizationTests(unittest.IsolatedAsyncioTestCase):
    """Verify that finalization cannot discard a useful partial transcript."""

    async def test_history_gate_requires_a_diarization_model(self) -> None:
        """Keep the original background ASR dispatch when MTD is absent."""

        without_diarization = AudioConsumer(
            event_bus=EventBus(),
            session_id="without-diarization",
            models=Models({ASR: _BlankFinalASR()}),
        )
        self.addAsyncCleanup(without_diarization.shutdown)
        with_diarization = AudioConsumer(
            event_bus=EventBus(),
            session_id="with-diarization",
            models=Models(
                {
                    ASR: _BlankFinalASR(),
                    SpeakerDiarization: object(),
                }
            ),
        )
        self.addAsyncCleanup(with_diarization.shutdown)

        self.assertFalse(without_diarization._speaker_history_gate_enabled)
        self.assertTrue(with_diarization._speaker_history_gate_enabled)

    async def test_blank_final_uses_cached_partial_for_final_event(self) -> None:
        """Publish the cached partial when the final ASR flush is blank."""

        event_bus = EventBus(enable_history=True)
        consumer = AudioConsumer(
            event_bus=event_bus,
            session_id="session",
            models=Models({ASR: _BlankFinalASR()}),
        )
        self.addAsyncCleanup(consumer.shutdown)

        await consumer._recognize_and_publish(b"partial-audio")
        await consumer._recognize_and_publish(
            b"",
            is_asr_end=True,
            is_final_chunk=True,
        )

        events = event_bus.get_history()
        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[0], ASRResultPartial)
        self.assertIsInstance(events[1], ASRResultFinal)
        self.assertEqual(events[0].text, _BlankFinalASR.PARTIAL_TEXT)
        self.assertEqual(events[1].text, _BlankFinalASR.PARTIAL_TEXT)

    async def test_abort_drops_in_flight_recognition_result(self) -> None:
        """Do not publish stale speech text after a text turn aborts audio."""

        event_bus = EventBus(enable_history=True)
        asr = _BlockingASR()
        consumer = AudioConsumer(
            event_bus=event_bus,
            session_id="session",
            models=Models({ASR: asr}),
        )
        self.addAsyncCleanup(consumer.shutdown)

        await asyncio.sleep(0)
        await consumer.start()
        end_task = asyncio.create_task(consumer.end())
        await asyncio.wait_for(asr.started.wait(), timeout=1.0)

        abort_task = asyncio.create_task(consumer.abort())
        await asyncio.sleep(0)
        self.assertGreaterEqual(consumer._recognition_generation, 1)
        asr.release.set()
        await asyncio.wait_for(
            asyncio.gather(end_task, abort_task),
            timeout=1.0,
        )

        self.assertEqual(event_bus.get_history(), [])


if __name__ == "__main__":
    unittest.main()
