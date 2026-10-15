"""Contract tests for the append-only X2 ASR adapter."""

from __future__ import annotations

import asyncio
import unittest

from xtalk.models.asr.x2_streaming_client import X2StreamingClient
from xtalk.models import ASR, Models
from xtalk.serving.event_bus import EventBus
from xtalk.serving.modules.asr_manager import AudioConsumer


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

    def post(self, url, *, json=None, timeout=None):
        """Create a session or return a transcript."""
        del timeout
        if url.endswith("/v1/session"):
            self.n += 1
            return _Response({"session_id": f"s{self.n}"})
        self.calls.append(json)
        return _Response({"text": "rewritten but accepted"})

    def delete(self, url, *, timeout=None):
        """Acknowledge decoder release."""
        del url, timeout
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


if __name__ == "__main__":
    unittest.main()
