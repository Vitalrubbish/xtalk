#!/usr/bin/env python3
"""Automated backend testing and test-set generation for Xtalk.

Example commands:
    python scripts/test.py --create logs/test_templates/smoke --out logs/tests
    python scripts/test.py --config server_configs/sample_local.json --input logs/tests/smoke --out logs/test_results/smoke
    python scripts/test.py --config server_configs/sample_local.json --input logs/tests/smoke --out logs/test_results/smoke --concurrency 2 --with-vad
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import math
import shutil
import socket
import subprocess
import sys
import time
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import requests
import soundfile as sf
import uvicorn
import websockets
from fastapi import FastAPI

from xtalk.api import Xtalk

try:
    import soxr
except Exception:  # pragma: no cover - optional dependency
    soxr = None


DEFAULT_TEST_CONFIG = {
    "concurrency": 1,
    "with_vad": False,
    "vad_redemption_ms": 500,
}
DEFAULT_SETTLE_SECONDS = 1.5
EMBEDDED_SERVER_HOST = "127.0.0.1"
EMBEDDED_SERVER_PORT = 0
SERVICE_CONFIG_PATCH = {
    "recording": True,
    "send_full_audio_to_client": True,
    "enable_persistence": False,
}
NO_RESPONSE_GRACE_SECONDS = 5.0
NON_ACTIVITY_ACTIONS = {"thought_updated"}
PREFERRED_TEST_CONFIG_NAMES = (
    "test_config.json",
    "testing_config.json",
    "config.json",
)
PREFERRED_TTS_CONFIG_NAMES = (
    "tts_config.json",
    "config.json",
    "sample_local.json",
)


@dataclass(frozen=True)
class RelativeTimeSpec:
    """Represents a scheduled timestamp expression."""

    kind: Literal["absolute", "relative"]
    value: float | None = None
    anchor: str | None = None
    offset: float = 0.0
    occurrence: int | None = None


@dataclass(frozen=True)
class ScheduledAudioInput:
    """Represents one scheduled input audio clip."""

    time_spec: RelativeTimeSpec
    audio_path: Path


@dataclass(frozen=True)
class GeneratedCaseLine:
    """Represents one scheduled text line for test-case generation."""

    time_spec: str
    text: str


@dataclass(frozen=True)
class EffectiveTestConfig:
    """Effective dataset-level runtime configuration."""

    concurrency: int
    with_vad: bool
    vad_redemption_ms: int


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run automated Xtalk backend tests or generate test datasets."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--input",
        type=Path,
        help="Path to the input test dataset folder.",
    )
    mode.add_argument(
        "--create",
        type=Path,
        help="Path to the test-case generation source folder.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to the backend service configuration JSON.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Path to the output folder.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        help="Override the dataset concurrency in test mode.",
    )
    vad_group = parser.add_mutually_exclusive_group()
    vad_group.add_argument(
        "--with-vad",
        dest="with_vad_override",
        action="store_true",
        help="Force-enable client-side VAD in test mode.",
    )
    vad_group.add_argument(
        "--without-vad",
        dest="with_vad_override",
        action="store_false",
        help="Force-disable client-side VAD in test mode.",
    )
    parser.set_defaults(with_vad_override=None)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file into a dictionary."""
    with path.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON file with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2, sort_keys=True)
        file_obj.write("\n")


def resolve_root_json(
    root: Path,
    preferred_names: tuple[str, ...],
) -> Path | None:
    """Resolve a single JSON file from a dataset root."""
    candidates = sorted(path for path in root.glob("*.json") if path.is_file())
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    by_name = {path.name: path for path in candidates}
    for name in preferred_names:
        if name in by_name:
            return by_name[name]

    names = ", ".join(path.name for path in candidates)
    raise ValueError(
        f"Found multiple JSON files under {root} and could not choose one: {names}"
    )


def discover_case_dirs(root: Path) -> list[Path]:
    """Discover direct child case directories."""
    case_dirs = sorted(path for path in root.iterdir() if path.is_dir())
    if not case_dirs:
        raise ValueError(f"No case directories found under {root}")
    return case_dirs


def merge_service_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    """Inject required testing service configuration overrides."""
    merged = dict(raw_config)
    service_config = dict(merged.get("service_config") or {})
    service_config.update(SERVICE_CONFIG_PATCH)
    merged["service_config"] = service_config
    return merged


