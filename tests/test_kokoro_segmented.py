"""Exercise incremental segmentation and cancellation through a real HTTP boundary."""
import asyncio
import base64
import unittest

from aiohttp import web
from xtalk.models.tts.kokoro_segmented import KokoroSegmented


class KokoroSegmentedTests(unittest.IsolatedAsyncioTestCase):
    """Check deadlines, generation isolation and finish on the native TTS interface."""

    async def asyncSetUp(self):
        """Start a deterministic synthesis endpoint without model weights."""
        self.requests = []
        self.gate = asyncio.Event()
        self.gate.set()
        self.started = asyncio.Event()
        app = web.Application()
        app.router.add_post('/v1/synthesize', self.synthesize)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await self.site.start()
        port = self.site._server.sockets[0].getsockname()[1]
        self.client = KokoroSegmented(f'http://127.0.0.1:{port}', max_wait_ms=20)

    async def asyncTearDown(self):
        """Release clients and blocked service handlers."""
        self.gate.set()
        await self.client.cancel()
        await self.runner.cleanup()

    async def synthesize(self, request):
        """Echo generation identity with nonempty 48kHz PCM16."""
        data = await request.json()
        self.requests.append(data)
        self.started.set()
        await self.gate.wait()
        return web.json_response({**data, 'sample_rate': 48000, 'channels': 1,
                                  'format': 'pcm_s16le', 'pcm': base64.b64encode(b'\x01\x02'*960).decode()})

    async def test_timeout_submits_before_finish(self):
        """The first segment does not depend on the complete answer being available."""
        await self.client.start()
        await self.client.append_text('Could you confirm Tuesday')
        await asyncio.wait_for(self.started.wait(), 1)
        self.assertFalse(self.client._finalized)
        await self.client.append_text(' at 9:30?')
        await self.client.flush()
        result = b''.join([part async for part in self.client.audio_stream()])
        await self.client.stop()
        self.assertTrue(result)
        self.assertEqual(''.join(r['text'] for r in self.requests), 'Could you confirm Tuesday at 9:30?')

    async def test_cancel_drops_inflight_and_restarts(self):
        """Late old PCM cannot enter a new response generation."""
        self.gate.clear()
        await self.client.start()
        await self.client.append_text('This response is cancelled.')
        await asyncio.wait_for(self.started.wait(), 1)
        old = self.requests[0]['generation']
        await asyncio.wait_for(self.client.cancel(), 1)
        self.gate.set()
        await self.client.start()
        await self.client.append_text('New reply.')
        await self.client.flush()
        audio = [chunk async for chunk in self.client.audio_stream()]
        await self.client.stop()
        self.assertEqual(sum(map(len, audio)), 1920)
        self.assertNotEqual(self.requests[-1]['generation'], old)

    async def test_segments_respect_length_and_preserve_text(self):
        """Length bounds preserve date/time text and do not duplicate increments."""
        text = 'At 9:30 the value is 3.14. ' * 20
        result = await self.client.async_synthesize(text)
        self.assertTrue(result)
        self.assertTrue(all(len(row['text']) <= 160 for row in self.requests))
        self.assertEqual(''.join(row['text'] for row in self.requests), text)
        self.assertEqual([row['sequence'] for row in self.requests], list(range(len(self.requests))))

    async def test_flush_closes_input(self):
        """Finish rejects further increments while queued audio drains."""
        await self.client.start()
        await self.client.append_text('Yes.')
        await self.client.flush()
        with self.assertRaises(RuntimeError):
            await self.client.append_text('late')
        self.assertTrue([chunk async for chunk in self.client.audio_stream()])
        await self.client.stop()

    async def test_remaining_word_uses_its_actual_arrival(self):
        """A newer word fragment does not inherit an older word's expired budget."""
        self.client.max_wait_ms = 200
        await self.client.start()
        await self.client.append_text('please ')
        await asyncio.sleep(.1)
        await self.client.append_text('con')
        await asyncio.wait_for(self.started.wait(),1)
        await self.client.append_text('firm ')
        await self.client.flush()
        self.assertTrue([chunk async for chunk in self.client.audio_stream()])
        await self.client.stop()
        self.assertEqual([row['text'] for row in self.requests],['please ','confirm '])


if __name__ == '__main__':
    unittest.main()
