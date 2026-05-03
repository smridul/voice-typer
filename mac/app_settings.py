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


@dataclass(frozen=True)
class AppSettings:
    context_language: str
    output_language: str
    input_device_name: Optional[str] = None


def _sanitize_language(code, fallback):
    return code if code in LANGUAGE_LABELS else fallback


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
    )


def save_settings(path, settings):
    payload = {
        "context_language": settings.context_language,
        "output_language": settings.output_language,
        "input_device_name": settings.input_device_name,
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
