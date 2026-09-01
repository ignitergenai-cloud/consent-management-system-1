"""Vercel ASGI entrypoint for the CMS Unified API."""

from vercel_app.main import app  # noqa: F401 — Vercel needs `app` in module scope

__all__ = ["app"]