def load_effective_test_config(
    dataset_root: Path,
    *,
    concurrency_override: int | None,
    with_vad_override: bool | None,
) -> EffectiveTestConfig:
    """Load and resolve the dataset test configuration."""
    config_path = resolve_root_json(
        dataset_root,
        preferred_names=PREFERRED_TEST_CONFIG_NAMES,
    )
    raw_config = dict(DEFAULT_TEST_CONFIG)
    if config_path is not None:
        raw_config.update(load_json(config_path))

    if concurrency_override is not None:
        raw_config["concurrency"] = concurrency_override
    if with_vad_override is not None:
        raw_config["with_vad"] = with_vad_override

    concurrency = int(raw_config.get("concurrency", 1))
    if concurrency <= 0:
        raise ValueError("concurrency must be a positive integer")
    with_vad = bool(raw_config.get("with_vad", False))
    vad_redemption_ms = int(
        raw_config.get(
            "vad_redemption_ms",
            DEFAULT_TEST_CONFIG["vad_redemption_ms"],
        )
    )
    if vad_redemption_ms <= 0:
        raise ValueError("vad_redemption_ms must be a positive integer")
    return EffectiveTestConfig(
        concurrency=concurrency,
        with_vad=with_vad,
        vad_redemption_ms=vad_redemption_ms,
    )


def parse_timestamp_spec(raw_spec: str) -> RelativeTimeSpec:
    """Parse a timestamp expression from timestamp.txt."""
    spec = raw_spec.strip()
    if not spec:
        raise ValueError("Empty timestamp expression")

    try:
        return RelativeTimeSpec(kind="absolute", value=float(spec))
    except ValueError:
        pass

    if "+" in spec:
        anchor_name, offset_text = spec.split("+", 1)
        offset = float(offset_text.strip())
    else:
        anchor_name, offset = spec, 0.0

    anchor = normalize_anchor_name(anchor_name.strip())
    return RelativeTimeSpec(kind="relative", anchor=anchor, offset=offset)


def normalize_anchor_name(anchor: str) -> str:
    """Normalize timestamp anchor names across supported aliases."""
    aliases = {
        "ai_start": "last_ai_start",
        "last_ai_start": "last_ai_start",
        "ai_end": "last_ai_end",
        "last_ai_end": "last_ai_end",
        "user_start": "last_user_start",
        "last_user_start": "last_user_start",
        "user_end": "last_user_end",
        "last_user_end": "last_user_end",
    }
    if anchor not in aliases:
        raise ValueError(f"Unsupported timestamp anchor: {anchor}")
    return aliases[anchor]


