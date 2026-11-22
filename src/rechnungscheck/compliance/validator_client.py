"""Client for the KoSIT validator daemon (internal container, ADR 0003).

POST raw XML, read the verdict from the HTTP status and the rule messages from
the report: 200 = acceptable, 406 = not acceptable. If no configured scenario
matches (e.g. ZUGFeRD BASIC / EXTENDED, older XRechnung versions), the verdict is
``unsupported``: the validator cannot judge the file, which is not the same as
invalid. The Compliance Checker then relies on its own rules and flags the gap.
"""

from __future__ import annotations

from enum import StrEnum

import httpx
from lxml import etree
from pydantic import BaseModel, ConfigDict

from rechnungscheck.extraction.xmlsafe import parse_xml

REP_NS = "http://www.xoev.de/de/validator/varl/1"


class Verdict(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    UNSUPPORTED = "unsupported"


class RuleMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str | None
    level: str
    text: str
    location: str | None = None


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict: Verdict
    scenario: str | None
    messages: tuple[RuleMessage, ...]

    @property
    def errors(self) -> tuple[RuleMessage, ...]:
        return tuple(m for m in self.messages if m.level in {"error", "fatal"})


class ValidatorError(RuntimeError):
    pass


def parse_report(status: int, body: bytes) -> ValidationReport:
    if status not in {200, 406}:
        raise ValidatorError(f"validator returned HTTP {status}")
    root = parse_xml(body)
    ns = {"rep": REP_NS, "s": "http://www.xoev.de/de/validator/framework/1/scenarios"}
    if root.find(f"{{{REP_NS}}}noScenarioMatched") is not None:
        return ValidationReport(verdict=Verdict.UNSUPPORTED, scenario=None, messages=())
    names = root.xpath("rep:scenarioMatched/s:scenario/s:name/text()", namespaces=ns)
    scenario = str(names[0]) if isinstance(names, list) and names else None
    msgs = []
    for m in root.iter(f"{{{REP_NS}}}message"):
        assert isinstance(m, etree._Element)  # noqa: S101
        msgs.append(
            RuleMessage(
                code=m.get("code"),
                level=m.get("level", "error"),
                text=" ".join((m.text or "").split()),
                location=m.get("xpathLocation"),
            )
        )
    verdict = Verdict.ACCEPT if status == 200 else Verdict.REJECT  # noqa: PLR2004
    return ValidationReport(verdict=verdict, scenario=scenario, messages=tuple(msgs))


class KositClient:
    def __init__(self, base_url: str, timeout: float = 60.0, client: httpx.Client | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    def validate(self, xml: bytes, name: str = "invoice.xml") -> ValidationReport:
        resp = self._client.post(
            f"{self._base}/{name}", content=xml, headers={"Content-Type": "application/xml"}
        )
        return parse_report(resp.status_code, resp.content)

    def healthy(self) -> bool:
        try:
            return self._client.get(f"{self._base}/server/health").status_code == 200  # noqa: PLR2004
        except httpx.HTTPError:
            return False
