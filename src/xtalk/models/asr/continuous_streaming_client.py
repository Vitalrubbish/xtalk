"""HTTP transport for an append-only continuous ASR service."""
from __future__ import annotations

import base64
import threading
import requests

from .interfaces import ASR
from ..registry import model


@model
class ContinuousStreamingASRClient(ASR):
    """Forward PCM to one online session without revision processing.

    Parameters
    ----------
    base_url : str
        Independent HTTP ASR service.
    timeout : float
        Request timeout, including session warmup.
    chunk_ms : int
        Preferred input duration, 80 ms by default.
    """

    continuous_audio = True

    def __init__(self, base_url: str = "http://127.0.0.1:8005",
                 timeout: float = 120, chunk_ms: int = 80):
        if chunk_ms <= 0:
            raise ValueError("chunk_ms must be positive")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.chunk_ms = chunk_ms
        self.session = requests.Session()
        self._session_id = None
        self._request_lock = threading.RLock()

    def stream_chunk_bytes_hint(self) -> int:
        """Return the preferred PCM16 byte count.

        Returns
        -------
        int
            Bytes at 16 kHz mono.
        """
        return 32 * self.chunk_ms

    def _request(self, audio: bytes, *, pause: bool = False, end: bool = False) -> str:
        """Append audio once and read online cumulative text."""
        with self._request_lock:
            if self._session_id is None:
                response = self.session.post(self.base_url + "/v1/session", timeout=self.timeout)
                response.raise_for_status()
                self._session_id = response.json()["session_id"]
            response = self.session.post(self.base_url + "/v1/recognize", json={
                "session_id": self._session_id, "audio": base64.b64encode(audio).decode(),
                "is_final": pause, "end_stream": end}, timeout=self.timeout)
            response.raise_for_status()
            return self._text(response)

    @staticmethod
    def _text(response) -> str:
        """Validate online text without revision filtering."""
        text = response.json()["text"]
        if not isinstance(text, str):
            raise RuntimeError("Continuous ASR service must return text")
        return text

    def recognize_stream(self, audio: bytes, *, is_final: bool = False,
                         chat_history: str | None = None) -> str:
        """Forward input; temporary pauses do not finish the decoder.

        Parameters
        ----------
        audio : bytes
            Incremental PCM16 at 16 kHz. Empty non-final input reads existing output.
        is_final : bool
            Temporary pause hint.
        chat_history : str | None
            Unused by the online model.

        Returns
        -------
        str
            Online transcript without filtering.
        """
        with self._request_lock:
            if not audio and not is_final:
                if self._session_id is None:
                    return ""
                response = self.session.get(
                    self.base_url + f"/v1/session/{self._session_id}/result",
                    timeout=self.timeout)
                response.raise_for_status()
                return self._text(response)
            return self._request(audio, pause=is_final)

    def finish_stream(self, audio: bytes = b"") -> str:
        """Close actual input and drain online text.

        Parameters
        ----------
        audio : bytes
            Remaining PCM16 input.

        Returns
        -------
        str
            Final online transcript.
        """
        return self._request(audio, end=True)

    def recognize(self, audio: bytes) -> str:
        """Recognize complete audio in an independent temporary stream.

        Parameters
        ----------
        audio : bytes
            Complete PCM16 input.

        Returns
        -------
        str
            Online transcript after draining.
        """
        client = self.clone()
        try:
            return client.finish_stream(audio)
        finally:
            client.close()

    def reset(self) -> None:
        """Release the decoder and its online cache."""
        with self._request_lock:
            if self._session_id is not None:
                response = self.session.delete(self.base_url + "/v1/session/" + self._session_id,
                                               timeout=self.timeout)
                response.raise_for_status()
                self._session_id = None

    def clone(self) -> "ContinuousStreamingASRClient":
        """Create an adapter with independent session state.

        Returns
        -------
        ContinuousStreamingASRClient
            Independent adapter.
        """
        return ContinuousStreamingASRClient(self.base_url, self.timeout, self.chunk_ms)

    def close(self) -> None:
        """Release model and HTTP resources."""
        with self._request_lock:
            try:
                self.reset()
            finally:
                self.session.close()
