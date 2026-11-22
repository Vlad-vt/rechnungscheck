"""Command-line interface: ``rechnungscheck --help``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from rechnungscheck.config.settings import get_settings
from rechnungscheck.tenancy import load_all

app = typer.Typer(no_args_is_help=True, help="RechnungsCheck command-line interface.")
tenants_app = typer.Typer(no_args_is_help=True, help="Tenant configuration commands.")
app.add_typer(tenants_app, name="tenants")

console = Console()
err_console = Console(stderr=True)

TenantsDir = Annotated[
    Path | None, typer.Option("--dir", help="Tenants root directory (default: RC_TENANTS_DIR or ./tenants).")
]


@tenants_app.command("validate")
def validate_tenants(tenants_dir: TenantsDir = None) -> None:
    """Validate every tenant config; exit code 1 on any error."""
    root = tenants_dir or get_settings().tenants_dir
    result = load_all(root)
    table = Table("tenant", "language", "actions", "auto-approve clean / tolerance", "mandatory fields")
    for t in result.tenants.values():
        table.add_row(
            t.tenant_id,
            "/".join(lang.value for lang in t.correspondence_languages),
            str(len(t.actions)),
            f"{t.auto_approval.clean_invoices} / {t.auto_approval.within_tolerance}",
            str(len(t.mandatory_fields)),
        )
    if result.tenants:
        console.print(table)
    for err in result.errors:
        err_console.print(f"[red]ERROR[/red] {err}")
    if not result.ok:
        raise typer.Exit(code=1)
    console.print(f"[green]{len(result.tenants)} tenant config(s) valid[/green]")


@tenants_app.command("schema")
def tenant_schema() -> None:
    """Print the tenant config JSON schema."""
    import json  # noqa: PLC0415

    from rechnungscheck.tenancy import TenantConfig  # noqa: PLC0415

    console.print_json(json.dumps(TenantConfig.model_json_schema()))


if __name__ == "__main__":
    app()
