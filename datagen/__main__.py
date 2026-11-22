"""``uv run python -m datagen --help``"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from datagen.build import DEFAULT_SEED, build_tenant
from rechnungscheck.tenancy import load_all

app = typer.Typer(no_args_is_help=True, help="Synthetic dataset generator.")


@app.command()
def generate(
    seed: Annotated[int, typer.Option(help="Dataset seed.")] = DEFAULT_SEED,
    tenants_dir: Annotated[Path, typer.Option("--tenants")] = Path("tenants"),
    out: Annotated[Path, typer.Option(help="Where rendered documents go (not committed).")] = Path(
        "data/generated"
    ),
    tenant: Annotated[list[str] | None, typer.Option(help="Only these tenants.")] = None,
    no_render: Annotated[bool, typer.Option("--no-render", help="Skip PDFs/XML/PNGs.")] = False,
) -> None:
    """Write master data, contracts, case manifests and rendered documents."""
    result = load_all(tenants_dir)
    if not result.ok:
        for err in result.errors:
            typer.echo(f"ERROR {err}", err=True)
        raise typer.Exit(1)
    for tid, cfg in result.tenants.items():
        if tenant and tid not in tenant:
            continue
        cases = build_tenant(cfg, tenants_dir / tid, out, seed=seed, render=not no_render)
        fmts = Counter(c.source_format.value for c in cases)
        typer.echo(f"{tid}: {len(cases)} cases {dict(fmts)}")


@app.command()
def verify(
    tenants_dir: Annotated[Path, typer.Option("--tenants")] = Path("tenants"),
    out: Annotated[Path, typer.Option()] = Path("data/generated"),
) -> None:
    """Check rendered documents against the committed SHA-256 lists."""
    import hashlib  # noqa: PLC0415

    bad = total = 0
    for sums in sorted(tenants_dir.glob("*/evals/documents.sha256")):
        for line in sums.read_text(encoding="utf-8").splitlines():
            digest, path = line.split("  ", 1)
            total += 1
            f = out / path
            if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != digest:
                bad += 1
                typer.echo(f"MISMATCH {path}", err=True)
    typer.echo(f"{total - bad}/{total} documents match")
    if bad:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
