"""HTTP adapter for the local Qwen3-ASR streaming service.

The service keeps one streaming state per ``session_id``; this adapter only
addresses sessions and forwards 16 kHz mono PCM16 audio. It conforms to the
:class:`ASR` contract: byte input, cumulative text output, and independent
per-session state through :meth:`clone`.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..registry import model
from .interfaces import ASR

logger = logging.getLogger(__name__)


@model
class Qwen3ASRClient(ASR):
    """Streaming ASR adapter backed by a local Qwen3-ASR service.

    Parameters
    ----------
    base_url : str, optional
        Root URL of the ASR service, for example ``http://127.0.0.1:8005``.
    timeout : float, optional
        Per-request timeout in seconds.
    sample_rate : int, optional
        PCM sample rate; the service expects 16 kHz mono PCM16.
    chunk_ms : int, optional
        Preferred streaming chunk duration, used to size
        :meth:`stream_chunk_bytes_hint`.
    **kwargs : Any
        Extra fields forwarded to every ``/v1/recognize`` request.
    """

    TARGET_SAMPLE_RATE = 16000

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8005",
        timeout: float = 15.0,
        sample_rate: int = 16000,
        chunk_ms: int = 600,
        **kwargs: Any,
    ) -> None:
        if sample_rate != self.TARGET_SAMPLE_RATE:
            raise ValueError("Qwen3-ASR expects 16 kHz audio")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.chunk_ms = chunk_ms
        self.extra_params = kwargs
        self._session_id: str | None = None
        self._confirmed_text = ""

        self.session = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(
            pool_connections=8,
            pool_maxsize=32,
            max_retries=retry,
            pool_block=False,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def stream_chunk_bytes_hint(self) -> int | None:
        """Return the preferred chunk size in bytes for 16 kHz mono PCM16.

        Returns
        -------
        int
            ``sample_rate * 2 bytes * chunk_ms / 1000``.
        """
        return int(self.TARGET_SAMPLE_RATE * 2 * self.chunk_ms / 1000)

    def recognize(self, audio: bytes) -> str:
        """Recognize one complete audio buffer in a fresh turn.

        Parameters
        ----------
        audio : bytes
            PCM 16-bit mono 16 kHz audio bytes.

        Returns
        -------
        str
            Final cumulative transcript.
        """
        return self.recognize_stream(audio, is_final=True)

    def recognize_stream(
        self,
        audio: bytes,
        *,
        is_final: bool = False,
        chat_history: str | None = None,
    ) -> str:
        """Send incremental audio and return the service's cumulative text.

        Parameters
        ----------
        audio : bytes
            Incremental PCM 16-bit mono 16 kHz audio bytes.
        is_final : bool, optional
            Temporary boundary hint; the service flushes its tail but keeps the
            session so later audio continues from the accumulated text.
        chat_history : str | None, optional
            Serialized chat history; currently not forwarded.

        Returns
        -------
        str
            Current cumulative transcript.
        """
        del chat_history
        if not audio and not is_final:
            return self._confirmed_text

        payload = {
            "session_id": self._ensure_session(),
            "audio": base64.b64encode(bytes(audio)).decode("ascii"),
            "is_final": bool(is_final),
            **self.extra_params,
        }
        text = str(self._post_json("/v1/recognize", payload).get("text", "")).strip()
        if text:
            self._confirmed_text = text
            return text
        return self._confirmed_text

    def reset(self) -> None:
        """Release the current session and clear cached text."""
        if self._session_id is None:
            return
        session_id = self._session_id
        self._session_id = None
        self._confirmed_text = ""
        try:
            self.session.delete(
                f"{self.base_url}/v1/session/{session_id}",
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Failed to release ASR session %s: %s", session_id, exc)

    def clone(self) -> "Qwen3ASRClient":
        """Return a new independent session with identical configuration.

        Returns
        -------
        Qwen3ASRClient
            Adapter instance with its own service session.
        """
        return Qwen3ASRClient(
            base_url=self.base_url,
            timeout=self.timeout,
            chunk_ms=self.chunk_ms,
            **self.extra_params,
        )

    def close(self) -> None:
        """Release the session and the underlying HTTP connection pool."""
        self.reset()
        self.session.close()

    def __del__(self) -> None:
        self.close()

    def _ensure_session(self) -> str:
        """Return the session id, registering one on first use.

        Returns
        -------
        str
            Service-issued session identifier.
        """
        if self._session_id is None:
            response = self._post_json("/v1/session", {})
            session_id = str(response.get("session_id", ""))
            if not session_id:
                raise RuntimeError("ASR service did not return a session id")
            self._session_id = session_id
        return self._session_id

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a JSON payload and return the decoded JSON response.

        Parameters
        ----------
        path : str
            Service path such as ``/v1/recognize``.
        payload : dict[str, Any]
            JSON body.

        Returns
        -------
        dict[str, Any]
            Decoded response body.
        """
        response = self.session.post(
            f"{self.base_url}{path}",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
