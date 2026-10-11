"""Contract tests for the local Qwen3-ASR HTTP adapter."""

from __future__ import annotations

import base64
import unittest
from unittest.mock import patch

import requests

from xtalk.models.asr.qwen3asr_client import Qwen3ASRClient


class _FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        """Match the requests API without failing."""

    def json(self) -> dict:
        """Return the configured JSON body."""

        return self._payload


class _FakeASRService:
    """Simulate the service with per-session cumulative transcripts."""

    def __init__(self) -> None:
        self._next_id = 0
        self.transcripts: dict[str, str] = {}
        self.deleted: list[str] = []
        self.recognize_calls: list[dict] = []

    def post(self, url: str, *, json: dict, timeout: float | None = None) -> _FakeResponse:
        """Answer session creation and recognition requests."""

        del timeout
        if url.endswith("/v1/session"):
            self._next_id += 1
            session_id = f"session-{self._next_id}"
            self.transcripts[session_id] = ""
            return _FakeResponse({"session_id": session_id})
        if url.endswith("/v1/recognize"):
            self.recognize_calls.append(dict(json))
            session_id = json["session_id"]
            audio = base64.b64decode(json["audio"])
            if audio:
                self.transcripts[session_id] = self.transcripts[session_id] + "x"
            return _FakeResponse({"text": self.transcripts[session_id]})
        raise AssertionError(f"unexpected POST {url}")

    def delete(self, url: str, *, timeout: float | None = None) -> _FakeResponse:
        """Release a session by id."""

        del timeout
        session_id = url.rsplit("/", 1)[-1]
        self.deleted.append(session_id)
        self.transcripts.pop(session_id, None)
        return _FakeResponse({"ok": True})

    def close(self) -> None:
        """Match the requests.Session API."""

    def mount(self, prefix, adapter) -> None:
        """Accept adapter registration for cloned transports."""


def _client_with(service: _FakeASRService, **kwargs) -> Qwen3ASRClient:
    """Build an adapter whose transport is the fake service."""

    client = Qwen3ASRClient(**kwargs)
    client.session = service
    return client


class Qwen3ASRClientTests(unittest.TestCase):
    """Verify byte input, cumulative text, and per-session isolation."""

    def test_stream_returns_cumulative_text_and_forwards_is_final(self) -> None:
        """Each call sends bytes and returns the cumulative transcript."""

        service = _FakeASRService()
        client = _client_with(service)

        self.assertEqual(client.recognize_stream(b"aa" b"bb"), "x")
        self.assertEqual(client.recognize_stream(b"cc"), "xx")

        first = service.recognize_calls[0]
        self.assertEqual(base64.b64decode(first["audio"]), b"aabb")
        self.assertFalse(first["is_final"])
        self.assertEqual(service.recognize_calls[1]["session_id"], first["session_id"])

    def test_clone_uses_independent_session(self) -> None:
        """Clones address different service sessions."""

        service = _FakeASRService()
        first = _client_with(service)
        with patch("xtalk.models.asr.qwen3asr_client.requests.Session", return_value=service):
            second = first.clone()

        self.assertEqual(first.recognize_stream(b"aa"), "x")
        self.assertEqual(second.recognize_stream(b"bb"), "x")
        self.assertNotEqual(
            service.recognize_calls[0]["session_id"],
            service.recognize_calls[1]["session_id"],
        )
        self.assertEqual(first.recognize_stream(b"cc"), "xx")
        self.assertEqual(second.recognize_stream(b"dd"), "xx")

    def test_empty_and_shortened_revisions_replace_cached_text(self) -> None:
        """A valid empty transcript clears stale recognized text."""
        client = _client_with(_FakeASRService())
        with patch.object(client, "_post_json", side_effect=[
            {"session_id": "test"}, {"text": "long prefix"},
            {"text": "short"}, {"text": ""},
        ]):
            self.assertEqual(client.recognize_stream(b"aa"), "long prefix")
            self.assertEqual(client.recognize_stream(b"bb"), "short")
            self.assertEqual(client.recognize_stream(b"cc"), "")
            self.assertEqual(client.recognize_stream(b""), "")

    def test_failed_or_invalid_response_does_not_replace_cache(self) -> None:
        """Transport failures and missing text remain visible to callers."""
        client = _client_with(_FakeASRService())
        self.assertEqual(client.recognize_stream(b"aa"), "x")
        with patch.object(client, "_post_json", side_effect=requests.HTTPError("failed")):
            with self.assertRaises(requests.HTTPError):
                client.recognize_stream(b"bb")
        for response in ({}, {"text": None}):
            with patch.object(client, "_post_json", return_value=response):
                with self.assertRaises(RuntimeError):
                    client.recognize_stream(b"cc")
        self.assertEqual(client.recognize_stream(b""), "x")

    def test_one_shot_calls_preserve_stream_and_release_temporary_sessions(self) -> None:
        """One-shot calls use fresh sessions without resetting the stream."""
        service = _FakeASRService()
        client = _client_with(service)
        self.assertEqual(client.recognize_stream(b"aa"), "x")
        stream_id = service.recognize_calls[0]["session_id"]
        with patch("xtalk.models.asr.qwen3asr_client.requests.Session", return_value=service):
            self.assertEqual(client.recognize(b"bb"), "x")
            self.assertEqual(client.recognize(b"cc"), "x")
        self.assertEqual(len(service.deleted), 2)
        self.assertNotIn(stream_id, service.deleted)
        self.assertEqual(client.recognize_stream(b"dd"), "xx")

    def test_one_shot_failure_releases_temporary_session(self) -> None:
        """An HTTP failure still closes the newly allocated session."""
        service = _FakeASRService()
        client = _client_with(service)
        original = service.post
        def failing_post(url, *, json, timeout=None):
            """Create a session but reject recognition."""
            if url.endswith("/v1/recognize"):
                raise requests.HTTPError("failed")
            return original(url, json=json, timeout=timeout)
        with patch("xtalk.models.asr.qwen3asr_client.requests.Session", return_value=service), patch.object(service, "post", side_effect=failing_post):
            with self.assertRaises(requests.HTTPError):
                client.recognize(b"aa")
        self.assertEqual(service.deleted, ["session-1"])

    def test_reset_releases_session_and_clears_text(self) -> None:
        """Reset deletes the session and the next call registers a new one."""

        service = _FakeASRService()
        client = _client_with(service)
        self.assertEqual(client.recognize_stream(b"aa"), "x")
        old_session = service.recognize_calls[0]["session_id"]

        client.reset()

        self.assertIn(old_session, service.deleted)
        self.assertEqual(client.recognize_stream(b"bb"), "x")
        self.assertNotEqual(service.recognize_calls[1]["session_id"], old_session)

    def test_temporary_boundary_keeps_session(self) -> None:
        """A final-flagged flush does not reset the session."""

        service = _FakeASRService()
        client = _client_with(service)
        self.assertEqual(client.recognize_stream(b"aa", is_final=True), "x")
        self.assertEqual(client.recognize_stream(b"bb"), "xx")

        self.assertEqual(service.recognize_calls[0]["is_final"], True)
        self.assertEqual(
            service.recognize_calls[0]["session_id"],
            service.recognize_calls[1]["session_id"],
        )
        self.assertEqual(service.deleted, [])

    def test_stream_chunk_bytes_hint_matches_chunk_ms(self) -> None:
        """The byte hint scales with the configured chunk duration."""

        client = _client_with(_FakeASRService(), chunk_ms=600)
        self.assertEqual(client.stream_chunk_bytes_hint(), 16000 * 2 * 600 // 1000)


if __name__ == "__main__":
    unittest.main()
