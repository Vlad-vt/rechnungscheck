"""Load and validate tenant configurations from ``tenants/<tenant_id>/config.yaml``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from rechnungscheck.tenancy.config import TenantConfig

CONFIG_FILE = "config.yaml"


class TenantConfigError(Exception):
    """A tenant configuration could not be loaded or is invalid."""

    def __init__(self, tenant_dir: Path, message: str) -> None:
        super().__init__(f"{tenant_dir.name}: {message}")
        self.tenant_dir = tenant_dir
        self.message = message


def load_tenant(tenant_dir: Path) -> TenantConfig:
    """Load one tenant. The directory name must equal the configured ``tenant_id``."""
    path = tenant_dir / CONFIG_FILE
    if not path.is_file():
        raise TenantConfigError(tenant_dir, f"missing {CONFIG_FILE}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TenantConfigError(tenant_dir, f"invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise TenantConfigError(tenant_dir, "config must be a mapping")
    try:
        config = TenantConfig.model_validate(raw)
    except ValidationError as exc:
        raise TenantConfigError(tenant_dir, str(exc)) from exc
    if config.tenant_id != tenant_dir.name:
        raise TenantConfigError(
            tenant_dir, f"tenant_id {config.tenant_id!r} does not match directory {tenant_dir.name!r}"
        )
    return config


@dataclass(frozen=True)
class LoadResult:
    tenants: dict[str, TenantConfig]
    errors: list[TenantConfigError]

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.tenants)


def load_all(tenants_root: Path) -> LoadResult:
    """Load every tenant directory under ``tenants_root``, collecting all errors."""
    tenants: dict[str, TenantConfig] = {}
    errors: list[TenantConfigError] = []
    if not tenants_root.is_dir():
        return LoadResult({}, [TenantConfigError(tenants_root, "tenants directory not found")])
    for tenant_dir in sorted(p for p in tenants_root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        try:
            cfg = load_tenant(tenant_dir)
        except TenantConfigError as exc:
            errors.append(exc)
        else:
            tenants[cfg.tenant_id] = cfg
    return LoadResult(tenants, errors)
