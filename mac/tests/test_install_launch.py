import os
import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "install-launch.sh"
INSTALLED_APP_BUNDLE = "/Applications/VoiceTyper.app"
INSTALLED_APP_BINARY = "/Applications/VoiceTyper.app/Contents/MacOS/VoiceTyper"


class InstallLaunchScriptTests(unittest.TestCase):
    def test_fails_when_installed_app_bundle_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp_home:
            nonexistent_app_binary = (
                Path(tmp_home) / "not-installed" / "VoiceTyper.app" / "Contents" / "MacOS" / "VoiceTyper"
            )
            env = os.environ.copy()
            env["HOME"] = tmp_home
            env["VOICETYPER_APP_BINARY_CHECK"] = str(nonexistent_app_binary)

            result = subprocess.run(
                ["bash", str(SCRIPT_PATH)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            f"Missing installed app executable at {INSTALLED_APP_BINARY}",
            result.stderr,
        )

    def test_generates_launch_agent_targeting_installed_app_bundle(self):
        with tempfile.TemporaryDirectory() as tmp_home, tempfile.TemporaryDirectory() as tmp_bin:
            home_path = Path(tmp_home)
            app_binary = home_path / "Applications" / "VoiceTyper.app" / "Contents" / "MacOS" / "VoiceTyper"
            app_binary.parent.mkdir(parents=True, exist_ok=True)
            app_binary.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
            app_binary.chmod(0o755)

            launchctl_path = Path(tmp_bin) / "launchctl"
            launchctl_path.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
            launchctl_path.chmod(0o755)

            env = os.environ.copy()
            env["HOME"] = str(home_path)
            env["PATH"] = f"{tmp_bin}:{env['PATH']}"
            env["VOICETYPER_APP_BINARY_CHECK"] = str(app_binary)

            result = subprocess.run(
                ["bash", str(SCRIPT_PATH)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )

            plist_path = home_path / "Library" / "LaunchAgents" / "com.voicetyper.plist"
            with plist_path.open("rb") as plist_file:
                plist_data = plistlib.load(plist_file)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(
            plist_data["ProgramArguments"],
            [INSTALLED_APP_BINARY],
        )


if __name__ == "__main__":
    unittest.main()
