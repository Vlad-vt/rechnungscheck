"""Compare the KoSIT and Mustang validators (ADR 0003).

Inputs:
* the public ZUGFeRD corpus (github.com/ZUGFeRD/corpus, Apache-2.0), cloned to
  ``data/corpus``: expectation from the directory (``fail/`` = invalid, else valid);
* the generated XRechnung (CII, UBL) and ZUGFeRD files: expectation from the labels.
  Per EN 16931 / XRechnung rules a generated file is invalid only if BT-10 is missing
  (BR-DE-15, XRechnung only) or the total with VAT is wrong (BR-CO-15). Other labelled
  problems (wrong VAT rate, line arithmetic, short delivery ...) are business errors
  that no syntax/semantics validator can see; they are reported per label type.

Requires the compose ``validator`` service (KoSIT daemon on 127.0.0.1:8081) and the
``rechnungscheck/validator-mustang:dev`` image. Run: ``make compare-validators``.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from lxml import etree

from datagen.models import Case, DiscrepancyType
from rechnungscheck.extraction.router import embedded_invoice_xml

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT_DIR = ROOT / "evals" / "results" / "validator_comparison"
KOSIT_URL = os.environ.get("KOSIT_URL", "http://127.0.0.1:8081")
MUSTANG_IMAGE = "rechnungscheck/validator-mustang:dev"
PARALLEL = 8


@dataclass
class Item:
    idx: int
    subset: str
    path: str  # relative to data/
    expected_valid: bool
    labels: list[str] = field(default_factory=list)
    kosit: str = "n/a"  # accept | reject | unsupported | error
    kosit_ms: float | None = None
    mustang: str = "n/a"
    mustang_xml: str = "n/a"
    mustang_pdf: str = "n/a"
    mustang_combined: str = "n/a"  # reject if either the XML or the PDF/A part is invalid
    mustang_ms: float | None = None


def corpus_items(start: int) -> list[Item]:
    base = DATA / "corpus"
    items: list[Item] = []
    for sub in ("ZUGFeRDv1", "ZUGFeRDv2", "XML-Rechnung"):
        for f in sorted((base / sub).rglob("*")):
            if f.suffix.lower() not in {".pdf", ".xml"} or not f.is_file():
                continue
            rel = f.relative_to(base).as_posix()
            invalid = "/fail/" in f"/{rel}"
            group = rel.split("/")[0] + ("/fail" if invalid else "/correct" if sub != "XML-Rechnung" else "")
            if sub == "XML-Rechnung":
                group = f"XML-Rechnung/{rel.split('/')[1]}"
            items.append(Item(start + len(items), f"corpus:{group}", f"corpus/{rel}", not invalid))
    return items


def generated_items(start: int) -> list[Item]:
    items: list[Item] = []
    for manifest in sorted((ROOT / "tenants").glob("*/evals/cases.jsonl")):
        for line in manifest.read_text(encoding="utf-8").splitlines():
            c = Case.model_validate_json(line)
            fmt = c.source_format.value
            if fmt not in {"xrechnung_cii", "xrechnung_ubl", "zugferd"}:
                continue
            bt10_missing = any(
                lb.type is DiscrepancyType.MISSING_MANDATORY_FIELD and lb.field == "buyer_reference"
                for lb in c.labels
            )
            total_wrong = any(
                lb.type is DiscrepancyType.ARITHMETIC_ERROR and lb.field == "totals.total_with_vat"
                for lb in c.labels
            )
            invalid = total_wrong or (
                bt10_missing and fmt != "zugferd"
            )  # BT-10 is optional in plain EN 16931
            labels = sorted(
                {f"{lb.type.value}:{lb.field}" if lb.field else lb.type.value for lb in c.labels}
            ) or ["clean"]
            items.append(
                Item(
                    start + len(items),
                    f"generated:{fmt}",
                    f"generated/{c.files['invoice']}",
                    not invalid,
                    labels,
                )
            )
    return items


def _kosit_one(item: Item) -> None:
    raw = (DATA / item.path).read_bytes()
    if item.path.lower().endswith(".pdf"):
        try:
            found = embedded_invoice_xml(raw)
        except Exception:
            found = None
        if not found:
            item.kosit = "unsupported"
            return
        raw = found[1]
    req = urllib.request.Request(  # noqa: S310 - fixed local URL
        f"{KOSIT_URL}/{item.idx}.xml", data=raw, headers={"Content-Type": "application/xml"}, method="POST"
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            body, status = resp.read(), resp.status
    except urllib.error.HTTPError as exc:
        body, status = exc.read(), exc.code
    item.kosit_ms = round((time.perf_counter() - t0) * 1000, 1)
    if status == 200:
        item.kosit = "accept"
    elif status == 406:
        # No configured scenario matches (other XRechnung versions, ZUGFeRD 1, Factur-X BASIC/EXTENDED, PEPPOL):
        # the file is outside what this KoSIT configuration can judge, which is not the same as invalid.
        item.kosit = "unsupported" if b"noScenarioMatched" in body else "reject"
    else:
        item.kosit = "error"


def run_kosit(items: list[Item]) -> None:
    for it in items:
        _kosit_one(it)


def run_mustang(items: list[Item], work: Path) -> None:
    work.mkdir(parents=True, exist_ok=True)
    for old in work.glob("*"):
        old.unlink()
    (work / "list.txt").write_text(
        "".join(f"{it.idx}\t{it.path}\n" for it in items), encoding="utf-8", newline="\n"
    )
    script = (
        "while IFS=$'\\t' read -r idx path; do printf '%s\\t%s\\n' \"$idx\" \"$path\"; done < /out/list.txt | "
        f"xargs -P {PARALLEL} -d '\\n' -n 1 bash -c '"
        'idx=${0%%$(printf "\\t")*}; path=${0#*$(printf "\\t")}; s=$(date +%s%N); '
        "java -Xmx768m -Dfile.encoding=UTF-8 -jar /opt/mustang/mustang.jar --no-notices --disable-file-logging "
        '--action validate --source "/work/$path" > /out/$idx.xml 2>/dev/null; rc=$?; '
        'echo "$rc $(( ($(date +%s%N) - s) / 1000000 ))" > /out/$idx.meta'
        "'"
    )
    subprocess.run(  # noqa: S603
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "bash",
            "-v",
            f"{DATA}:/work:ro",
            "-v",
            f"{work}:/out",
            MUSTANG_IMAGE,
            "-c",
            script,
        ],
        check=True,
    )
    for it in items:
        meta = work / f"{it.idx}.meta"
        rep = work / f"{it.idx}.xml"
        if not meta.exists():
            it.mustang = "error"
            continue
        it.mustang_ms = float(meta.read_text().split()[1])
        try:
            root = etree.fromstring(
                rep.read_bytes(), etree.XMLParser(recover=True, resolve_entities=False, no_network=True)
            )
        except (etree.XMLSyntaxError, ValueError):
            root = None
        if root is None:
            it.mustang = "error"
            continue
        top = root.find("summary")
        it.mustang = {"valid": "accept", "invalid": "reject"}.get(
            top.get("status", "") if top is not None else "", "error"
        )
        for part in ("xml", "pdf"):
            s = root.find(f"{part}/summary")
            setattr(
                it,
                f"mustang_{part}",
                {"valid": "accept", "invalid": "reject"}.get(
                    s.get("status", "") if s is not None else "", "n/a"
                ),
            )


def _metrics(items: list[Item], verdict: str) -> dict[str, object]:
    sup = [it for it in items if getattr(it, verdict) in {"accept", "reject"}]
    ok = [it for it in sup if (getattr(it, verdict) == "accept") == it.expected_valid]
    fa = [it for it in sup if getattr(it, verdict) == "accept" and not it.expected_valid]
    fr = [it for it in sup if getattr(it, verdict) == "reject" and it.expected_valid]
    times = [
        t for it in sup if (t := getattr(it, f"{verdict.split('_', maxsplit=1)[0]}_ms")) is not None
    ]  # same run
    return {
        "files": len(items),
        "supported": len(sup),
        "agreement": round(len(ok) / len(sup), 4) if sup else None,
        "false_accept": len(fa),
        "false_reject": len(fr),
        "unsupported_or_error": len(items) - len(sup),
        "median_ms": round(statistics.median(times), 1) if times else None,
    }


def _reuse_mustang(items: list[Item]) -> None:
    """Take Mustang verdicts from the previous run (Mustang is slow; KoSIT is re-run)."""
    prev = json.loads((OUT_DIR / "latest.json").read_text(encoding="utf-8"))
    by_path = {it["path"]: it for it in prev["items"]}
    for it in items:
        old = by_path.get(it.path)
        if old:
            it.mustang, it.mustang_xml, it.mustang_pdf, it.mustang_ms = (
                old["mustang"],
                old["mustang_xml"],
                old["mustang_pdf"],
                old["mustang_ms"],
            )


def main() -> None:
    import sys  # noqa: PLC0415

    items = corpus_items(0)
    items += generated_items(len(items))
    print(f"{len(items)} files")
    t0 = time.perf_counter()
    run_kosit(items)
    print(f"KoSIT done in {time.perf_counter() - t0:.0f} s")
    t0 = time.perf_counter()
    if "--reuse-mustang" in sys.argv:
        _reuse_mustang(items)
    else:
        run_mustang(items, DATA / "validator_runs" / "mustang")
    print(f"Mustang done in {time.perf_counter() - t0:.0f} s")

    for it in items:
        verdicts = {it.mustang, it.mustang_pdf}
        it.mustang_combined = "reject" if "reject" in verdicts else it.mustang
    subsets = sorted({it.subset for it in items})
    table: dict[str, dict[str, object]] = {}
    for sub in subsets:
        group = [it for it in items if it.subset == sub]
        table[sub] = {
            "expected_invalid": sum(1 for it in group if not it.expected_valid),
            "kosit": _metrics(group, "kosit"),
            "mustang": _metrics(group, "mustang"),
            "mustang_xml_part": _metrics(group, "mustang_xml"),
            "mustang_pdf_and_xml": _metrics(group, "mustang_combined"),
        }
    by_label: dict[str, Counter[str]] = defaultdict(Counter)
    for it in items:
        if it.subset.startswith("generated"):
            for lb in it.labels:
                by_label[lb]["n"] += 1
                by_label[lb]["kosit_reject"] += it.kosit == "reject"
                by_label[lb]["mustang_reject"] += it.mustang == "reject"
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    corpus_sha = subprocess.run(  # noqa: S603
        ["git", "-C", str(DATA / "corpus"), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    )
    result = {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "repo_commit": commit,
        "repo_dirty": dirty,
        "corpus_commit": corpus_sha,
        "validators": {
            "kosit": "1.6.3 + xrechnung-3.0.2 config 2026-08-31",
            "mustang": "2.26.0 (CLI, veraPDF)",
        },
        "subsets": table,
        "generated_rejections_by_label": {k: dict(v) for k, v in sorted(by_label.items())},
        "items": [asdict(it) for it in items],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "latest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    (OUT_DIR / "latest.md").write_text(render_md(result), encoding="utf-8", newline="\n")
    print((OUT_DIR / "latest.md").read_text(encoding="utf-8"))


def _fmt(m: dict[str, object]) -> str:
    agr = m["agreement"]
    agr_s = f"{agr:.1%}" if isinstance(agr, float) else "n/a"
    ms = m["median_ms"] if m["median_ms"] is not None else "n/a"
    return (
        f"{agr_s} · {m['supported']}/{m['files']} · FA {m['false_accept']} · FR {m['false_reject']} · {ms} ms"
    )


def render_md(r: dict[str, object]) -> str:
    lines = [
        "# Validator comparison: KoSIT vs Mustang",
        "",
        f"Run {r['run_at']} on repo commit `{r['repo_commit']}`{' (uncommitted changes!)' if r['repo_dirty'] else ''}, "
        f"corpus commit `{r['corpus_commit']}`.",
        "Agreement = share of supported files where accept/reject matches the expectation.",
        "Median ms: KoSIT = HTTP round trip to the running daemon; Mustang = one CLI run incl. JVM start.",
        "",
        "Each validator cell: agreement | supported/files | false accept | false reject | median ms.",
        "Mustang's own top-level summary reflects the XML part only; 'Mustang PDF+XML' also rejects on PDF/A errors.",
        "",
        "| Subset | exp. invalid | KoSIT | Mustang (own summary) | Mustang PDF+XML |",
        "|---|---|---|---|---|",
    ]
    subsets = r["subsets"]
    assert isinstance(subsets, dict)  # noqa: S101
    for sub, row in subsets.items():
        lines.append(
            f"| {sub} | {row['expected_invalid']} | {_fmt(row['kosit'])} | {_fmt(row['mustang'])} "
            f"| {_fmt(row['mustang_pdf_and_xml'])} |"
        )
    lines += [
        "",
        "## Generated files: rejections by label",
        "",
        "| Label | n | KoSIT rejects | Mustang rejects |",
        "|---|---|---|---|",
    ]
    by_label = r["generated_rejections_by_label"]
    assert isinstance(by_label, dict)  # noqa: S101
    for lb, c in by_label.items():
        lines.append(
            f"| {lb} | {c.get('n', 0)} | {c.get('kosit_reject', 0)} | {c.get('mustang_reject', 0)} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
