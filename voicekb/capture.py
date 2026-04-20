from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd

from .logging import get_logger

_log = get_logger()


class RingRecorder:
    """RAM-only ring buffer recorder. Audio never touches disk."""

    def __init__(self, sample_rate_hz: int, channels: int, max_seconds: int) -> None:
        self._sr = sample_rate_hz
        self._channels = channels
        self._capacity = sample_rate_hz * max_seconds
        self._buf = np.zeros(self._capacity, dtype=np.float32)
        self._write = 0
        self._full = False
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    def _on_audio(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            _log.warning("capture status: %s", status)
        chunk = indata[:, 0] if indata.ndim == 2 else indata
        with self._lock:
            end = self._write + len(chunk)
            if end <= self._capacity:
                self._buf[self._write : end] = chunk
            else:
                first = self._capacity - self._write
                self._buf[self._write :] = chunk[:first]
                self._buf[: len(chunk) - first] = chunk[first:]
                self._full = True
            self._write = end % self._capacity

    def start(self) -> None:
        with self._lock:
            self._buf.fill(0.0)
            self._write = 0
            self._full = False
        self._stream = sd.InputStream(
            samplerate=self._sr,
            channels=self._channels,
            dtype="float32",
            callback=self._on_audio,
        )
        self._stream.start()

    def stop_and_drain(self) -> np.ndarray:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        with self._lock:
            if self._full:
                audio = np.concatenate(
                    (self._buf[self._write :], self._buf[: self._write])
                )
            else:
                audio = self._buf[: self._write].copy()
            self._buf.fill(0.0)
            self._write = 0
            self._full = False
        return audio

    @property
    def sample_rate(self) -> int:
        return self._sr
