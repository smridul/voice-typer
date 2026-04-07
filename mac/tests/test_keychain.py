import unittest
from unittest.mock import Mock, patch

from keychain import (
    KEYCHAIN_ACCOUNT,
    KEYCHAIN_SERVICE,
    KeychainError,
    load_api_key,
    save_api_key,
)


class KeychainTests(unittest.TestCase):
    @patch("keychain.subprocess.run")
    def test_load_api_key_returns_secret(self, run_mock):
        run_mock.return_value = Mock(returncode=0, stdout="secret\n", stderr="")

        result = load_api_key()

        self.assertEqual(result, "secret")
        run_mock.assert_called_once_with(
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

    @patch("keychain.subprocess.run")
    def test_load_api_key_missing_returns_none(self, run_mock):
        run_mock.return_value = Mock(returncode=44, stdout="", stderr="")

        result = load_api_key()

        self.assertIsNone(result)

    @patch("keychain.subprocess.run")
    def test_save_api_key_updates_existing_entry(self, run_mock):
        run_mock.return_value = Mock(returncode=0, stdout="", stderr="")

        save_api_key("new-secret")

        run_mock.assert_called_once_with(
            [
                "security",
                "add-generic-password",
                "-U",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                KEYCHAIN_ACCOUNT,
                "-w",
                "new-secret",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("keychain.subprocess.run")
    def test_save_api_key_raises_on_failure(self, run_mock):
        run_mock.return_value = Mock(returncode=1, stdout="", stderr="permission denied")

        with self.assertRaises(KeychainError) as ctx:
            save_api_key("ignored")

        self.assertIn("permission denied", str(ctx.exception))
