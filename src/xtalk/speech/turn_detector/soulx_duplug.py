import asyncio
import uuid
import base64
import json
from typing import Optional, Literal

import numpy as np
import websockets

from ..interfaces import (
    TurnDetector,
    TurnDetectionAction,
    TurnDetectionResult,
    TurnDetectionSemantic,
)

_IDLE_RESULT = TurnDetectionResult(
    action=TurnDetectionAction.DO_NOTHING,
    semantic=TurnDetectionSemantic.IDLE,
)


class SoulxDuplug(TurnDetector):
    """Turn detector backed by the SoulX duplex turn-taking WebSocket service."""

    def __init__(
        self,
        server_url: str = "ws://localhost:8000/turn",
        client_id: Optional[str] = None,
        timeout: float = 1.0,
        fallback_time_before_speak: float = 3.0,
    ) -> None:
        super().__init__()
        if fallback_time_before_speak < 0:
            raise ValueError("fallback_time_before_speak must be non-negative")

        # Primary SoulX connection/runtime state.
        self._server_url = server_url
        self._client_id = client_id or uuid.uuid4().hex
        self._timeout = timeout
        self._ws: Optional[websockets.ClientConnection] = None

        # Delayed fallback state used when VAD indicates a speech pause but the
        # remote audio model does not emit an end-of-turn signal.
        self._fallback_time_before_speak = fallback_time_before_speak
        self._fallback_lock = asyncio.Lock()
        self._fallback_seq = 0
        self._pending_fallback_seq: Optional[int] = None

    # ----------------------------
    # Fallback control
    # ----------------------------
    async def _arm_fallback(self) -> int:
        """Start a new delayed fallback window and return its sequence id."""
        async with self._fallback_lock:
            self._fallback_seq += 1
            self._pending_fallback_seq = self._fallback_seq
            return self._fallback_seq

    async def _cancel_fallback(self) -> None:
        """Cancel any pending delayed fallback trigger."""
        async with self._fallback_lock:
            self._pending_fallback_seq = None

    async def _consume_fallback(self, seq: int) -> bool:
        """Consume a fallback trigger if it is still current and the bot is listening."""
        async with self._fallback_lock:
            if self._pending_fallback_seq != seq or not self.listening:
                return False
            self._pending_fallback_seq = None
            return True

    async def _handle_text_fallback(
        self, text: str, speech_pause: Optional[bool]
    ) -> TurnDetectionResult | list[TurnDetectionResult]:
        """
        Handle the text-driven fallback path.

        SoulX remains the primary signal source for turn completion. This fallback
        only exists to guarantee eventual START_GENERATION after a VAD-backed
        speech pause when the remote audio model fails to emit its end-of-turn
        state.
        """
        async with self.listening_lock():
            listening = self.listening

        if not listening:
            return _IDLE_RESULT

        # Any resumed text after a pause means the user is still speaking, so the
        # delayed fallback should be invalidated.
        if not speech_pause:
            await self._cancel_fallback()
            return _IDLE_RESULT

        # Start a cancellable deadline. If nothing stronger arrives before the
        # deadline expires, this call returns START_GENERATION as a safety net.
        seq = await self._arm_fallback()
        await asyncio.sleep(self._fallback_time_before_speak)
        if await self._consume_fallback(seq):
            return TurnDetectionResult(
                action=TurnDetectionAction.START_GENERATION,
                semantic=TurnDetectionSemantic.COMPLETE,
            )

        return _IDLE_RESULT

    # ----------------------------
    # Primary SoulX logic
    # ----------------------------
    async def _handle_audio_primary(
        self, audio: bytes
    ) -> TurnDetectionResult | list[TurnDetectionResult]:
        """Handle the primary audio-driven turn detection path."""
        if self._ws is None:
            await self._connect()

        data = await self._send_audio(audio)
        state_name: Literal["idle", "nonidle", "speak", "blank"] = data.get(
            "state", {}
        ).get("state", "blank")

        async with self.listening_lock():
            if state_name not in ["blank", "idle"]:
                print(f"{'listening' if self.listening else 'speaking'}:{state_name}")
            if self.listening:
                if state_name == "speak":
                    # Primary path wins over the delayed fallback once SoulX has
                    # positively identified end-of-turn.
                    await self._cancel_fallback()
                    return TurnDetectionResult(
                        action=TurnDetectionAction.START_GENERATION,
                        semantic=TurnDetectionSemantic.COMPLETE,
                    )
                if state_name == "nonidle":
                    return TurnDetectionResult(
                        action=TurnDetectionAction.DO_NOTHING,
                        semantic=TurnDetectionSemantic.INCOMPLETE,
                    )
            else:
                if state_name == "nonidle":
                    return TurnDetectionResult(
                        action=TurnDetectionAction.STOP_SPEAKING,
                        semantic=TurnDetectionSemantic.INCOMPLETE,
                    )
        return _IDLE_RESULT

    async def _connect(self) -> None:
        self._ws = await websockets.connect(self._server_url)

    async def _send_audio(self, audio: bytes) -> dict:
        """Send audio to the server and return the parsed response."""
        pcm = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        payload = {
            "type": "audio",
            "session_id": self._client_id,
            "audio": base64.b64encode(pcm.astype(np.float32).tobytes()).decode(),
        }
        msg = json.dumps(payload)

        try:
            await self._ws.send(msg)
            response = await asyncio.wait_for(self._ws.recv(), timeout=self._timeout)
            return json.loads(response)
        except Exception:
            # Reconnect on any failure and retry once
            await self._connect()
            await self._ws.send(msg)
            response = await asyncio.wait_for(self._ws.recv(), timeout=self._timeout)
            return json.loads(response)

    def detect(
        self,
        audio: Optional[bytes] = None,
        text: Optional[str] = None,
        speech_pause: Optional[bool] = None,
    ) -> TurnDetectionResult | list[TurnDetectionResult]:
        return asyncio.run(self.async_detect(audio, text, speech_pause))

    async def async_detect(
        self,
        audio: Optional[bytes] = None,
        text: Optional[str] = None,
        speech_pause: Optional[bool] = None,
    ) -> TurnDetectionResult | list[TurnDetectionResult]:
        if text is not None:
            return await self._handle_text_fallback(text, speech_pause)

        if audio is None:
            return _IDLE_RESULT

        return await self._handle_audio_primary(audio)

    def clone(self) -> "SoulxDuplug":
        return SoulxDuplug(
            server_url=self._server_url,
            timeout=self._timeout,
            fallback_time_before_speak=self._fallback_time_before_speak,
        )
