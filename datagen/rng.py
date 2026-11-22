"""Deterministic, platform-independent random streams."""

from __future__ import annotations

import random
import zlib


def stream(seed: int, *labels: str) -> random.Random:
    """Independent RNG per (seed, labels). Uses CRC32, not ``hash()``, so results do not
    depend on PYTHONHASHSEED or the platform."""
    key = "|".join((str(seed), *labels)).encode("utf-8")
    return random.Random(zlib.crc32(key) ^ (seed * 2654435761 & 0xFFFFFFFF))
