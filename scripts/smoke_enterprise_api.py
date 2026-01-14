#!/usr/bin/env python3
"""
EnterpriseRBAC API smoke test (real-world endpoint runner).

Assumes an instance is already running (e.g. examples/enterprise_rbac/main.py)
and seeded (e.g. examples/enterprise_rbac/reset_test_env.py).

Usage:
  uv run python scripts/smoke_enterprise_api.py

Environment:
  BASE_URL   Base URL including /v1 (default: http://localhost:8004/v1)
  EMAIL      Login email (default: admin@acme.com)
  PASSWORD   Login password (default: Test123!!)
"""

import asyncio
import json
import os
from typing import Any

import httpx


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


async def _request(
    client: httpx.AsyncClient, method: str, path: str, **kwargs: Any
) -> httpx.Response:
    r = await client.request(method, path, **kwargs)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text}")
    return r


async def main() -> None:
    base_url = _env("BASE_URL", "http://localhost:8004/v1").rstrip("/")
    email = _env("EMAIL", "admin@acme.com")
    password = _env("PASSWORD", "Test123!!")

    async with httpx.AsyncClient(
        base_url=base_url, timeout=20.0, follow_redirects=True
    ) as client:
        # Health/config
        await _request(client, "GET", "/auth/config")

        # Login
        login = await _request(
            client,
            "POST",
            "/auth/login",
            json={"email": email, "password": password},
        )
        tokens = login.json()
        access_token = tokens["access_token"]
        client.headers.update({"Authorization": f"Bearer {access_token}"})

        # List entities, find a stable parent (sf-office) from seeded demo.
        entities = (
            await _request(
                client, "GET", "/entities/", params={"page": 1, "limit": 1000}
            )
        ).json()
        items = entities.get("items", [])
        if not items:
            raise RuntimeError("No entities returned from /entities/")

        parent = next(
            (e for e in items if e.get("slug") == "san-francisco-office"), None
        )
        if parent is None:
            parent = items[0]
        parent_id = parent["id"]

        # Create a child entity under parent (requires entity:create_tree on parent context).
        child_slug = "smoke-team"
        created = await _request(
            client,
            "POST",
            "/entities/",
            json={
                "name": "smoke_team",
                "display_name": "Smoke Team",
                "slug": child_slug,
                "description": "created by smoke test",
                "entity_class": "structural",
                "entity_type": "team",
                "parent_entity_id": parent_id,
                "status": "active",
            },
        )
        child = created.json()
        child_id = child["id"]

        # Descendants read (requires entity:read_tree)
        await _request(client, "GET", f"/entities/{parent_id}/descendants")

        # Members read (requires membership:read_tree)
        await _request(
            client,
            "GET",
            f"/entities/{parent_id}/members",
            params={"page": 1, "limit": 50},
        )

        # Move: move the created child to root (new_parent_id null)
        await _request(
            client, "POST", f"/entities/{child_id}/move", json={"new_parent_id": None}
        )

        # Cleanup: archive the entity
        await _request(client, "DELETE", f"/entities/{child_id}")

        # ABAC smoke: try to create a lead with a resource context that satisfies
        # the seeded demo condition (resource.lead_status == "draft").
        # This only validates that the server accepts X-Resource-Context and that
        # ABAC is evaluated somewhere in the hot path.
        headers = {"X-Resource-Context": json.dumps({"lead_status": "draft"})}
        await _request(
            client,
            "POST",
            "/leads",
            json={
                "entity_id": parent_id,
                "first_name": "Smoke",
                "last_name": "Lead",
                "email": "smoke.lead@example.com",
                "phone": "+15555550123",
                "lead_type": "buyer",
                "status": "draft",
            },
            headers=headers,
        )


if __name__ == "__main__":
    asyncio.run(main())
