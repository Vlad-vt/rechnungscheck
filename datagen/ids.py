"""Synthetic identifiers with valid check digits, drawn from ranges that do not
belong to real organisations or products where such ranges exist.

* GTIN-13 with GS1 prefix 200-299 ("restricted circulation", for internal use;
  never assigned to trade items).
* German IBANs with bank code (BLZ) starting with ``99``: syntactically valid
  (ISO 13616 mod-97), no real bank uses the 9xxxxxxx clearing area for accounts.
* German VAT ids (USt-IdNr) ``DE99xxxxxxx`` with a valid ISO 7064 MOD 11,10
  check digit. The format is valid; the numbers are random and unrelated to
  any real company.
"""

from __future__ import annotations

import random
import string


def gtin13_check_digit(first12: str) -> int:
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(first12))
    return (10 - total % 10) % 10


def make_gtin(rng: random.Random) -> str:
    body = f"2{rng.randint(0, 99):02d}" + "".join(rng.choice(string.digits) for _ in range(9))
    return body + str(gtin13_check_digit(body))


def gtin_is_valid(gtin: str) -> bool:
    return len(gtin) == 13 and gtin.isdigit() and gtin13_check_digit(gtin[:12]) == int(gtin[12])


def _iban_check(country: str, bban: str) -> str:
    rearranged = bban + country + "00"
    numeric = "".join(str(int(c, 36)) for c in rearranged)
    return f"{98 - int(numeric) % 97:02d}"


def make_de_iban(rng: random.Random) -> str:
    blz = "99" + "".join(rng.choice(string.digits) for _ in range(6))
    account = "".join(rng.choice(string.digits) for _ in range(10))
    bban = blz + account
    return f"DE{_iban_check('DE', bban)}{bban}"


def iban_is_valid(iban: str) -> bool:
    s = iban.replace(" ", "").upper()
    if len(s) < 15 or not s[:2].isalpha() or not s[2:4].isdigit():
        return False
    numeric = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    return int(numeric) % 97 == 1


def de_vat_check_digit(first8: str) -> int:
    product = 10
    for d in first8:
        total = (int(d) + product) % 10
        if total == 0:
            total = 10
        product = (2 * total) % 11
    check = 11 - product
    return 0 if check == 10 else check


def make_de_vat_id(rng: random.Random) -> str:
    first8 = "99" + "".join(rng.choice(string.digits) for _ in range(6))
    return f"DE{first8}{de_vat_check_digit(first8)}"


def make_bic(rng: random.Random) -> str:
    """BIC-shaped code with a made-up institution code (``XX`` location = test-like)."""
    inst = "".join(rng.choice(string.ascii_uppercase) for _ in range(4))
    return f"{inst}DEXX"
