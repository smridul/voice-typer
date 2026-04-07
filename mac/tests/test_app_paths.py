import tempfile
import unittest
from pathlib import Path

from app_paths import (
    APP_SUPPORT_SUBDIR,
    SETTINGS_FILENAME,
    ensure_application_support_dir,
    legacy_settings_path,
    migrate_legacy_settings_if_needed,
    settings_path,
)


class AppPathsTests(unittest.TestCase):
    def test_settings_path_uses_application_support(self):
        with tempfile.TemporaryDirectory() as tmp_home:
            home_dir = Path(tmp_home)
            expected = (
                home_dir
                / "Library"
                / "Application Support"
                / APP_SUPPORT_SUBDIR
                / SETTINGS_FILENAME
            )

            self.assertEqual(settings_path(home_dir=home_dir), expected)

    def test_migrate_legacy_settings_if_needed_copies_repo_local_settings_once(self):
        with tempfile.TemporaryDirectory() as tmp_home, tempfile.TemporaryDirectory() as tmp_repo:
            home_dir = Path(tmp_home)
            repo_dir = Path(tmp_repo)
            legacy_file = legacy_settings_path(repo_dir=repo_dir)
            legacy_file.write_text('{"legacy":"value"}', encoding="utf-8")

            migrated = migrate_legacy_settings_if_needed(home_dir=home_dir, repo_dir=repo_dir)
            dest = settings_path(home_dir=home_dir)

            self.assertEqual(migrated, dest)
            self.assertTrue(dest.exists())
            self.assertEqual(dest.read_text(encoding="utf-8"), '{"legacy":"value"}')

            legacy_file.write_text('{"legacy":"new"}', encoding="utf-8")
            second_migration = migrate_legacy_settings_if_needed(home_dir=home_dir, repo_dir=repo_dir)

            self.assertEqual(second_migration, dest)
            self.assertEqual(dest.read_text(encoding="utf-8"), '{"legacy":"value"}')

    def test_existing_application_support_settings_win_over_legacy_file(self):
        with tempfile.TemporaryDirectory() as tmp_home, tempfile.TemporaryDirectory() as tmp_repo:
            home_dir = Path(tmp_home)
            repo_dir = Path(tmp_repo)

            ensure_application_support_dir(home_dir=home_dir)
            dest = settings_path(home_dir=home_dir)
            dest.write_text('{"existing":"value"}', encoding="utf-8")

            legacy_file = legacy_settings_path(repo_dir=repo_dir)
            legacy_file.write_text('{"legacy":"value"}', encoding="utf-8")

            result = migrate_legacy_settings_if_needed(home_dir=home_dir, repo_dir=repo_dir)

            self.assertEqual(result, dest)
            self.assertEqual(dest.read_text(encoding="utf-8"), '{"existing":"value"}')


if __name__ == "__main__":
    unittest.main()
