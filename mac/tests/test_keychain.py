import unittest
from unittest.mock import patch

from keychain import (
    KEYCHAIN_DUPLICATE_ITEM,
    KEYCHAIN_ITEM_NOT_FOUND,
    KeychainError,
    load_api_key,
    save_api_key,
)


class KeychainTests(unittest.TestCase):
    @patch("keychain._find_generic_password")
    def test_load_api_key_returns_secret(self, find_mock):
        find_mock.return_value = (0, "secret\n")

        self.assertEqual(load_api_key(), "secret")

    @patch("keychain._find_generic_password")
    def test_load_api_key_missing_returns_none(self, find_mock):
        find_mock.return_value = (KEYCHAIN_ITEM_NOT_FOUND, None)

        self.assertIsNone(load_api_key())

    @patch("keychain._find_generic_password")
    @patch("keychain._status_message")
    def test_load_api_key_raises_on_error_status(self, status_mock, find_mock):
        find_mock.return_value = (1, None)
        status_mock.return_value = None

        with self.assertRaises(KeychainError) as ctx:
            load_api_key()

        self.assertIn("status 1", str(ctx.exception))

    @patch("keychain._add_generic_password")
    def test_save_api_key_adds_new_item(self, add_mock):
        add_mock.return_value = 0

        save_api_key("new-secret")

        add_mock.assert_called_once_with(b"new-secret")

    @patch("keychain._add_generic_password")
    @patch("keychain._find_keychain_item_ref")
    @patch("keychain._update_existing_password")
    def test_save_api_key_updates_existing_entry(self, update_mock, find_mock, add_mock):
        add_mock.return_value = KEYCHAIN_DUPLICATE_ITEM
        sentinel = object()
        find_mock.return_value = (0, sentinel)
        update_mock.return_value = 0

        save_api_key("new-secret")

        add_mock.assert_called_once_with(b"new-secret")
        update_mock.assert_called_once_with(sentinel, b"new-secret")
        find_mock.assert_called_once()

    @patch("keychain._status_message")
    @patch("keychain._add_generic_password")
    def test_save_api_key_raises_on_failure(self, add_mock, status_mock):
        add_mock.return_value = 5
        status_mock.return_value = None

        with self.assertRaises(KeychainError) as ctx:
            save_api_key("ignored")

        self.assertIn("status 5", str(ctx.exception))
