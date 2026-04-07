from __future__ import annotations

import shutil
from pathlib import Path

APP_SUPPORT_SUBDIR = "VoiceTyper"
SETTINGS_FILENAME = "settings.json"


def _resolve_home_dir(home_dir: Path | str | None = None) -> Path:
    if home_dir is None:
        return Path.home()
    return Path(home_dir).expanduser()


def application_support_dir(home_dir: Path | str | None = None) -> Path:
    home = _resolve_home_dir(home_dir)
    return home / "Library" / "Application Support" / APP_SUPPORT_SUBDIR


def ensure_application_support_dir(home_dir: Path | str | None = None) -> Path:
    directory = application_support_dir(home_dir=home_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def settings_path(home_dir: Path | str | None = None) -> Path:
    return application_support_dir(home_dir=home_dir) / SETTINGS_FILENAME


def legacy_settings_path(repo_dir: Path | str | None = None) -> Path:
    if repo_dir is None:
        repo_dir = Path(__file__).resolve().parent
    return Path(repo_dir) / SETTINGS_FILENAME


def migrate_legacy_settings_if_needed(
    home_dir: Path | str | None = None,
    repo_dir: Path | str | None = None,
) -> Path:
    target = settings_path(home_dir=home_dir)
    if target.exists():
        return target

    source = legacy_settings_path(repo_dir=repo_dir)
    if not source.exists():
        ensure_application_support_dir(home_dir=home_dir)
        return target

    ensure_application_support_dir(home_dir=home_dir)
    shutil.copy2(source, target)
    return target
