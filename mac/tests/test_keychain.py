import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from keychain import KeychainError, load_api_key, save_api_key


class KeychainTests(unittest.TestCase):
    @patch("keychain._run_security")
    def test_load_api_key_returns_secret(self, run_security_mock):
        run_security_mock.return_value = CompletedProcess(
            args=["security"],
            returncode=0,
            stdout="secret\n",
            stderr="",
        )

        self.assertEqual(load_api_key(), "secret")

    @patch("keychain._run_security")
    def test_load_api_key_missing_returns_none(self, run_security_mock):
        run_security_mock.return_value = CompletedProcess(
            args=["security"],
            returncode=44,
            stdout="",
            stderr="security: SecKeychainSearchCopyNext: The specified item could not be found in the keychain.\n",
        )

        self.assertIsNone(load_api_key())

    @patch("keychain._run_security")
    def test_load_api_key_raises_on_error_status(self, run_security_mock):
        run_security_mock.return_value = CompletedProcess(
            args=["security"],
            returncode=1,
            stdout="",
            stderr="security: failed\n",
        )

        with self.assertRaises(KeychainError) as ctx:
            load_api_key()

        self.assertIn("security: failed", str(ctx.exception))

    @patch("keychain._run_security")
    def test_save_api_key_adds_new_item(self, run_security_mock):
        run_security_mock.return_value = CompletedProcess(
            args=["security"],
            returncode=0,
            stdout="",
            stderr="password data for new item:\nretype password for new item:\n",
        )

        save_api_key("new-secret")

        run_security_mock.assert_called_once()
        args, kwargs = run_security_mock.call_args
        self.assertEqual(
            args[0],
            [
                "add-generic-password",
                "-U",
                "-a",
                "groq_api_key",
                "-s",
                "com.voicetyper.app",
                "-w",
            ],
        )
        self.assertEqual(kwargs["input_text"], "new-secret\nnew-secret\n")

    @patch("keychain._run_security")
    def test_save_api_key_raises_on_failure(self, run_security_mock):
        run_security_mock.return_value = CompletedProcess(
            args=["security"],
            returncode=1,
            stdout="",
            stderr="security: write failed\n",
        )

        with self.assertRaises(KeychainError) as ctx:
            save_api_key("ignored")

        self.assertIn("security: write failed", str(ctx.exception))

    @patch("keychain._run_security")
    def test_security_cli_unavailable_falls_back_to_native_load(self, run_security_mock):
        run_security_mock.side_effect = FileNotFoundError()

        with patch("keychain._find_generic_password", return_value=(0, "native-secret\n")) as find_mock:
            self.assertEqual(load_api_key(), "native-secret")

        find_mock.assert_called_once()

    @patch("keychain._run_security")
    def test_security_cli_unavailable_falls_back_to_native_save(self, run_security_mock):
        run_security_mock.side_effect = FileNotFoundError()

        with patch("keychain._add_generic_password", return_value=0) as add_mock:
            save_api_key("native-secret")

        add_mock.assert_called_once_with(b"native-secret")


if __name__ == "__main__":
    unittest.main()
