"""Run the dataset generator in its pinned container (canonical bytes, ADR 0004).

Usage: ``uv run python scripts/datagen_docker.py generate`` (or ``verify``, extra args passed through).
Works the same on Windows (Docker Desktop) and Linux; on Linux the container runs as the
caller's uid/gid so generated files are not owned by root.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "rechnungscheck/datagen:dev"


def main() -> int:
    args = sys.argv[1:] or ["generate"]
    subprocess.run(  # noqa: S603
        ["docker", "build", "-q", "-t", IMAGE, "-f", str(ROOT / "datagen" / "Dockerfile"), str(ROOT)],  # noqa: S607
        check=True,
        stdout=subprocess.DEVNULL,
    )
    user: list[str] = []
    if hasattr(os, "getuid"):
        user = ["--user", f"{os.getuid()}:{os.getgid()}"]
    cmd = ["docker", "run", "--rm", "--network", "none", *user, "-v", f"{ROOT}:/work", IMAGE, *args]
    return subprocess.run(cmd, check=False).returncode  # noqa: S603


if __name__ == "__main__":
    sys.exit(main())
