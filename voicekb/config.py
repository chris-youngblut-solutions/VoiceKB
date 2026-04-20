from __future__ import annotations

from dataclasses import dataclass, field

HOTKEY_PRESETS: dict[str, tuple[str, ...]] = {
    "capslock": ("KEY_CAPSLOCK",),
    "ctrl-shift-4": ("KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_4"),
    "ctrl-shift-r-4": ("KEY_LEFTCTRL", "KEY_RIGHTSHIFT", "KEY_4"),
    "ctrl-shift-semicolon": ("KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_SEMICOLON"),
    "turbo": ("KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_LEFTMETA"),
}


@dataclass(frozen=True)
class Config:
    hotkey: str = "ctrl-shift-4"
    model: str = "medium.en"
    compute_type: str = "int8"
    language: str = "en"
    beam_size: int = 5
    vad_filter: bool = True
    sample_rate_hz: int = 16_000
    channels: int = 1
    max_utterance_s: int = 30
    model_dir: str = "./models"
    logfile: str | None = None
    hotkey_keys: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        if self.hotkey not in HOTKEY_PRESETS:
            raise ValueError(
                f"unknown hotkey preset {self.hotkey!r}; "
                f"choose from {sorted(HOTKEY_PRESETS)}"
            )
        object.__setattr__(self, "hotkey_keys", HOTKEY_PRESETS[self.hotkey])
