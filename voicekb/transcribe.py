from __future__ import annotations

import time

import numpy as np
from faster_whisper import WhisperModel

from .config import Config


class Transcriber:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._model: WhisperModel | None = None

    def load(self) -> None:
        if self._model is None:
            self._model = WhisperModel(
                self._cfg.model,
                device="cpu",
                compute_type=self._cfg.compute_type,
                download_root=self._cfg.model_dir,
            )

    def transcribe(self, audio: np.ndarray) -> tuple[str, float, int]:
        if self._model is None:
            self.load()
        assert self._model is not None
        t0 = time.monotonic()
        segments_iter, _info = self._model.transcribe(
            audio,
            language=self._cfg.language,
            beam_size=self._cfg.beam_size,
            vad_filter=self._cfg.vad_filter,
            condition_on_previous_text=False,
        )
        parts: list[str] = []
        tokens = 0
        for seg in segments_iter:
            parts.append(seg.text)
            tokens += len(seg.text.split())
        text = " ".join(p.strip() for p in parts).strip()
        return text, time.monotonic() - t0, tokens
