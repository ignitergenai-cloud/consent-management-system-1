"""Supabase PostgREST client (httpx-based, fully async)."""

from __future__ import annotations

import httpx

_TIMEOUT = 10.0


class SupabaseDB:
    """Thin async wrapper around the Supabase PostgREST REST API."""

    def __init__(self, url: str, key: str) -> None:
        base = url.rstrip("/")
        self._rest = f"{base}/rest/v1"
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    async def _get(self, table: str, params: dict) -> list[dict]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"{self._rest}/{table}", headers=self._headers, params=params)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else [data]

    async def _post(self, table: str, data: dict | list) -> list[dict]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(f"{self._rest}/{table}", headers=self._headers, json=data)
            r.raise_for_status()
            body = r.json()
            if isinstance(body, list):
                return body
            return [body] if body else []

    async def _patch(self, table: str, data: dict, params: dict) -> list[dict]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.patch(
                f"{self._rest}/{table}", headers=self._headers, json=data, params=params
            )
            r.raise_for_status()
            body = r.json()
            if isinstance(body, list):
                return body
            return [body] if body else []

    async def _delete(self, table: str, params: dict) -> list[dict]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.delete(f"{self._rest}/{table}", headers=self._headers, params=params)
            r.raise_for_status()
            body = r.json()
            return body if isinstance(body, list) else []

    # ------------------------------------------------------------------
    # Public query API
    # ------------------------------------------------------------------

    async def select(
        self,
        table: str,
        *,
        columns: str = "*",
        order: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        **filters: str,
    ) -> list[dict]:
        """SELECT rows.  Filters use PostgREST syntax: status='eq.PENDING'."""
        params: dict = {"select": columns}
        params.update(filters)
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        return await self._get(table, params)

    async def select_one(self, table: str, **filters: str) -> dict | None:
        rows = await self.select(table, limit=1, **filters)
        return rows[0] if rows else None

    async def insert(self, table: str, data: dict) -> dict:
        rows = await self._post(table, data)
        return rows[0] if rows else data

    async def insert_many(self, table: str, data: list[dict]) -> list[dict]:
        return await self._post(table, data)

    async def update(self, table: str, data: dict, **filters: str) -> list[dict]:
        return await self._patch(table, data, dict(filters))

    async def delete(self, table: str, **filters: str) -> list[dict]:
        return await self._delete(table, dict(filters))

    async def upsert(self, table: str, data: dict, on_conflict: str = "") -> dict:
        """INSERT … ON CONFLICT DO UPDATE."""
        headers = {**self._headers, "Prefer": "return=representation,resolution=merge-duplicates"}
        params = {}
        if on_conflict:
            params["on_conflict"] = on_conflict
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(
                f"{self._rest}/{table}", headers=headers, json=data, params=params
            )
            r.raise_for_status()
            body = r.json()
            rows = body if isinstance(body, list) else [body]
            return rows[0] if rows else data

    async def rpc(self, func: str, params: dict | None = None) -> object:
        """Call a Postgres function via PostgREST /rpc/."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(
                f"{self._rest}/rpc/{func}",
                headers=self._headers,
                json=params or {},
            )
            r.raise_for_status()
            return r.json()
