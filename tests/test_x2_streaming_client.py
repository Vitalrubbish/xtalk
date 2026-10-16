"""Contract tests for the append-only X2 ASR adapter."""

from __future__ import annotations

import asyncio
import base64
import threading
import unittest

from xtalk.duplex_control.micro_turn import MicroTurnAssembler
from xtalk.duplex_control.model_client import GenerationEnd
from xtalk.duplex_control.runtime_adapter import DuplexRuntimeAdapter
from xtalk.models.asr.x2_streaming_client import X2StreamingClient
from xtalk.models import ASR, Models
from xtalk.serving.event_bus import EventBus, EventDispatchMode
from xtalk.serving.events import ASRResultPartial, DuplexMicroTurnReady, LLMAgentLoop
from xtalk.serving.modules.asr_manager import ASRManager, AudioConsumer


class _Response:
    """Minimal HTTP response for adapter tests."""

    def __init__(self, payload):
        """Keep one JSON payload."""
        self.payload = payload

    def raise_for_status(self):
        """Represent a successful request."""
        return None

    def json(self):
        """Return the payload."""
        return self.payload


class _HTTP:
    """Capture incremental requests without a network service."""

    def __init__(self):
        """Initialize captured requests."""
        self.calls = []
        self.n = 0
        self.text = "rewritten but accepted"
        self.reads = []
        self.deleted = []
        self.post_returned = threading.Event()
        self.read_started = threading.Event()
        self.release_read = None

    def post(self, url, *, json=None, timeout=None):
        """Create a session or return a transcript."""
        del timeout
        if url.endswith("/v1/session"):
            self.n += 1
            return _Response({"session_id": f"s{self.n}"})
        self.calls.append(json)
        response = _Response({"text": self.text})
        self.post_returned.set()
        return response

    def get(self, url, *, timeout=None):
        """Read output, optionally holding the request across cancellation."""
        del timeout
        self.reads.append(url)
        self.read_started.set()
        if self.release_read is not None and not self.release_read.wait(2):
            raise RuntimeError("test read was not released")
        return _Response({"text": self.text})

    def delete(self, url, *, timeout=None):
        """Acknowledge decoder release."""
        del timeout
        self.deleted.append(url)
        return _Response({"ok": True})

    def close(self):
        """Release the fake connection pool."""
        return None


class X2StreamingClientTests(unittest.TestCase):
    """Protect native online request semantics."""

    def test_pause_hint_is_not_end_stream(self):
        """A pause preserves the stream; actual EOF closes it."""
        http = _HTTP()
        client = X2StreamingClient(chunk_ms=80)
        client.session = http
        self.assertTrue(client.continuous_audio)
        client.recognize_stream(b"\x00\x00", is_final=True)
        client.finish_stream()
        self.assertTrue(http.calls[0]["is_final"])
        self.assertFalse(http.calls[0]["end_stream"])
        self.assertTrue(http.calls[1]["end_stream"])
        self.assertEqual(client.stream_chunk_bytes_hint(), 2560)

    def test_online_text_is_returned_without_prefix_filter(self):
        """The adapter applies no Qwen revision policy."""
        http = _HTTP()
        client = X2StreamingClient()
        client.session = http
        self.assertEqual(client.recognize_stream(b"x"), "rewritten but accepted")

    def test_empty_read_never_allocates_or_finalizes_input(self):
        """Only an existing session is queried, without posting audio or EOF."""
        http = _HTTP()
        client = X2StreamingClient()
        client.session = http
        self.assertEqual(client.recognize_stream(b""), "")
        self.assertEqual(http.n, 0)
        self.assertFalse(http.reads)
        client.recognize_stream(b"\x00\x00")
        http.text = "late result"
        self.assertEqual(client.recognize_stream(b""), "late result")
        self.assertEqual(len(http.calls), 1)
        self.assertEqual(http.reads, [client.base_url + '/v1/session/s1/result'])
        self.assertFalse(http.calls[0]['end_stream'])
        client.reset()
        self.assertEqual(client.recognize_stream(b""), "")
        self.assertEqual(http.n, 1)


