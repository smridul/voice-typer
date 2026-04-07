from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path

APP_NAME = "VoiceTyper"
APP_BUNDLE_ID = "com.voicetyper.app"
NS_MICROPHONE_USAGE_DESCRIPTION = "VoiceTyper needs microphone access to transcribe speech."
MIC_PERMISSION_HELPER_NAME = "VoiceTyperMicPermission"
MIC_PERMISSION_HELPER_SOURCE_NAME = "mic_permission_helper.swift"


def _repo_dir() -> Path:
    return Path(__file__).resolve().parent


def pyinstaller_command(python_bin: str) -> list[str]:
    return [
        python_bin,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--osx-bundle-identifier",
        APP_BUNDLE_ID,
        str(_repo_dir() / "main.py"),
    ]


def patch_info_plist(plist_path: Path) -> None:
    plist_path = Path(plist_path)
    with plist_path.open("rb") as plist_file:
        plist_data = plistlib.load(plist_file)

    plist_data["LSUIElement"] = True
    plist_data["CFBundleDisplayName"] = APP_NAME
    plist_data["NSMicrophoneUsageDescription"] = NS_MICROPHONE_USAGE_DESCRIPTION

    with plist_path.open("wb") as plist_file:
        plistlib.dump(plist_data, plist_file)


def mic_permission_helper_command(app_bundle_path: Path) -> list[str]:
    helper_output = Path(app_bundle_path) / "Contents" / "MacOS" / MIC_PERMISSION_HELPER_NAME
    helper_source = _repo_dir() / MIC_PERMISSION_HELPER_SOURCE_NAME
    return [
        "xcrun",
        "swiftc",
        "-framework",
        "Foundation",
        "-framework",
        "AVFAudio",
        "-o",
        str(helper_output),
        str(helper_source),
    ]


def codesign_command(app_bundle_path: Path) -> list[str]:
    return ["codesign", "--force", "--deep", "--sign", "-", str(app_bundle_path)]


def build_app(python_bin: str) -> Path:
    repo_dir = _repo_dir()
    subprocess.run(pyinstaller_command(python_bin), check=True, cwd=repo_dir)

    app_bundle_path = repo_dir / "dist" / f"{APP_NAME}.app"
    plist_path = app_bundle_path / "Contents" / "Info.plist"
    patch_info_plist(plist_path)
    subprocess.run(mic_permission_helper_command(app_bundle_path), check=True, cwd=repo_dir)
    subprocess.run(codesign_command(app_bundle_path), check=True, cwd=repo_dir)
    return app_bundle_path


if __name__ == "__main__":
    selected_python = sys.argv[1] if len(sys.argv) > 1 else "python3"
    build_app(selected_python)
