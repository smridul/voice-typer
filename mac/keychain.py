"""Platform helpers for interacting with the macOS Keychain service."""

from __future__ import annotations

import ctypes
from ctypes import (
    POINTER,
    byref,
    c_bool,
    c_char_p,
    c_int32,
    c_long,
    c_uint32,
    c_void_p,
    create_string_buffer,
)
from ctypes.util import find_library

KEYCHAIN_SERVICE = "com.voicetyper.app"
KEYCHAIN_ACCOUNT = "groq_api_key"
KEYCHAIN_ITEM_NOT_FOUND = -25300
KEYCHAIN_DUPLICATE_ITEM = -25299

_SERVICE_BYTES = KEYCHAIN_SERVICE.encode("utf-8")
_ACCOUNT_BYTES = KEYCHAIN_ACCOUNT.encode("utf-8")
_SERVICE_LENGTH = len(_SERVICE_BYTES)
_ACCOUNT_LENGTH = len(_ACCOUNT_BYTES)
_KCFSTRING_ENCODING_UTF8 = 0x08000100


class KeychainError(RuntimeError):
    """Raised when Keychain operations fail."""


class _SecurityAPI:
    _initialized = False
    security: ctypes.CDLL | None = None
    core: ctypes.CDLL | None = None

    @classmethod
    def ensure_loaded(cls) -> None:
        if cls._initialized:
            return

        security_path = find_library("Security")
        core_path = find_library("CoreFoundation")
        if not security_path or not core_path:
            raise RuntimeError("Security frameworks are unavailable")

        cls.security = ctypes.CDLL(security_path)
        cls.core = ctypes.CDLL(core_path)
        cls._configure_functions()
        cls._initialized = True

    @classmethod
    def _configure_functions(cls) -> None:
        security = cls.security
        core = cls.core

        assert security is not None
        assert core is not None

        security.SecKeychainFindGenericPassword.argtypes = [
            c_void_p,
            c_uint32,
            c_char_p,
            c_uint32,
            c_char_p,
            POINTER(c_uint32),
            POINTER(c_void_p),
            POINTER(c_void_p),
        ]
        security.SecKeychainFindGenericPassword.restype = c_int32

        security.SecKeychainAddGenericPassword.argtypes = [
            c_void_p,
            c_uint32,
            c_char_p,
            c_uint32,
            c_char_p,
            c_uint32,
            c_void_p,
            POINTER(c_void_p),
        ]
        security.SecKeychainAddGenericPassword.restype = c_int32

        security.SecKeychainItemModifyAttributesAndData.argtypes = [
            c_void_p,
            c_void_p,
            c_uint32,
            c_void_p,
        ]
        security.SecKeychainItemModifyAttributesAndData.restype = c_int32

        security.SecKeychainItemFreeContent.argtypes = [c_void_p, c_void_p]
        security.SecKeychainItemFreeContent.restype = c_int32

        security.SecCopyErrorMessageString.argtypes = [c_int32, c_void_p]
        security.SecCopyErrorMessageString.restype = c_void_p

        core.CFStringGetCStringPtr.argtypes = [c_void_p, c_uint32]
        core.CFStringGetCStringPtr.restype = c_char_p

        core.CFStringGetCString.argtypes = [c_void_p, c_char_p, c_long, c_uint32]
        core.CFStringGetCString.restype = c_bool

        core.CFRelease.argtypes = [c_void_p]
        core.CFRelease.restype = None


def load_api_key() -> str | None:
    """Return the stored API key or None when the item is missing."""
    status, secret = _find_generic_password()

    if status == 0:
        return (secret or "").rstrip("\n")

    if status == KEYCHAIN_ITEM_NOT_FOUND:
        return None

    raise KeychainError(_format_error(status, "Keychain find operation"))


def save_api_key(api_key: str) -> None:
    """Write or update the API key in the Keychain."""
    api_key_bytes = api_key.encode("utf-8")

    status = _add_generic_password(api_key_bytes)
    if status == KEYCHAIN_DUPLICATE_ITEM:
        find_status, item_ref = _find_keychain_item_ref()
        if find_status != 0:
            raise KeychainError(_format_error(find_status, "Keychain find operation"))

        status = _update_existing_password(item_ref, api_key_bytes)

    if status != 0:
        raise KeychainError(_format_error(status, "Keychain write operation"))


def _find_generic_password() -> tuple[int, str | None]:
    _SecurityAPI.ensure_loaded()
    length = c_uint32()
    data = c_void_p()

    security = _SecurityAPI.security
    assert security is not None

    status = security.SecKeychainFindGenericPassword(
        None,
        _SERVICE_LENGTH,
        _SERVICE_BYTES,
        _ACCOUNT_LENGTH,
        _ACCOUNT_BYTES,
        byref(length),
        byref(data),
        None,
    )

    secret = None
    if status == 0 and data:
        raw = ctypes.string_at(data, length.value)
        secret = raw.decode("utf-8", errors="ignore")

    if data:
        security.SecKeychainItemFreeContent(None, data)

    return status, secret


def _find_keychain_item_ref() -> tuple[int, c_void_p]:
    _SecurityAPI.ensure_loaded()
    length = c_uint32()
    data = c_void_p()
    item_ref = c_void_p()

    security = _SecurityAPI.security
    assert security is not None

    status = security.SecKeychainFindGenericPassword(
        None,
        _SERVICE_LENGTH,
        _SERVICE_BYTES,
        _ACCOUNT_LENGTH,
        _ACCOUNT_BYTES,
        byref(length),
        byref(data),
        byref(item_ref),
    )

    if data:
        security.SecKeychainItemFreeContent(None, data)

    return status, item_ref


def _add_generic_password(api_key_bytes: bytes) -> int:
    _SecurityAPI.ensure_loaded()
    buffer = create_string_buffer(api_key_bytes)

    security = _SecurityAPI.security
    assert security is not None

    return security.SecKeychainAddGenericPassword(
        None,
        _SERVICE_LENGTH,
        _SERVICE_BYTES,
        _ACCOUNT_LENGTH,
        _ACCOUNT_BYTES,
        len(api_key_bytes),
        ctypes.cast(buffer, c_void_p),
        None,
    )


def _update_existing_password(item_ref: c_void_p, api_key_bytes: bytes) -> int:
    _SecurityAPI.ensure_loaded()
    buffer = create_string_buffer(api_key_bytes)
    security = _SecurityAPI.security
    core = _SecurityAPI.core
    assert security is not None
    assert core is not None

    try:
        return security.SecKeychainItemModifyAttributesAndData(
            item_ref,
            None,
            len(api_key_bytes),
            ctypes.cast(buffer, c_void_p),
        )
    finally:
        if item_ref:
            core.CFRelease(item_ref)


def _format_error(status: int, operation: str) -> str:
    message = _status_message(status)
    return message or f"{operation} failed with status {status}"


def _status_message(status: int) -> str | None:
    _SecurityAPI.ensure_loaded()
    security = _SecurityAPI.security
    core = _SecurityAPI.core
    assert security is not None
    assert core is not None

    message_ref = security.SecCopyErrorMessageString(status, None)
    if not message_ref:
        return None

    try:
        ptr = core.CFStringGetCStringPtr(message_ref, _KCFSTRING_ENCODING_UTF8)
        if ptr:
            return ptr.decode("utf-8")

        buffer = create_string_buffer(256)
        success = core.CFStringGetCString(
            message_ref,
            buffer,
            ctypes.sizeof(buffer),
            _KCFSTRING_ENCODING_UTF8,
        )
        if success:
            return buffer.value.decode("utf-8")
    finally:
        core.CFRelease(message_ref)

    return None
