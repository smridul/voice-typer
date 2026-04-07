"""Platform helpers for interacting with the macOS Keychain service."""

from __future__ import annotations

import subprocess

KEYCHAIN_SERVICE = "com.voicetyper.app"
KEYCHAIN_ACCOUNT = "groq_api_key"


class KeychainError(RuntimeError):
    """Raised when Keychain operations fail."""


def load_api_key() -> str | None:
    """Return the stored API key or None when the item is missing."""
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-s",
            KEYCHAIN_SERVICE,
            "-a",
            KEYCHAIN_ACCOUNT,
            "-w",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        return result.stdout.strip()

    if result.returncode == 44:
        return None

    message = (
        result.stderr.strip()
        or "Keychain find operation failed with exit code "
        f"{result.returncode}"
    )
    raise KeychainError(message)


def save_api_key(api_key: str) -> None:
    """Write or update the API key in the Keychain."""
    result = subprocess.run(
        [
            "security",
            "add-generic-password",
            "-U",
            "-s",
            KEYCHAIN_SERVICE,
            "-a",
            KEYCHAIN_ACCOUNT,
            "-w",
            api_key,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        message = (
            result.stderr.strip()
            or "Keychain add operation failed with exit code "
            f"{result.returncode}"
        )
        raise KeychainError(message)