def parse_case_inputs(case_dir: Path) -> list[ScheduledAudioInput]:
    """Parse timestamp.txt and resolve audio files for one case."""
    timestamp_path = case_dir / "timestamp.txt"
    if not timestamp_path.exists():
        raise ValueError(f"Missing timestamp.txt in {case_dir}")

    scheduled_inputs: list[ScheduledAudioInput] = []
    relative_anchor_occurrences: dict[str, int] = {}
    with timestamp_path.open("r", encoding="utf-8") as file_obj:
        for line_no, raw_line in enumerate(file_obj, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                raise ValueError(
                    f"Invalid timestamp entry in {timestamp_path}:{line_no}: {line}"
                )
            time_text, audio_name = line.split(":", 1)
            audio_path = case_dir / audio_name.strip()
            if not audio_path.exists():
                raise ValueError(f"Missing audio file {audio_path}")
            time_spec = parse_timestamp_spec(time_text)
            if time_spec.kind == "relative" and time_spec.anchor is not None:
                occurrence = relative_anchor_occurrences.get(time_spec.anchor, 0) + 1
                relative_anchor_occurrences[time_spec.anchor] = occurrence
                time_spec = RelativeTimeSpec(
                    kind=time_spec.kind,
                    value=time_spec.value,
                    anchor=time_spec.anchor,
                    offset=time_spec.offset,
                    occurrence=occurrence,
                )
            scheduled_inputs.append(
                ScheduledAudioInput(
                    time_spec=time_spec,
                    audio_path=audio_path,
                )
            )

    if not scheduled_inputs:
        raise ValueError(f"No valid timestamp entries found in {timestamp_path}")
    return scheduled_inputs


def parse_generation_case(case_dir: Path) -> list[GeneratedCaseLine]:
    """Parse timestamp.txt for test-case generation."""
    timestamp_path = case_dir / "timestamp.txt"
    if not timestamp_path.exists():
        raise ValueError(f"Missing timestamp.txt in {case_dir}")

    lines: list[GeneratedCaseLine] = []
    with timestamp_path.open("r", encoding="utf-8") as file_obj:
        for line_no, raw_line in enumerate(file_obj, start=1):
            line = raw_line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if ":" not in line:
                raise ValueError(
                    f"Invalid timestamp entry in {timestamp_path}:{line_no}: {line}"
                )
            time_text, text = line.split(":", 1)
            lines.append(
                GeneratedCaseLine(time_spec=time_text.strip(), text=text.strip())
            )

    if not lines:
        raise ValueError(f"No valid generation entries found in {timestamp_path}")
    return lines


def pick_free_port(host: str) -> int:
    """Pick a free TCP port for the embedded server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def resample_audio(audio: np.ndarray, source_sr: int, target_sr: int) -> np.ndarray:
    """Resample mono audio to the target sample rate."""
    if source_sr == target_sr:
        return audio.astype(np.float32, copy=False)

    mono_audio = audio.astype(np.float32, copy=False)
    if soxr is not None:
        return soxr.resample(mono_audio, source_sr, target_sr).astype(np.float32)

    duration = mono_audio.shape[0] / float(source_sr)
    target_size = max(1, int(round(duration * target_sr)))
    if mono_audio.shape[0] == 1:
        return np.full((target_size,), float(mono_audio[0]), dtype=np.float32)
    x_old = np.linspace(0.0, 1.0, num=mono_audio.shape[0], endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=target_size, endpoint=False)
    return np.interp(x_new, x_old, mono_audio).astype(np.float32)


def float_to_pcm16(audio: np.ndarray) -> bytes:
    """Convert floating point audio in [-1, 1] to PCM16 bytes."""
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    return pcm.tobytes()


def load_audio_as_pcm16(path: Path, *, target_sr: int = 16000) -> bytes:
    """Load an audio file as mono PCM16 bytes at the requested sample rate."""
    try:
        audio, sample_rate = sf.read(path, dtype="float32", always_2d=False)
        if isinstance(audio, np.ndarray) and audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        if not isinstance(audio, np.ndarray):
            audio = np.asarray(audio, dtype=np.float32)
        resampled = resample_audio(audio, int(sample_rate), target_sr)
        return float_to_pcm16(resampled)
    except Exception:
        return decode_audio_via_ffmpeg(path, target_sr=target_sr)


def decode_audio_via_ffmpeg(path: Path, *, target_sr: int = 16000) -> bytes:
    """Use ffmpeg as a fallback decoder for formats unsupported by soundfile."""
    command = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(path),
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        str(target_sr),
        "-",
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"Failed to decode {path} with ffmpeg: {stderr}")
    return bytes(result.stdout)


def decode_tts_audio_payload(
    payload: bytes,
    *,
    sample_rate_hint: int = 48000,
) -> tuple[bytes, int]:
    """Normalize a TTS payload into WAV-ready PCM16 bytes."""
    try:
        audio, sample_rate = sf.read(
            io.BytesIO(payload), dtype="float32", always_2d=False
        )
        if isinstance(audio, np.ndarray) and audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        if not isinstance(audio, np.ndarray):
            audio = np.asarray(audio, dtype=np.float32)
        return float_to_pcm16(np.asarray(audio, dtype=np.float32)), int(sample_rate)
    except Exception:
        return payload, sample_rate_hint


def write_pcm_wav(
    path: Path,
    *,
    pcm_bytes: bytes,
    sample_rate: int,
    channels: int,
) -> None:
    """Write PCM bytes into a WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)


def count_wav_frames(path: Path) -> int:
    """Return the number of frames in a WAV file."""
    with wave.open(str(path), "rb") as wav_file:
        return int(wav_file.getnframes())


def stereo_pcm_has_right_channel_signal(pcm_bytes: bytes) -> bool:
    """Return whether stereo PCM16 data contains non-zero right-channel samples."""
    if not pcm_bytes:
        return False
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    if samples.size < 2:
        return False
    stereo = samples.reshape(-1, 2)
    return bool(np.any(stereo[:, 1]))


class EmbeddedServer:
    """Run an embedded uvicorn server for automated tests."""

    def __init__(self, *, config: dict[str, Any], host: str, port: int) -> None:
        self._config = config
        self._host = host
        self._port = port if port > 0 else pick_free_port(host)
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def http_base_url(self) -> str:
        """Return the HTTP base URL."""
        return f"http://{self._host}:{self._port}"

    @property
    def websocket_url(self) -> str:
        """Return the WebSocket endpoint URL."""
        return f"ws://{self._host}:{self._port}/ws"

    async def __aenter__(self) -> "EmbeddedServer":
        """Start the embedded server."""
        app = FastAPI(title="Xtalk Automated Test Server")
        xtalk_instance = Xtalk.from_config(self._config)
        xtalk_instance.mount_routes(app)

        uvicorn_config = uvicorn.Config(
            app=app,
            host=self._host,
            port=self._port,
            log_level="error",
            lifespan="off",
        )
        self._server = uvicorn.Server(uvicorn_config)
        self._server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
        self._task = asyncio.create_task(self._server.serve())

        deadline = time.monotonic() + 15.0
        while True:
            if self._server.started:
                return self
            if self._task.done():
                raise RuntimeError("Embedded server exited before startup completed")
            if time.monotonic() >= deadline:
                raise TimeoutError("Timed out waiting for embedded server startup")
            await asyncio.sleep(0.05)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Stop the embedded server."""
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            await self._task


class AnchorClock:
    """Tracks absolute monotonic timestamps for schedule anchors."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._values: dict[str, float] = {}
        self._history: dict[str, list[float]] = {}

    async def set(self, name: str, value: float) -> None:
        """Set an anchor and notify waiting tasks."""
        async with self._condition:
            self._values[name] = value
            self._history.setdefault(name, []).append(value)
            self._condition.notify_all()

    async def wait_for(self, name: str) -> float:
        """Wait until an anchor becomes available."""
        async with self._condition:
            await self._condition.wait_for(lambda: name in self._values)
            return self._values[name]

    async def wait_for_occurrence(self, name: str, occurrence: int) -> float:
        """Wait until the requested anchor occurrence becomes available."""
        if occurrence <= 0:
            raise ValueError("occurrence must be a positive integer")
        async with self._condition:
            await self._condition.wait_for(
                lambda: len(self._history.get(name, [])) >= occurrence
            )
            return self._history[name][occurrence - 1]

    async def get(self, name: str) -> float | None:
        """Return an anchor value if it already exists."""
        async with self._condition:
            return self._values.get(name)