class ContinuousLifecycleTests(unittest.IsolatedAsyncioTestCase):
    """Exercise the real consumer across pause, EOF and shutdown."""

    async def test_pause_keeps_audio_flowing_and_end_drains(self):
        """Silence remains input and only actual EOF invokes finish_stream."""
        http = _HTTP()
        client = X2StreamingClient()
        client.session = http
        consumer = AudioConsumer(EventBus(), "s", Models({ASR: client}))
        try:
            await consumer.start()
            await consumer.accept_audio_frame(b"\x00\x00" * 1280)
            for _ in range(100):
                if http.calls:
                    break
                await asyncio.sleep(0.001)
            await consumer.pause()
            self.assertTrue(consumer._consumer_running())
            await consumer.accept_audio_frame(b"\x00\x00" * 1280)
            for _ in range(100):
                if len(http.calls) >= 2:
                    break
                await asyncio.sleep(0.001)
            self.assertEqual(len(http.calls), 2)
            self.assertFalse(any(c["end_stream"] for c in http.calls))
            await consumer.end()
            self.assertTrue(http.calls[-1]["end_stream"])
            self.assertIsNone(client._session_id)
        finally:
            await consumer.shutdown()


class _WaitingModel:
    """Capture actual adapter inputs and return the official waiting marker."""

    def __init__(self):
        """Initialize captured inference histories."""
        self.prompts = []

    async def stream(self, history):
        """Return one valid control-only system micro-turn."""
        self.prompts.append(history)
        yield '<|user is talking|><|im_end|>'
        yield GenerationEnd('stop', (151647, 151645))


