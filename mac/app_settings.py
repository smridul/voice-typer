import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_CONTEXT_LANGUAGE = "en"
DEFAULT_OUTPUT_LANGUAGE = "en"
LANGUAGE_LABELS = {"en": "English", "hi": "Hindi", "es": "Spanish", "zh": "Chinese"}
LANGUAGE_CODES_BY_LABEL = {"English": "en", "Hindi": "hi", "Spanish": "es", "Chinese": "zh"}

# How long the mic stream stays open after a recording. Bluetooth mics need
# several seconds to start sending audio, so a warm stream makes the next
# recording start instantly. 0 = close right away, MIC_WARM_ALWAYS = never.
MIC_WARM_ALWAYS = -1
DEFAULT_MIC_WARM_SECONDS = 180
MIC_WARM_LABELS = {
    0: "Off",
    60: "1 Minute",
    180: "3 Minutes",
    600: "10 Minutes",
    1800: "30 Minutes",
    MIC_WARM_ALWAYS: "Always",
}


@dataclass(frozen=True)
class AppSettings:
    context_language: str
    output_language: str
    input_device_name: Optional[str] = None
    show_record_button: bool = True
    mic_warm_seconds: int = DEFAULT_MIC_WARM_SECONDS


def _sanitize_language(code, fallback):
    return code if code in LANGUAGE_LABELS else fallback


def _sanitize_mic_warm_seconds(value):
    # bool is an int subclass; JSON true must not become a 1-second window.
    if isinstance(value, int) and not isinstance(value, bool):
        if value >= 0 or value == MIC_WARM_ALWAYS:
            return value
    return DEFAULT_MIC_WARM_SECONDS


def _default_settings():
    return AppSettings(
        context_language=DEFAULT_CONTEXT_LANGUAGE,
        output_language=DEFAULT_OUTPUT_LANGUAGE,
        input_device_name=None,
    )


def load_settings(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        return _default_settings()

    if not isinstance(payload, dict):
        return _default_settings()

    raw_device = payload.get("input_device_name")
    input_device_name = raw_device if isinstance(raw_device, str) else None
    raw_show_button = payload.get("show_record_button")
    show_record_button = raw_show_button if isinstance(raw_show_button, bool) else True

    return AppSettings(
        context_language=_sanitize_language(
            payload.get("context_language"),
            DEFAULT_CONTEXT_LANGUAGE,
        ),
        output_language=_sanitize_language(
            payload.get("output_language"),
            DEFAULT_OUTPUT_LANGUAGE,
        ),
        input_device_name=input_device_name,
        show_record_button=show_record_button,
        mic_warm_seconds=_sanitize_mic_warm_seconds(payload.get("mic_warm_seconds")),
    )


def save_settings(path, settings):
    payload = {
        "context_language": settings.context_language,
        "output_language": settings.output_language,
        "input_device_name": settings.input_device_name,
        "show_record_button": settings.show_record_button,
        "mic_warm_seconds": settings.mic_warm_seconds,
    }
    settings_path = Path(path)
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=settings_path.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(json.dumps(payload))

        os.replace(temp_path, settings_path)
    except Exception:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
        raise