class ClientVADController:
    """Client-side VAD state machine aligned with frontend/backend VAD timing."""

    SAMPLE_RATE = 16000
    FRAME_SAMPLES = 512
    FRAME_BYTES = FRAME_SAMPLES * 2
    MIN_SPEECH_MS = 250
    DEFAULT_REDEMPTION_MS = 500
    _SHARED_VAD: Any = None

    def __init__(self, *, redemption_ms: int = DEFAULT_REDEMPTION_MS) -> None:
        from xtalk.speech.vad.silero_vad import SileroVAD

        if self.__class__._SHARED_VAD is None:
            self.__class__._SHARED_VAD = SileroVAD()
        self._vad = self.__class__._SHARED_VAD
        self._redemption_ms = redemption_ms
        self._speech_run_frames = 0
        self._non_speech_run_frames = 0
        self._in_speech = False
        self._min_speech_frames = max(
            1,
            int(
                round(
                    self.MIN_SPEECH_MS
                    / ((self.FRAME_SAMPLES * 1000.0) / self.SAMPLE_RATE)
                )
            ),
        )
        self._redemption_frames = max(
            1,
            int(
                round(
                    self._redemption_ms
                    / ((self.FRAME_SAMPLES * 1000.0) / self.SAMPLE_RATE)
                )
            ),
        )

    def feed(self, frame: bytes) -> list[str]:
        """Feed one PCM frame and return zero or more VAD events."""
        if len(frame) < self.FRAME_BYTES:
            frame = frame + (b"\x00" * (self.FRAME_BYTES - len(frame)))

        is_speech = bool(self._vad.is_speech(frame))
        events: list[str] = []
        if is_speech:
            self._speech_run_frames += 1
            self._non_speech_run_frames = 0
            if (
                not self._in_speech
                and self._speech_run_frames >= self._min_speech_frames
            ):
                self._in_speech = True
                events.append("vad_speech_start")
        else:
            self._non_speech_run_frames += 1
            self._speech_run_frames = 0
            if (
                self._in_speech
                and self._non_speech_run_frames >= self._redemption_frames
            ):
                self._in_speech = False
                events.append("vad_speech_end")
        return events

    def trailing_silence_frames(self) -> int:
        """Return the number of silence frames needed to trigger speech end."""
        return self._redemption_frames + 1


