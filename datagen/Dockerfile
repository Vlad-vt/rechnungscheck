# Canonical rendering environment for the synthetic dataset (ADR 0004).
# PDF and PNG bytes depend on the zlib / libpng / pdfium builds, which differ between
# Windows and Linux wheels. Generating inside this digest-pinned image makes the
# committed SHA-256 list reproducible on any host that runs Docker (local and CI).
FROM ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 AS uv

FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    PYTHONPATH=/work/src:/work
WORKDIR /build
# Dependencies only (from the lockfile); the repository itself is bind-mounted at /work.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --no-dev --group datagen \
 && useradd --create-home --uid 10001 datagen
USER datagen
WORKDIR /work
ENTRYPOINT ["/opt/venv/bin/python", "-m", "datagen"]
