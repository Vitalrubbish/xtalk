"""Bound incremental text into Kokoro segments on the native playback path."""
from __future__ import annotations

import asyncio
import base64
from collections import deque
import logging
import math
import re
import time
import uuid
from typing import AsyncIterator

import aiohttp
import numpy as np

from ..registry import model
from .interfaces import StreamingTextTTS, TTS

LOG = logging.getLogger(__name__)


def trim_segment_padding(pcm: bytes, text: str) -> tuple[bytes, dict[str, float]]:
    """Remove only redundant outer silence, retaining original speech samples.

    Parameters
    ----------
    pcm : bytes
        Mono PCM16 at 48kHz for one completed segment.
    text : str
        Committed segment text, used only to retain punctuation pauses.

    Returns
    -------
    tuple[bytes, dict[str, float]]
        A contiguous PCM slice and its original duration and edge trim amounts.
    """
    samples = np.frombuffer(pcm, dtype='<i2')
    frames = np.pad(samples, (0, -len(samples) % 480)).reshape(-1, 480)
    rms = np.sqrt(np.mean((frames.astype(np.float64) / 32768) ** 2, axis=1))
    active = np.flatnonzero(rms > 1e-3)
    start, end = 0, len(samples)
    if len(active):
        suffix = text.rstrip()
        tail_ms = 150 if suffix.endswith(('.', '!', '?')) else (80 if suffix.endswith((',', ';')) else 30)
        start = max(0, int(active[0]) * 480 - 1440)
        end = min(len(samples), (int(active[-1]) + 1) * 480 + tail_ms * 48)
    return pcm[start * 2:end * 2], {
        'raw_audio_seconds': len(samples) / 48000,
        'leading_trim_seconds': start / 48000,
        'trailing_trim_seconds': (len(samples) - end) / 48000,
        'audio_seconds': (end - start) / 48000,
    }