class PlaybackSimulator:
    """Simulates frontend output playback behavior over a WebSocket session."""

    def __init__(
        self,
        *,
        websocket: websockets.WebSocketClientProtocol,
        anchors: AnchorClock,
        activity_callback,
    ) -> None:
        self._websocket = websocket
        self._anchors = anchors
        self._activity_callback = activity_callback
        self._queue: deque[bytes] = deque()
        self._condition = asyncio.Condition()
        self._resume_event = asyncio.Event()
        self._resume_event.set()
        self._closed = False
        self._server_tts_finished = False
        self._currently_playing = False
        self._turn_started = False
        self._stop_generation = 0
        self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        try:
            while True:
                async with self._condition:
                    await self._condition.wait_for(
                        lambda: self._closed or bool(self._queue)
                    )
                    if self._closed:
                        return
                    chunk = self._queue.popleft()
                    generation = self._stop_generation
                    self._currently_playing = True

                if not self._turn_started:
                    self._turn_started = True
                    await self._anchors.set(
                        "last_ai_start", asyncio.get_running_loop().time()
                    )

                await self._activity_callback()
                duration = self._chunk_duration_seconds(chunk)
                interrupted = await self._play_chunk(duration, generation)
                async with self._condition:
                    self._currently_playing = False

                if interrupted:
                    continue

                if not await self._send_json({"action": "tts_chunk_played"}):
                    return
                await self._activity_callback()
                await self._maybe_finish_turn()
        except asyncio.CancelledError:
            raise
        except websockets.ConnectionClosed:
            return

    async def _play_chunk(self, duration: float, generation: int) -> bool:
        remaining = duration
        while remaining > 0.0:
            await self._resume_event.wait()
            if self._stop_generation != generation:
                return True
            start = asyncio.get_running_loop().time()
            step = min(0.05, remaining)
            await asyncio.sleep(step)
            if self._stop_generation != generation:
                return True
            if not self._resume_event.is_set():
                continue
            elapsed = asyncio.get_running_loop().time() - start
            remaining = max(0.0, remaining - elapsed)
        return False

    @staticmethod
    def _chunk_duration_seconds(chunk: bytes) -> float:
        samples = len(chunk) // 2
        return samples / 48000.0

    async def push(self, chunk: bytes) -> None:
        """Queue one TTS chunk for simulated playback."""
        async with self._condition:
            self._queue.append(chunk)
            self._condition.notify_all()
        await self._activity_callback()

    async def pause(self) -> None:
        """Pause simulated playback."""
        self._resume_event.clear()
        await self._activity_callback()

    async def resume(self) -> None:
        """Resume simulated playback."""
        self._resume_event.set()
        await self._activity_callback()

    async def stop(self) -> None:
        """Stop playback and clear pending chunks."""
        async with self._condition:
            self._queue.clear()
            self._stop_generation += 1
            self._server_tts_finished = False
            self._currently_playing = False
            self._turn_started = False
            self._condition.notify_all()
        self._resume_event.set()
        await self._activity_callback()

    async def mark_server_tts_finished(self) -> None:
        """Mark that the server finished generating TTS for the current turn."""
        async with self._condition:
            self._server_tts_finished = True
        await self._maybe_finish_turn()

    async def is_idle(self) -> bool:
        """Return whether playback is fully idle."""
        async with self._condition:
            return not self._currently_playing and not self._queue

    async def _maybe_finish_turn(self) -> None:
        async with self._condition:
            if (
                not self._server_tts_finished
                or self._currently_playing
                or self._queue
                or not self._turn_started
            ):
                return
            self._server_tts_finished = False
            self._turn_started = False
        now = asyncio.get_running_loop().time()
        await self._anchors.set("last_ai_end", now)
        if not await self._send_json({"action": "tts_playback_finished"}):
            return
        await self._activity_callback()

    async def _send_json(self, payload: dict[str, Any]) -> bool:
        """Send a JSON payload unless the WebSocket is already closed."""
        try:
            await self._websocket.send(json.dumps(payload))
        except websockets.ConnectionClosed:
            return False
        return True

    async def close(self) -> None:
        """Stop the simulator worker."""
        await self.stop()
        async with self._condition:
            self._closed = True
            self._condition.notify_all()
        self._worker_task.cancel()
        try:
            await self._worker_task
        except asyncio.CancelledError:
            pass