class MicroTurnReadTests(unittest.IsolatedAsyncioTestCase):
    """Exercise delayed result delivery through the real micro-turn and LLM path."""

    async def asyncSetUp(self):
        """Build real managers around a controlled X2 HTTP adapter."""
        self.bus = EventBus(enable_history=True)
        self.addAsyncCleanup(self.bus.shutdown)
        self.http = _HTTP()
        self.http.text = ''
        self.client = X2StreamingClient()
        self.client.session = self.http
        self.manager = ASRManager(self.bus, 's', Models({ASR: self.client}))
        self.addAsyncCleanup(self.manager.shutdown)
        self.assembler = MicroTurnAssembler(self.bus, 's', {'duplex_auto_tick': False})
        self.addAsyncCleanup(self.assembler.shutdown)
        self.model = _WaitingModel()
        self.adapter = DuplexRuntimeAdapter(self.bus, 's', {'duplex_model_client': self.model})
        self.addAsyncCleanup(self.adapter.shutdown)

    async def start_session(self):
        """Start the existing continuous audio lifecycle."""
        await self.bus.publish(LLMAgentLoop(session_id='s'),
                               mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)

    async def send_audio(self, audio=None):
        """Submit one chunk and await its initial response, without another input."""
        audio = b'\x00\x00' * 1280 if audio is None else audio
        self.http.post_returned.clear()
        await self.manager._audio_consumer.accept_audio_frame(audio)
        self.assertTrue(await asyncio.to_thread(self.http.post_returned.wait, 1))

    async def test_each_tick_reads_latest_delta_without_more_audio(self):
        """New text enters the same tick; unchanged text becomes an empty user turn."""
        await self.start_session()
        first = await self.assembler.flush()
        self.assertEqual(first.delta_text, '')
        self.assertEqual(self.http.n, 0)
        await self.send_audio()
        self.http.text = 'how can'
        self.assertEqual((await self.assembler.flush()).delta_text, 'how can')
        self.http.text = 'how can i improve'
        await asyncio.sleep(0.1)
        self.assertEqual(len(self.http.reads), 1)
        self.assertEqual((await self.assembler.flush()).delta_text, ' i improve')
        self.assertEqual((await self.assembler.flush()).delta_text, '')
        self.http.text = 'how can i improve my sleep'
        self.assertEqual((await self.assembler.flush()).delta_text, ' my sleep')
        users = [item['text'] for item in self.adapter.history if item['role'] == 'user']
        self.assertEqual(users, ['', 'how can', ' i improve', '', ' my sleep'])
        self.assertEqual(len(self.http.reads), 4)
        self.assertEqual(len(self.http.calls), 1)
        self.assertFalse(self.http.calls[0]['end_stream'])
        partials = self.bus.get_history(event_type=ASRResultPartial.TYPE)
        self.assertEqual([e.text for e in partials],
                         ['how can', 'how can i improve', 'how can i improve my sleep'])

    async def test_clock_runs_before_first_asr_text(self):
        """Session startup creates no-voice ticks without waiting for ASR callbacks."""
        await self.assembler.shutdown()
        self.assembler = MicroTurnAssembler(
            self.bus, 's', {'duplex_micro_turn_seconds': 0.02})
        self.addAsyncCleanup(self.assembler.shutdown)
        ready = asyncio.Event()
        self.bus.subscribe(DuplexMicroTurnReady, lambda event: ready.set())
        await self.start_session()
        await asyncio.wait_for(ready.wait(), 1)
        self.assertEqual(self.model.prompts[0], [{'role': 'user', 'text': ''}])
        self.assertFalse(self.http.calls)
        self.assertEqual(self.http.n, 0)
        await self.send_audio()
        self.http.text = 'first late word'

        async def wait_for_text():
            """Observe a later scheduled tick picking up the first model emit."""
            while not any(item.get('text') == 'first late word' for item in self.adapter.history):
                await asyncio.sleep(0.001)

        await asyncio.wait_for(wait_for_text(), 1)

    async def test_read_preserves_partial_audio_chunk(self):
        """Taking a text snapshot neither submits nor discards queued short audio."""
        await self.start_session()
        await self.send_audio()
        short = b'\x01\x02' * 20
        await self.manager._audio_consumer.accept_audio_frame(short)
        self.http.text = 'late word'
        self.assertEqual((await self.assembler.flush()).delta_text, 'late word')
        self.assertEqual(len(self.http.calls), 1)
        remaining = b'\x03\x04' * 1260
        await self.send_audio(remaining)
        self.assertEqual(base64.b64decode(self.http.calls[-1]['audio']), short + remaining)
        self.assertFalse(any(call['end_stream'] for call in self.http.calls))

    async def test_abort_discards_an_inflight_read_and_never_reopens_it(self):
        """A late result cannot republish text from an aborted decoder session."""
        await self.start_session()
        await self.send_audio()
        self.http.release_read = threading.Event()
        self.addCleanup(self.http.release_read.set)
        tick = asyncio.create_task(self.assembler.flush())
        self.assertTrue(await asyncio.to_thread(self.http.read_started.wait, 1))
        abort = asyncio.create_task(self.manager._audio_consumer.abort())
        await asyncio.sleep(0)
        self.http.text = 'stale result'
        self.http.release_read.set()
        await asyncio.wait_for(asyncio.gather(tick, abort), 1)
        self.assertFalse(self.bus.get_history(event_type=ASRResultPartial.TYPE))
        self.assertIsNone(self.client._session_id)
        await self.assembler.flush()
        self.assertEqual(len(self.http.reads), 1)
        self.assertEqual(self.http.n, 1)

    async def test_cancelled_tick_and_shutdown_release_the_inflight_read(self):
        """Cancellation leaves no receiver task or late session recreation."""
        await self.start_session()
        await self.send_audio()
        self.http.release_read = threading.Event()
        self.addCleanup(self.http.release_read.set)
        tick = asyncio.create_task(self.assembler.flush())
        self.assertTrue(await asyncio.to_thread(self.http.read_started.wait, 1))
        tick.cancel()
        await asyncio.gather(tick, return_exceptions=True)
        shutdown = asyncio.create_task(self.manager.shutdown())
        await asyncio.sleep(0)
        self.http.text = 'stale result'
        self.http.release_read.set()
        await asyncio.wait_for(shutdown, 1)
        self.assertIsNone(self.client._session_id)
        self.assertTrue(self.manager._audio_consumer._audio_consumer_task.done())
        self.assertFalse(self.bus.get_history(event_type=ASRResultPartial.TYPE))
        self.assertEqual(self.client.recognize_stream(b''), '')
        self.assertEqual(self.http.n, 1)


if __name__ == "__main__":
    unittest.main()
