import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_app


class BuildAppTests(unittest.TestCase):
    def test_pyinstaller_command_builds_windowed_bundle_from_main(self):
        python_bin = "/tmp/custom-python"

        command = build_app.pyinstaller_command(python_bin)

        self.assertEqual(command[0], python_bin)
        self.assertEqual(command[1:3], ["-m", "PyInstaller"])
        self.assertIn("--windowed", command)
        self.assertIn("--name", command)
        self.assertIn(build_app.APP_NAME, command)
        self.assertIn("--osx-bundle-identifier", command)
        self.assertIn(build_app.APP_BUNDLE_ID, command)
        self.assertEqual(
            command[-1],
            str(Path(build_app.__file__).resolve().parent / "main.py"),
        )

    def test_patch_info_plist_sets_required_bundle_fields(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plist_path = Path(tmp_dir) / "Info.plist"
            with plist_path.open("wb") as plist_file:
                plistlib.dump({}, plist_file)

            build_app.patch_info_plist(plist_path)

            with plist_path.open("rb") as plist_file:
                patched = plistlib.load(plist_file)

        self.assertIs(patched["LSUIElement"], True)
        self.assertEqual(patched["CFBundleDisplayName"], build_app.APP_NAME)
        self.assertEqual(
            patched["NSMicrophoneUsageDescription"],
            build_app.NS_MICROPHONE_USAGE_DESCRIPTION,
        )

    def test_mic_permission_helper_command_targets_app_bundle_binary(self):
        script_dir = Path(build_app.__file__).resolve().parent
        app_bundle = script_dir / "dist" / f"{build_app.APP_NAME}.app"

        command = build_app.mic_permission_helper_command(app_bundle)

        self.assertEqual(command[:2], ["xcrun", "swiftc"])
        self.assertEqual(command[-3], "-o")
        self.assertEqual(
            command[-2],
            str(app_bundle / "Contents" / "MacOS" / build_app.MIC_PERMISSION_HELPER_NAME),
        )
        self.assertEqual(
            command[-1],
            str(script_dir / build_app.MIC_PERMISSION_HELPER_SOURCE_NAME),
        )

    def test_codesign_command_resigns_app_bundle(self):
        script_dir = Path(build_app.__file__).resolve().parent
        app_bundle = script_dir / "dist" / f"{build_app.APP_NAME}.app"

        command = build_app.codesign_command(app_bundle)

        self.assertEqual(
            command,
            ["codesign", "--force", "--deep", "--sign", "-", str(app_bundle)],
        )

    @patch("build_app.patch_info_plist")
    @patch("build_app.subprocess.run")
    def test_build_app_runs_pyinstaller_then_patches_info_plist(self, run_mock, patch_mock):
        app_bundle = build_app.build_app("python3")

        script_dir = Path(build_app.__file__).resolve().parent
        expected_app_bundle = script_dir / "dist" / f"{build_app.APP_NAME}.app"
        expected_plist = (
            script_dir / "dist" / f"{build_app.APP_NAME}.app" / "Contents" / "Info.plist"
        )
        self.assertEqual(run_mock.call_count, 3)
        self.assertEqual(
            run_mock.call_args_list[0].kwargs,
            {"check": True, "cwd": script_dir},
        )
        self.assertEqual(
            run_mock.call_args_list[0].args[0],
            build_app.pyinstaller_command("python3"),
        )
        self.assertEqual(
            run_mock.call_args_list[1].kwargs,
            {"check": True, "cwd": script_dir},
        )
        self.assertEqual(
            run_mock.call_args_list[1].args[0],
            build_app.mic_permission_helper_command(expected_app_bundle),
        )
        self.assertEqual(
            run_mock.call_args_list[2].kwargs,
            {"check": True, "cwd": script_dir},
        )
        self.assertEqual(
            run_mock.call_args_list[2].args[0],
            build_app.codesign_command(expected_app_bundle),
        )
        patch_mock.assert_called_once_with(expected_plist)
        self.assertEqual(app_bundle, expected_app_bundle)


if __name__ == "__main__":
    unittest.main()
