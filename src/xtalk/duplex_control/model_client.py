"""Stream raw official micro-turns from the released-weight inference service."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import aiohttp


@dataclass(frozen=True)
class GenerationEnd:
    """Preserve the model service's termination reason and exact generated ids.

    Parameters
    ----------
    reason : str
        ``stop`` when the model emitted ``<|im_end|>``, otherwise ``length``.
    token_ids : tuple[int, ...]
        Token ids exactly as decoded, including special markers. The released
        server appends these ids back into its history, so text alone cannot
        reproduce the next prompt.
    metrics : dict[str, Any]
        Server timing and cache diagnostics, separate from generated text.
    """

    reason: str
    token_ids: tuple[int, ...] = field(default_factory=tuple)
    metrics: dict[str, Any] = field(default_factory=dict)


class DuplexModelClient:
    """Send raw micro-turn history while preserving conversational special tokens.

    Parameters
    ----------
    base_url : str
        Official-weight service root.
    max_new_tokens : int
        Per system micro-turn generation limit (official default 64).
    timeout_seconds : float
        Request deadline; generation errors propagate to the runtime.
    session_id : str
        Explicit identity used for isolated server caches.
    use_cache : bool
        Reuse verified history prefixes across requests.
    """

    def __init__(self, base_url: str, max_new_tokens: int = 64, timeout_seconds: float = 30,
                 session_id: str = "", use_cache: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_new_tokens = max_new_tokens
        self.timeout_seconds = timeout_seconds
        self.session_id, self.use_cache = session_id, use_cache

    async def stream(self, history: list[dict[str, Any]], *, request_id: str = "") -> AsyncIterator[str | GenerationEnd]:
        """Yield NDJSON token text, including special and end-of-message tokens.

        Parameters
        ----------
        history : list[dict[str, Any]]
            Alternating user micro-turns (``text``) and assistant micro-turns
            (``token_ids``) ending with the triggering user micro-turn.
        request_id : str
            Originating micro-turn identity for latency correlation.
        """
        logging.getLogger(__name__).info("latency_model_client %s", json.dumps({
            "session_id": self.session_id, "request_id": request_id,
            "at_monotonic": time.monotonic(), "kind": "request"}))
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.base_url + "/generate", json={
                "history": history, "max_new_tokens": self.max_new_tokens,
                "session_id": self.session_id, "use_cache": self.use_cache, "request_id": request_id,
            }) as response:
                response.raise_for_status()
                async for line in response.content:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise RuntimeError("Malformed NDJSON from official model service") from exc
                    if "error" in payload:
                        raise RuntimeError(payload["error"])
                    if "text" in payload:
                        yield payload["text"]
                    if "finish_reason" in payload:
                        yield GenerationEnd(
                            payload["finish_reason"],
                            tuple(payload.get("token_ids") or ()),
                            payload.get("metrics") or {},
                        )

    async def release(self) -> None:
        """Release this session's server cache after inference has stopped."""
        if self.use_cache and self.session_id:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    async with session.delete(self.base_url + "/cache/" + self.session_id) as response:
                        response.raise_for_status()
            except (aiohttp.ClientError, asyncio.TimeoutError):
                logging.getLogger(__name__).warning("Cache release deferred to server expiry")
