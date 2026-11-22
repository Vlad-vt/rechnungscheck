"""Print Makefile targets that carry a ``## description`` comment (cross-platform ``make help``)."""

import re
import sys
from pathlib import Path

PATTERN = re.compile(r"^([a-zA-Z_-]+):.*?## (.*)$")

for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if m := PATTERN.match(line):
        print(f"  {m.group(1):<18} {m.group(2)}")
