"""Validate native ASR generations at the explicit client boundary."""
import unittest
from xtalk.models.asr.nemotron_streaming_client import NemotronStreamingClient


class Response:
    """Expose a deterministic HTTP JSON result."""

    def __init__(self, text, generation='s', version=1):
        """Store a result for one decoder generation."""
        self.value = dict(text=text, generation=generation, session_id=generation, prefix_version=version)

    def json(self):
        """Return the stored result."""
        return self.value


class NemotronClientTests(unittest.TestCase):
    """Reject stream pollution and transcript rewrites instead of hiding them."""

    def test_generation_rewrite_and_version(self):
        """Append-only text and monotonic versions are required within one UUID."""
        client = NemotronStreamingClient()
        self.addCleanup(client.session.close)
        client._session_id = 's'
        self.assertEqual(client._text(Response('hel')), 'hel')
        self.assertEqual(client._text(Response('hello', version=2)), 'hello')
        for response in (Response('world',version=3), Response('hello',generation='old'), Response('hello',version=1)):
            with self.assertRaises(RuntimeError):
                client._text(response)

    def test_clone_is_explicit_and_independent(self):
        """Cloning preserves backend type and transport packet duration."""
        client = NemotronStreamingClient(chunk_ms=40)
        clone = client.clone()
        self.addCleanup(client.session.close)
        self.addCleanup(clone.session.close)
        self.assertIsInstance(clone, NemotronStreamingClient)
        self.assertIsNot(client.session, clone.session)
        self.assertEqual(clone.stream_chunk_bytes_hint(),1280)


if __name__ == '__main__':
    unittest.main()
