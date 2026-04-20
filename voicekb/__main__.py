from __future__ import annotations

import argparse
import signal
import threading
import time
from pathlib import Path

import numpy as np

from . import sdnotify
from .capture import RingRecorder
from .config import HOTKEY_PRESETS, Config
from .doctor import run as run_doctor
from .inject import InjectionError, inject
from .logging import get_logger
from .transcribe import Transcriber

_log = get_logger()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="voicekb")
    sub = p.add_subparsers(dest="cmd", required=True)

    def _add_run_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--hotkey",
            choices=sorted(HOTKEY_PRESETS),
            default="ctrl-shift-4",
        )
        sp.add_argument("--model", default="medium.en")
        sp.add_argument(
            "--adapter",
            choices=["evdev", "oxpctl"],
            default="evdev",
        )

    _add_run_args(sub.add_parser("run", help="foreground hold-to-talk hotkey listener"))
    _add_run_args(
        sub.add_parser(
            "run-daemon",
            help="systemd --user background service (same hotkey logic, daemonized)",
        )
    )

    sub.add_parser("doctor", help="read-only sanity checks")
    sub.add_parser("fetch-model", help="pre-cache the faster-whisper model")
    sub.add_parser("bench", help="record a 10s sample and measure RTF")

    return p


def _resolve_config(args: argparse.Namespace) -> Config:
    cfg = Config(hotkey=args.hotkey, model=args.model)
    resolved = str(Path(cfg.model_dir).expanduser().resolve())
    if resolved != cfg.model_dir:
        cfg = Config(hotkey=args.hotkey, model=args.model, model_dir=resolved)
    return cfg


def _warm_transcriber(t: Transcriber) -> None:
    _log.info("loading model…")
    t.load()
    silent = np.zeros(16_000, dtype=np.float32)
    t.transcribe(silent)
    _log.info("model ready")


def _build_callbacks(
    cfg: Config,
    recorder: RingRecorder,
    transcriber: Transcriber,
    state: dict[str, float | bool],
) -> tuple[callable, callable]:
    def on_press() -> None:
        if state["recording"]:
            return
        state["recording"] = True
        state["start_ts"] = time.monotonic()
        recorder.start()
        _log.info("recording… (hold %s)", cfg.hotkey)

    def on_release() -> None:
        if not state["recording"]:
            return
        state["recording"] = False
        audio = recorder.stop_and_drain()
        held_s = time.monotonic() - state["start_ts"]
        if audio.size < cfg.sample_rate_hz // 4:
            _log.info("held %.2fs — too short, skipped", held_s)
            return
        text, took_s, tokens = transcriber.transcribe(audio)
        if not text:
            _log.info("held %.2fs, transcribe %.2fs — empty", held_s, took_s)
            return
        try:
            inject(text)
        except InjectionError as exc:
            _log.error("injection failed: %s", exc)
            return
        _log.info("held %.2fs, transcribe %.2fs, %d tok", held_s, took_s, tokens)

    return on_press, on_release


def _cmd_run(cfg: Config, adapter: str) -> int:
    if adapter == "oxpctl":
        from . import hotkey_oxpctl as hk
    else:
        from . import hotkey_evdev as hk

    recorder = RingRecorder(cfg.sample_rate_hz, cfg.channels, cfg.max_utterance_s)
    transcriber = Transcriber(cfg)
    _warm_transcriber(transcriber)

    state: dict[str, float | bool] = {"recording": False, "start_ts": 0.0}
    on_press, on_release = _build_callbacks(cfg, recorder, transcriber, state)

    _log.info("ready — hold %s to dictate; Ctrl-C to quit", cfg.hotkey)
    try:
        hk.dispatch_hold_to_talk(cfg.hotkey_keys, on_press, on_release)
    except KeyboardInterrupt:
        _log.info("exiting")
    except Exception as exc:  # noqa: BLE001
        _log.error("fatal: %s", exc)
        return 1
    return 0


def _cmd_run_daemon(cfg: Config, adapter: str) -> int:
    if adapter == "oxpctl":
        from . import hotkey_oxpctl as hk
    else:
        from . import hotkey_evdev as hk

    shutdown = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        _log.info("received signal %d — shutting down", signum)
        shutdown.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    recorder = RingRecorder(cfg.sample_rate_hz, cfg.channels, cfg.max_utterance_s)
    transcriber = Transcriber(cfg)
    sdnotify.status("loading model")
    _warm_transcriber(transcriber)

    state: dict[str, float | bool] = {"recording": False, "start_ts": 0.0}
    on_press, on_release = _build_callbacks(cfg, recorder, transcriber, state)

    _log.info("ready — hold %s to dictate (daemon)", cfg.hotkey)
    sdnotify.ready()
    sdnotify.status(f"ready (hotkey: {cfg.hotkey})")
    try:
        hk.dispatch_hold_to_talk(
            cfg.hotkey_keys, on_press, on_release, should_stop=shutdown.is_set
        )
    except Exception as exc:  # noqa: BLE001
        _log.error("fatal: %s", exc)
        sdnotify.stopping()
        return 1
    sdnotify.stopping()
    _log.info("stopped cleanly")
    return 0


def _cmd_fetch_model(cfg: Config) -> int:
    _log.info("caching model %r into %s/…", cfg.model, cfg.model_dir)
    transcriber = Transcriber(cfg)
    transcriber.load()
    _log.info("model cached")
    return 0


def _cmd_bench(cfg: Config) -> int:
    duration = 10
    recorder = RingRecorder(cfg.sample_rate_hz, cfg.channels, duration + 2)
    transcriber = Transcriber(cfg)
    _warm_transcriber(transcriber)
    _log.info("bench: speak for %d seconds after the beep", duration)
    time.sleep(0.5)
    _log.info("GO")
    recorder.start()
    time.sleep(duration)
    audio = recorder.stop_and_drain()
    audio_s = audio.size / cfg.sample_rate_hz
    text, took_s, tokens = transcriber.transcribe(audio)
    rtf = took_s / max(audio_s, 0.001)
    _log.info(
        "bench: audio %.2fs, transcribe %.2fs, RTF=%.3f, %d tokens",
        audio_s,
        took_s,
        rtf,
        tokens,
    )
    _log.info("transcript: %r", text)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd in ("run", "run-daemon"):
        cfg = _resolve_config(args)
        if args.cmd == "run-daemon":
            return _cmd_run_daemon(cfg, args.adapter)
        return _cmd_run(cfg, args.adapter)
    if args.cmd == "doctor":
        return run_doctor(Config())
    if args.cmd == "fetch-model":
        return _cmd_fetch_model(Config())
    if args.cmd == "bench":
        return _cmd_bench(Config())
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
