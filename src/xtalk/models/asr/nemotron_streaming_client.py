"""Adapt the explicit Nemotron service to the existing continuous ASR path."""
from __future__ import annotations

from .continuous_streaming_client import ContinuousStreamingASRClient
from ..registry import model


@model
class NemotronStreamingClient(ContinuousStreamingASRClient):
    """Reuse HTTP transport while validating native Nemotron stream identities.

    Parameters
    ----------
    base_url : str
        Explicit Nemotron service URL; there is no backend fallback.
    timeout : float
        HTTP request deadline in seconds.
    chunk_ms : int
        PCM transport granularity, independently of 160ms model windows.
    """

    def __init__(self, base_url: str = 'http://127.0.0.1:8005',
                 timeout: float = 120, chunk_ms: int = 80):
        super().__init__(base_url, timeout, chunk_ms)
        self._visible = ''
        self._version = -1
        self.last_result: dict = {}

    def _text(self, response) -> str:
        """Reject stale generations and rewrites before exposing a new prefix.

        Parameters
        ----------
        response : requests.Response
            Response from the current decoder generation.

        Returns
        -------
        str
            Verified cumulative visible transcript.
        """
        result = response.json()
        if result['session_id'] != self._session_id or result['generation'] != self._session_id:
            raise RuntimeError('Nemotron returned a stale stream generation')
        text = result['text']
        if not isinstance(text, str) or not text.startswith(self._visible):
            raise RuntimeError('Nemotron rewrote a delivered prefix')
        version = result['prefix_version']
        if not isinstance(version, int) or version < self._version:
            raise RuntimeError('Nemotron returned a stale prefix version')
        self._visible, self._version, self.last_result = text, version, result
        return text

    def reset(self) -> None:
        """Release the old native generation before clearing local prefix state."""
        with self._request_lock:
            super().reset()
            self._visible, self._version, self.last_result = '', -1, {}

    def clone(self) -> 'NemotronStreamingClient':
        """Create independent HTTP and stream state.

        Returns
        -------
        NemotronStreamingClient
            A new explicit Nemotron adapter.
        """
        return NemotronStreamingClient(self.base_url, self.timeout, self.chunk_ms)
