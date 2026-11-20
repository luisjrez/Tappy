import os
import subprocess
import sys

VALID_SECRET = "synthetic-secret-key-for-tests-0123456789"
TAPPY_COMMAND = (sys.executable, "-m", "tappy")


def isolated_environment(environment: dict[str, str]) -> dict[str, str]:
    inherited = {key: value for key, value in os.environ.items() if not key.startswith("TAPPY_")}
    return {**inherited, **environment}


def run_tappy(environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        TAPPY_COMMAND,
        env=isolated_environment(environment),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def spawn_tappy(environment: dict[str, str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        TAPPY_COMMAND,
        env=isolated_environment(environment),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
