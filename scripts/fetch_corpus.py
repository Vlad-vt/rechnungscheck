"""Clone the public ZUGFeRD corpus (Apache-2.0) at a pinned commit into data/corpus.

The corpus is not vendored into this repository: some files are third-party
samples whose individual provenance was not verified (ADR 0003), so it is
fetched on demand and stays out of git (data/ is ignored).
"""

import subprocess
import sys
from pathlib import Path

URL = "https://github.com/ZUGFeRD/corpus"
COMMIT = "02d4b5684738cb2d9faac2cec6599dc0e86c16d5"  # 2026-11-19, used for ADR 0003
DEST = Path(__file__).resolve().parents[1] / "data" / "corpus"


def git(*args: str) -> None:
    subprocess.run(["git", *args], check=True)  # noqa: S603, S607


def main() -> None:
    if not DEST.exists():
        DEST.parent.mkdir(parents=True, exist_ok=True)
        git("clone", "--filter=blob:none", "--no-checkout", URL, str(DEST))
    git("-C", str(DEST), "fetch", "--depth", "1", "origin", COMMIT)
    git("-C", str(DEST), "checkout", "--detach", COMMIT)
    print(f"corpus at {COMMIT} in {DEST}")


if __name__ == "__main__":
    sys.exit(main())
