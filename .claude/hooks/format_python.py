"""PostToolUse hook: format and lint every Python file Claude edits.

Reads the hook payload from stdin. Exit code 2 feeds remaining lint errors back to Claude.
"""

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path", "")
    path = Path(file_path)
    if path.suffix != ".py" or not path.exists():
        return 0

    subprocess.run([sys.executable, "-m", "ruff", "format", "--quiet", str(path)], check=False)
    lint = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--fix", "--quiet", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if lint.returncode != 0:
        print(f"ruff found issues in {path}:\n{lint.stdout}{lint.stderr}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
