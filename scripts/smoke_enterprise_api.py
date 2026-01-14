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
    agent_email = _env("AGENT_EMAIL", "agent@sf.acme.com")
    agent_password = _env("AGENT_PASSWORD", "Test123!!")

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

        # Seed ABAC via API: Agents can only act on draft leads.
        # This demonstrates wiring from permission checks -> PolicyEvaluationEngine.
        roles = (
            await _request(client, "GET", "/roles/", params={"page": 1, "limit": 100})
        ).json()
        role_items = roles.get("items", [])
        agent_role = next((r for r in role_items if r.get("name") == "agent"), None)
        if not agent_role:
            raise RuntimeError("Could not find 'agent' role in /roles/")
        agent_role_id = agent_role["id"]

        existing_conditions = await _request(
            client, "GET", f"/roles/{agent_role_id}/conditions"
        )
        for cond in existing_conditions.json():
            await _request(
                client,
                "DELETE",
                f"/roles/{agent_role_id}/conditions/{cond['id']}",
            )

        await _request(
            client,
            "POST",
            f"/roles/{agent_role_id}/conditions",
            json={
                "attribute": "resource.lead_status",
                "operator": "equals",
                "value": "draft",
                "value_type": "string",
                "description": "Agents can only act on draft leads (smoke demo)",
            },
        )

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

        # Find the agent's entity (sf-residential-team) for ABAC tests
        # The agent has membership in sf_residential, so they can only create leads there
        agent_entity = next(
            (e for e in items if e.get("slug") == "sf-residential"), None
        )
        if agent_entity is None:
            # Fallback - try to find any team entity
            agent_entity = next(
                (e for e in items if e.get("entity_type") == "team"), None
            )
        if agent_entity is None:
            raise RuntimeError("Could not find agent's entity (sf-residential)")
        agent_entity_id = agent_entity["id"]

        # ABAC smoke (non-superuser): agent should be denied unless resource.lead_status == "draft".
        agent_login = await _request(
            client,
            "POST",
            "/auth/login",
            json={"email": agent_email, "password": agent_password},
        )
        agent_tokens = agent_login.json()
        agent_access = agent_tokens["access_token"]

        # Test 1: Agent denied when lead_status is "published" (ABAC condition fails)
        # X-Entity-Context header tells the permission check which entity to check against
        denied_headers = {
            "Authorization": f"Bearer {agent_access}",
            "X-Entity-Context": agent_entity_id,
            "X-Resource-Context": json.dumps({"lead_status": "published"}),
        }
        denied = await client.post(
            "/leads",
            json={
                "entity_id": agent_entity_id,  # Use agent's entity
                "first_name": "Smoke",
                "last_name": "Lead",
                "email": "smoke.lead.denied@example.com",
                "phone": "+15555550123",
                "lead_type": "buyer",
                "status": "published",
                "source": "smoke_test",
            },
            headers=denied_headers,
        )
        if denied.status_code != 403:
            raise RuntimeError(
                f"Expected 403 for ABAC denied lead create, got {denied.status_code}: {denied.text}"
            )

        # Test 2: Agent allowed when lead_status is "draft" (ABAC condition passes)
        allowed_headers = {
            "Authorization": f"Bearer {agent_access}",
            "X-Entity-Context": agent_entity_id,
            "X-Resource-Context": json.dumps({"lead_status": "draft"}),
        }
        await _request(
            client,
            "POST",
            "/leads",
            json={
                "entity_id": agent_entity_id,  # Use agent's entity
                "first_name": "Smoke",
                "last_name": "Lead",
                "email": "smoke.lead.allowed@example.com",
                "phone": "+15555550123",
                "lead_type": "buyer",
                "status": "draft",
                "source": "smoke_test",
            },
            headers=allowed_headers,
        )


if __name__ == "__main__":
    asyncio.run(main())