class CaseRunner:
    """Runs one automated test case against the embedded server."""

    def __init__(
        self,
        *,
        case_dir: Path,
        output_path: Path,
        temp_recording_path: Path,
        websocket_url: str,
        http_base_url: str,
        with_vad: bool,
        vad_redemption_ms: int,
        settle_seconds: float,
    ) -> None:
        self._case_dir = case_dir
        self._output_path = output_path
        self._temp_recording_path = temp_recording_path
        self._websocket_url = websocket_url
        self._http_base_url = http_base_url
        self._with_vad = with_vad
        self._vad_redemption_ms = vad_redemption_ms
        self._settle_seconds = settle_seconds
        self._anchors = AnchorClock()
        self._connection_started: float | None = None
        self._attached_event = asyncio.Event()
        self._scheduler_done = asyncio.Event()
        self._ws_closed = asyncio.Event()
        self._activity_lock = asyncio.Lock()
        self._last_activity: float = 0.0
        self._scheduler_done_at: float | None = None
        self._full_audio_bytes = bytearray()
        self._receiver_task: asyncio.Task[None] | None = None
        self._playback: PlaybackSimulator | None = None
        self._error: Exception | None = None
        self._last_full_audio_at: float | None = None

    async def run(self) -> None:
        """Execute the case end to end and write the output WAV."""
        token = await self._login()
        websocket = await websockets.connect(
            self._build_authenticated_ws_url(token),
            max_size=None,
        )

        try:
            self._playback = PlaybackSimulator(
                websocket=websocket,
                anchors=self._anchors,
                activity_callback=self._touch_activity,
            )
            self._receiver_task = asyncio.create_task(self._receiver_loop(websocket))

            await websocket.send(
                json.dumps({"action": "attach_session", "session_id": None})
            )
            await self._attached_event.wait()
            self._connection_started = asyncio.get_running_loop().time()
            await self._touch_activity()

            await websocket.send(
                json.dumps(
                    {
                        "action": "session_config",
                        "recording_path": str(self._temp_recording_path),
                    }
                )
            )

            scheduled_inputs = parse_case_inputs(self._case_dir)
            await self._send_scheduled_inputs(websocket, scheduled_inputs)
            self._scheduler_done_at = asyncio.get_running_loop().time()
            self._scheduler_done.set()
            await self._wait_until_idle(websocket)
        finally:
            await websocket.close()
            if self._receiver_task is not None:
                try:
                    await self._receiver_task
                except websockets.ConnectionClosed:
                    pass
            if self._playback is not None:
                await self._playback.close()

        await asyncio.sleep(0.1)
        await self._materialize_output()
        if self._error is not None:
            raise self._error

    async def _login(self) -> str:
        payload = await asyncio.to_thread(
            requests.post,
            f"{self._http_base_url}/api/auth/login",
            timeout=10,
        )
        payload.raise_for_status()
        body = payload.json()
        token = body.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Login response did not include access_token")
        return token

    def _build_authenticated_ws_url(self, token: str) -> str:
        separator = "&" if "?" in self._websocket_url else "?"
        return f"{self._websocket_url}{separator}access_token={token}"

    async def _receiver_loop(
        self, websocket: websockets.WebSocketClientProtocol
    ) -> None:
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    await self._touch_activity()
                    if self._playback is not None:
                        await self._playback.push(message)
                    continue
                await self._handle_text_message(message)
        except websockets.ConnectionClosed:
            pass
        finally:
            self._ws_closed.set()

    async def _handle_text_message(self, message: str) -> None:
        payload = json.loads(message)
        action = payload.get("action")
        data = payload.get("data")
        if action not in NON_ACTIVITY_ACTIONS:
            await self._touch_activity()
        if action == "session_attached":
            self._attached_event.set()
            return
        if action == "pause_tts" and self._playback is not None:
            await self._playback.pause()
            return
        if action == "resume_tts" and self._playback is not None:
            await self._playback.resume()
            return
        if action == "stop_tts" and self._playback is not None:
            await self._playback.stop()
            return
        if action == "tts_finished" and self._playback is not None:
            await self._playback.mark_server_tts_finished()
            return
        if action == "full_audio_frame":
            self._last_full_audio_at = asyncio.get_running_loop().time()
            self._collect_full_audio_frame(data)
            return
        if action == "error":
            self._error = RuntimeError(f"{self._case_dir.name}: backend error: {data}")

    def _collect_full_audio_frame(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        audio_base64 = data.get("audio_base64")
        if not isinstance(audio_base64, str) or not audio_base64:
            return
        sample_rate = int(data.get("sample_rate", 48000))
        channels = int(data.get("channels", 2))
        audio_format = data.get("format", "pcm_s16le")
        if sample_rate != 48000 or channels != 2 or audio_format != "pcm_s16le":
            raise RuntimeError(
                f"Unsupported full_audio_frame format: sr={sample_rate}, channels={channels}, format={audio_format}"
            )
        self._full_audio_bytes.extend(base64.b64decode(audio_base64))

    async def _send_scheduled_inputs(
        self,
        websocket: websockets.WebSocketClientProtocol,
        scheduled_inputs: list[ScheduledAudioInput],
    ) -> None:
        for scheduled_input in scheduled_inputs:
            target_time = await self._resolve_target_time(scheduled_input.time_spec)
            await self._send_silence_until(websocket, target_time)
            await self._stream_audio_file(websocket, scheduled_input.audio_path)
            if self._error is not None:
                raise self._error

    async def _resolve_target_time(self, time_spec: RelativeTimeSpec) -> float:
        if self._connection_started is None:
            raise RuntimeError("Connection start time is not initialized")
        if time_spec.kind == "absolute":
            return self._connection_started + float(time_spec.value or 0.0)
        if time_spec.anchor is None:
            raise RuntimeError("Relative time spec missing anchor")
        if time_spec.occurrence is None:
            raise RuntimeError("Relative time spec missing anchor occurrence")
        anchor_value = await self._anchors.wait_for_occurrence(
            time_spec.anchor, time_spec.occurrence
        )
        return anchor_value + time_spec.offset

    async def _stream_audio_file(
        self,
        websocket: websockets.WebSocketClientProtocol,
        audio_path: Path,
    ) -> None:
        pcm_bytes = load_audio_as_pcm16(audio_path, target_sr=16000)
        frame_bytes = ClientVADController.FRAME_BYTES
        vad_controller = (
            ClientVADController(redemption_ms=self._vad_redemption_ms)
            if self._with_vad
            else None
        )
        audio_frame_count = int(math.ceil(len(pcm_bytes) / frame_bytes))
        trailing_frames = (
            vad_controller.trailing_silence_frames() if vad_controller else 0
        )
        total_frames = audio_frame_count + trailing_frames
        stream_started = asyncio.get_running_loop().time()
        await self._anchors.set("last_user_start", stream_started)
        last_user_end_set = False

        for frame_index in range(total_frames):
            target_send_time = stream_started + (
                frame_index * (ClientVADController.FRAME_SAMPLES / 16000.0)
            )
            now = asyncio.get_running_loop().time()
            if target_send_time > now:
                await asyncio.sleep(target_send_time - now)

            start = frame_index * frame_bytes
            frame = pcm_bytes[start : start + frame_bytes]
            if len(frame) < frame_bytes:
                frame = frame + (b"\x00" * (frame_bytes - len(frame)))

            await websocket.send(frame)
            await self._touch_activity()
            if not last_user_end_set and frame_index + 1 >= audio_frame_count:
                await self._anchors.set(
                    "last_user_end", asyncio.get_running_loop().time()
                )
                last_user_end_set = True
            if vad_controller is not None:
                for action in vad_controller.feed(frame):
                    await websocket.send(json.dumps({"action": action}))
                    await self._touch_activity()

        if not last_user_end_set:
            await self._anchors.set("last_user_end", asyncio.get_running_loop().time())

    async def _send_silence_until(
        self,
        websocket: websockets.WebSocketClientProtocol,
        target_time: float,
    ) -> None:
        """Continuously send silent PCM frames until the target monotonic time."""
        silence_frame = b"\x00" * ClientVADController.FRAME_BYTES
        frame_duration = ClientVADController.FRAME_SAMPLES / 16000.0
        while True:
            now = asyncio.get_running_loop().time()
            remaining = target_time - now
            if remaining <= 0.0:
                return
            await websocket.send(silence_frame)
            await asyncio.sleep(min(frame_duration, remaining))

    async def _wait_until_idle(
        self, websocket: websockets.WebSocketClientProtocol
    ) -> None:
        while True:
            if self._error is not None:
                raise self._error
            playback_idle = True
            if self._playback is not None:
                playback_idle = await self._playback.is_idle()

            await websocket.send(b"\x00" * ClientVADController.FRAME_BYTES)

            async with self._activity_lock:
                last_activity = self._last_activity
            quiet_for = asyncio.get_running_loop().time() - last_activity
            ai_end_seen = await self._anchors.get("last_ai_end")
            last_full_audio_at = self._last_full_audio_at
            scheduler_quiet_for = 0.0
            if self._scheduler_done_at is not None:
                scheduler_quiet_for = (
                    asyncio.get_running_loop().time() - self._scheduler_done_at
                )
            no_response_grace_elapsed = scheduler_quiet_for >= max(
                self._settle_seconds,
                NO_RESPONSE_GRACE_SECONDS,
            )
            if self._scheduler_done.is_set() and playback_idle:
                if ai_end_seen is not None:
                    if (
                        last_full_audio_at is not None
                        and last_full_audio_at >= ai_end_seen
                        and quiet_for >= self._settle_seconds
                    ):
                        return
                elif no_response_grace_elapsed:
                    if (
                        last_full_audio_at is not None
                        and quiet_for >= self._settle_seconds
                    ):
                        return
            if self._ws_closed.is_set():
                return
            await asyncio.sleep(0.1)

    async def _touch_activity(self) -> None:
        async with self._activity_lock:
            self._last_activity = asyncio.get_running_loop().time()

    async def _materialize_output(self) -> None:
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        full_audio_bytes = bytes(self._full_audio_bytes)
        if not full_audio_bytes:
            raise RuntimeError(
                f"{self._case_dir.name}: did not receive any full_audio_frame"
            )
        if not stereo_pcm_has_right_channel_signal(full_audio_bytes):
            raise RuntimeError(
                f"{self._case_dir.name}: received full_audio_frame but AI channel is empty"
            )
        write_pcm_wav(
            self._output_path,
            pcm_bytes=full_audio_bytes,
            sample_rate=48000,
            channels=2,
        )


def validate_vad_configuration(config: dict[str, Any], *, with_vad: bool) -> None:
    """Validate frontend/backend VAD compatibility for test mode."""
    has_backend_vad = bool(config.get("vad"))
    if with_vad and has_backend_vad:
        raise ValueError(
            "with_vad=true uses client-side VAD; remove backend 'vad' from the server config to avoid duplicate turn events."
        )
    if not with_vad and not has_backend_vad:
        raise ValueError(
            "with_vad=false requires a backend 'vad' model in the server config."
        )


async def run_test_mode(args: argparse.Namespace) -> None:
    """Run automated backend tests."""
    if args.config is None:
        raise ValueError("--config is required in test mode")
    dataset_root = args.input.resolve()
    if not dataset_root.is_dir():
        raise ValueError(f"Input dataset directory does not exist: {dataset_root}")

    raw_service_config = load_json(args.config.resolve())
    merged_service_config = merge_service_config(raw_service_config)
    effective_test_config = load_effective_test_config(
        dataset_root,
        concurrency_override=args.concurrency,
        with_vad_override=args.with_vad_override,
    )
    validate_vad_configuration(
        merged_service_config,
        with_vad=effective_test_config.with_vad,
    )

    output_root = args.out.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(
        output_root / "test_config.json",
        {
            "concurrency": effective_test_config.concurrency,
            "with_vad": effective_test_config.with_vad,
            "vad_redemption_ms": effective_test_config.vad_redemption_ms,
        },
    )
    write_json(output_root / "service_config.json", merged_service_config)

    temp_recording_root = output_root / ".server_recordings"
    temp_recording_root.mkdir(parents=True, exist_ok=True)

    case_dirs = discover_case_dirs(dataset_root)
    semaphore = asyncio.Semaphore(effective_test_config.concurrency)

    async with EmbeddedServer(
        config=merged_service_config,
        host=EMBEDDED_SERVER_HOST,
        port=EMBEDDED_SERVER_PORT,
    ) as server:

        async def run_one_case(case_dir: Path) -> None:
            async with semaphore:
                runner = CaseRunner(
                    case_dir=case_dir,
                    output_path=output_root / f"{case_dir.name}.wav",
                    temp_recording_path=temp_recording_root / f"{case_dir.name}.wav",
                    websocket_url=server.websocket_url,
                    http_base_url=server.http_base_url,
                    with_vad=effective_test_config.with_vad,
                    vad_redemption_ms=effective_test_config.vad_redemption_ms,
                    settle_seconds=DEFAULT_SETTLE_SECONDS,
                )
                await runner.run()

        try:
            await asyncio.gather(*(run_one_case(case_dir) for case_dir in case_dirs))
        finally:
            shutil.rmtree(temp_recording_root, ignore_errors=True)


def resolve_create_output_root(source_root: Path, requested_out: Path) -> Path:
    """Resolve the actual root folder for generated test cases."""
    if not requested_out.exists():
        return requested_out
    if not requested_out.is_dir():
        raise ValueError(f"Output path exists and is not a directory: {requested_out}")
    return requested_out / source_root.name


def load_tts_from_config(config_path: Path):
    """Instantiate a TTS model from a config file using Xtalk's registry."""
    raw_config = load_json(config_path)
    tts_config = raw_config.get("tts", raw_config)
    if not isinstance(tts_config, dict):
        raise ValueError(f"Invalid TTS config in {config_path}")
    return Xtalk._init_model(tts_config, Xtalk.MODEL_REGISTRY["tts"])


def run_create_mode(args: argparse.Namespace) -> None:
    """Generate a test dataset from text lines and a TTS configuration."""
    source_root = args.create.resolve()
    if not source_root.is_dir():
        raise ValueError(f"Generation source directory does not exist: {source_root}")

    test_config_path = resolve_root_json(
        source_root,
        preferred_names=PREFERRED_TEST_CONFIG_NAMES,
    )
    tts_config_path = resolve_root_json(
        source_root,
        preferred_names=PREFERRED_TTS_CONFIG_NAMES,
    )
    if tts_config_path is None:
        raise ValueError(f"No TTS config JSON found under {source_root}.")

    tts_model = load_tts_from_config(tts_config_path)
    if tts_model is None:
        raise RuntimeError("Failed to initialize TTS model from the provided config")

    output_root = resolve_create_output_root(source_root, args.out.resolve())
    output_root.mkdir(parents=True, exist_ok=True)
    if test_config_path is not None:
        shutil.copyfile(test_config_path, output_root / "test_config.json")

    sample_rate_hint = int(getattr(tts_model, "sample_rate", 48000) or 48000)
    for case_dir in discover_case_dirs(source_root):
        lines = parse_generation_case(case_dir)
        case_output_dir = output_root / case_dir.name
        case_output_dir.mkdir(parents=True, exist_ok=True)
        timestamp_lines: list[str] = []
        for index, line in enumerate(lines):
            audio_name = f"audio_{index:03d}.wav"
            audio_payload = tts_model.synthesize(line.text)
            pcm_bytes, sample_rate = decode_tts_audio_payload(
                audio_payload,
                sample_rate_hint=sample_rate_hint,
            )
            write_pcm_wav(
                case_output_dir / audio_name,
                pcm_bytes=pcm_bytes,
                sample_rate=sample_rate,
                channels=1,
            )
            timestamp_lines.append(f"{line.time_spec}:{audio_name}")

        (case_output_dir / "timestamp.txt").write_text(
            "\n".join(timestamp_lines) + "\n",
            encoding="utf-8",
        )


async def async_main(args: argparse.Namespace) -> None:
    """Dispatch to the requested mode."""
    if args.input is not None:
        await run_test_mode(args)
        return
    run_create_mode(args)


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
