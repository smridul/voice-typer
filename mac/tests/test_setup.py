import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "setup.sh"


class SetupScriptTests(unittest.TestCase):
    def test_non_interactive_setup_uses_env_key_and_pipes_secret_over_stdin(self):
        with tempfile.TemporaryDirectory() as tmp_home, tempfile.TemporaryDirectory() as tmp_bin:
            home_path = Path(tmp_home)
            bin_path = Path(tmp_bin)
            python_args_log = home_path / "python-args.log"
            python_stdin_log = home_path / "python-stdin.log"

            fake_python = bin_path / "python3"
            fake_python.write_text(
                textwrap.dedent(
                    f"""\
                    #!/bin/bash
                    set -e
                    for arg in "$@"; do
                        printf '%s\n' "$arg" >> "{python_args_log}"
                    done
                    printf '%s\n' '---' >> "{python_args_log}"

                    if [ "$1" = "--version" ]; then
                        echo "Python 3.12.0"
                        exit 0
                    fi

                    if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then
                        exit 0
                    fi

                    if [ "$1" = "-c" ]; then
                        cat > "{python_stdin_log}"
                        exit 0
                    fi

                    echo "Unexpected python3 invocation: $*" >&2
                    exit 1
                    """
                ),
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            api_key = "gsk_test_non_interactive"
            env = os.environ.copy()
            env["HOME"] = str(home_path)
            env["PATH"] = f"{bin_path}:{env['PATH']}"
            env["GROQ_API_KEY"] = api_key

            result = subprocess.run(
                ["bash", str(SCRIPT_PATH)],
                capture_output=True,
                text=True,
                env=env,
                cwd=home_path,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("Using GROQ_API_KEY from environment", result.stdout)

            args_text = python_args_log.read_text(encoding="utf-8")
            self.assertIn("-m", args_text)
            self.assertIn("pip", args_text)
            self.assertIn("install", args_text)
            self.assertIn("-r", args_text)
            self.assertIn(
                str(SCRIPT_PATH.parent / "requirements.txt"),
                args_text,
            )
            self.assertIn("-c", args_text)
            self.assertNotIn(api_key, args_text)

            self.assertEqual(
                python_stdin_log.read_text(encoding="utf-8"),
                api_key,
            )


if __name__ == "__main__":
    unittest.main()
