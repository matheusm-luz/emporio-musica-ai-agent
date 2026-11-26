"""Stop hook: Claude may only finish a turn while the offline unit tests pass.

Exit code 2 blocks the stop and feeds the failing output back to Claude. The `stop_hook_active`
flag prevents an endless loop when Claude is already continuing because of this hook.
"""

import json
import subprocess
import sys

NO_TESTS_COLLECTED = 5


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return 0

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    if result.returncode in (0, NO_TESTS_COLLECTED):
        return 0
    tail = "\n".join((result.stdout + result.stderr).splitlines()[-40:])
    print(f"Unit tests are failing — fix them before finishing:\n{tail}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