@model
class KokoroSegmented(TTS, StreamingTextTTS):
    """Submit bounded segments while accepting actual LLM text increments.

    Parameters
    ----------
    base_url : str
        Dedicated Kokoro synthesis service URL.
    min_chars : int
        Preferred minimum before a sentence boundary triggers submission.
    max_chars : int
        Hard segment size limit, at most 160 characters.
    max_wait_ms : float
        Complete-word aggregation deadline; unfinished words wait for input.
    """

    output_sample_rate = 48000
    sample_rate = 48000

    def __init__(self, base_url: str = 'http://127.0.0.1:8004', min_chars: int = 12,
                 max_chars: int = 160, max_wait_ms: float = 600):
        if not 1 <= min_chars <= max_chars <= 160:
            raise ValueError('Require 1 <= min_chars <= max_chars <= 160')
        if not math.isfinite(max_wait_ms) or max_wait_ms <= 0:
            raise ValueError('max_wait_ms must be positive and finite')
        self.base_url = base_url.rstrip('/')
        self.min_chars, self.max_chars, self.max_wait_ms = min_chars, max_chars, max_wait_ms
        self._worker = None
        self._session = None
        self._buffer = ''
        self._generation = ''
        self._finalized = False
        self._wake = asyncio.Event()
        self._audio = asyncio.Queue(maxsize=50)
        self._buffer_started = None
        self._arrivals = deque()
        self.timeline = []

    def _record(self, kind, **fields):
        """Keep response-local diagnostics and log identities with monotonic time."""
        value = {'kind': kind, 'generation': self._generation,
                 'at_monotonic': time.monotonic(), **fields}
        if len(self.timeline) < 4096:
            self.timeline.append(value)
        LOG.info('kokoro_client %s', value)

    async def start(self) -> None:
        """Start one response generation; no parallel player or synthesis owner."""
        if self._worker is not None:
            raise RuntimeError('Kokoro generation already active')
        self._generation = uuid.uuid4().hex
        self._buffer, self._buffer_started = '', None
        self._arrivals = deque()
        self._finalized = False
        self.timeline = []
        self._wake = asyncio.Event()
        self._audio = asyncio.Queue(maxsize=50)
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
        self._worker = asyncio.create_task(self._produce(self._generation, self._audio))

    async def append_text(self, text: str) -> None:
        """Append visible text without waiting for synthesis.

        Parameters
        ----------
        text : str
            Newly generated text, never a predicted future answer.
        """
        if self._worker is None or self._finalized or self._worker.done():
            raise RuntimeError('No accepting Kokoro generation')
        if len(self._buffer) + len(text) > 8192:
            raise RuntimeError('Kokoro text backlog exceeded 8192 characters')
        if text and not self._buffer:
            self._buffer_started = time.monotonic()
        if text:
            self._arrivals.append((len(text), time.monotonic()))
        self._buffer += text
        self._record('append', chars=len(text))
        self._wake.set()

    async def flush(self) -> None:
        """Finish input and flush the residual segment; later appends are rejected."""
        if self._worker is None:
            raise RuntimeError('Kokoro generation is not active')
        self._finalized = True
        self._wake.set()

    def _take(self, timed_out):
        """Select a causal segment while protecting decimal dots and word boundaries."""
        text = self._buffer
        if not text:
            return ''
        end = None
        for match in re.finditer(r'[!?;](?:\s|$)|(?<!\d)\.(?:\s|$)', text):
            if match.end() >= self.min_chars:
                end = match.end()
                break
        if end is None and len(text) >= self.max_chars:
            end = text.rfind(' ', 0, self.max_chars + 1)
            if end <= 0:
                end = self.max_chars
        if end is None and (timed_out or self._finalized):
            end = min(len(text), self.max_chars)
            if not self._finalized:
                boundary = text.rfind(' ', 0, end + 1)
                if boundary > 0:
                    end = boundary + 1
                else:
                    return ''
        if end is None:
            return ''
        end = min(end, self.max_chars)
        selected, self._buffer = text[:end], text[end:]
        self._record('segment', text=selected,
                     aggregation_seconds=time.monotonic() - self._buffer_started)
        remaining = end
        while remaining:
            count, arrived = self._arrivals.popleft()
            used = min(count, remaining)
            remaining -= used
            if count > used:
                self._arrivals.appendleft((count - used, arrived))
        self._buffer_started = self._arrivals[0][1] if self._arrivals else None
        return selected

    async def _produce(self, generation, audio):
        """Synthesize serially and accept PCM only for the originating generation."""
        sequence = 0
        try:
            while generation == self._generation:
                self._wake.clear()
                timed_out = (self._buffer_started is not None and
                             time.monotonic() - self._buffer_started >= self.max_wait_ms / 1000)
                segment = self._take(timed_out)
                if segment:
                    if not segment.strip():
                        continue
                    request_started = time.monotonic()
                    async with self._session.post(self.base_url + '/v1/synthesize', json={
                        'generation': generation, 'sequence': sequence, 'text': segment,
                        'voice': 'af_heart'}) as response:
                        response.raise_for_status()
                        value = await response.json()
                    if generation != self._generation:
                        return
                    if (value['generation'] != generation or value['sequence'] != sequence
                        or value['sample_rate'] != 48000 or value['channels'] != 1
                        or value['format'] != 'pcm_s16le'):
                        raise RuntimeError('Invalid Kokoro segment identity or audio format')
                    pcm = base64.b64decode(value['pcm'], validate=True)
                    if not pcm or len(pcm) % 2:
                        raise RuntimeError('Kokoro returned empty or malformed PCM16')
                    pcm, padding = trim_segment_padding(pcm, segment)
                    self._record('pcm', sequence=sequence, bytes=len(pcm), **padding,
                                 compute_seconds=value.get('compute_seconds'),
                                 request_seconds=time.monotonic() - request_started)
                    for offset in range(0, len(pcm), 3840):
                        await audio.put(pcm[offset:offset + 3840])
                    sequence += 1
                    continue
                if self._finalized and not self._buffer:
                    break
                wait = None if self._buffer_started is None else max(
                    0.001, self.max_wait_ms / 1000 - (time.monotonic() - self._buffer_started))
                if timed_out:
                    wait = None
                try:
                    await asyncio.wait_for(self._wake.wait(), wait)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await audio.put(exc)
        finally:
            if generation == self._generation:
                await audio.put(None)

    async def audio_stream(self) -> AsyncIterator[bytes]:
        """Yield PCM to TTSManager; cancellation invalidates the captured generation.

        Yields
        ------
        bytes
            Mono signed little-endian PCM16 at 48kHz.
        """
        generation, queue = self._generation, self._audio
        while generation == self._generation:
            value = await queue.get()
            if generation != self._generation or value is None:
                return
            if isinstance(value, Exception):
                raise value
            yield value

    async def stop(self) -> None:
        """Drain a flushed generation; otherwise abort it."""
        if self._worker is None:
            return
        if not self._finalized:
            await self.cancel()
            return
        try:
            await asyncio.wait_for(asyncio.shield(self._worker), 60)
        finally:
            await self._close()

    async def cancel(self) -> None:
        """Invalidate queued and in-flight PCM immediately, then close transport."""
        self._record('cancel')
        self._generation = ''
        if self._worker is not None:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
        while not self._audio.empty():
            self._audio.get_nowait()
        self._audio.put_nowait(None)
        await self._close()

    async def _close(self):
        """Release network resources after drain or cancellation."""
        if self._worker is not None and not self._worker.done():
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
        self._worker = None
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def async_synthesize(self, text: str, **kwargs) -> bytes:
        """Run complete text through an independent instance of the same segmentation.

        Parameters
        ----------
        text : str
            Complete text for the standard TTS compatibility API.
        **kwargs : dict
            Reserved for the standard interface.

        Returns
        -------
        bytes
            Concatenated 48kHz PCM16.
        """
        client = self.clone()
        await client.start()
        try:
            await client.append_text(text)
            await client.flush()
            result = b''.join([chunk async for chunk in client.audio_stream()])
            await client.stop()
            return result
        finally:
            await client.cancel()

    def synthesize(self, text: str) -> bytes:
        """Implement the baseline API through isolated async synthesis.

        Parameters
        ----------
        text : str
            Complete text.

        Returns
        -------
        bytes
            Concatenated 48kHz PCM16.
        """
        return asyncio.run(self.async_synthesize(text))

    def clone(self) -> 'KokoroSegmented':
        """Copy configuration with independent buffers, identities and transport.

        Returns
        -------
        KokoroSegmented
            Session-safe client.
        """
        return KokoroSegmented(self.base_url, self.min_chars, self.max_chars, self.max_wait_ms)
