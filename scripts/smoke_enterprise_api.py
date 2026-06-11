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
import time
import uuid
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


async def _confirm_visible(
    client: httpx.AsyncClient, path: str, timeout_s: float = 5.0
) -> None:
    """Read-your-writes barrier after a create.

    The library's unit-of-work commits in dependency teardown, which FastAPI
    (>=0.106) runs AFTER the response is sent — an immediate dependent request
    can race the commit on a loaded host (observed once in CI as a 404 for a
    just-created role). Poll until the resource is readable.
    """
    deadline = time.time() + timeout_s
    while True:
        r = await client.get(path)
        if r.status_code < 400:
            return
        if time.time() > deadline:
            raise RuntimeError(
                f"{path} not visible within {timeout_s}s after create ({r.status_code})"
            )
        await asyncio.sleep(0.1)


async def main() -> None:
    base_url = _env("BASE_URL", "http://localhost:8004/v1").rstrip("/")
    email = _env("EMAIL", "admin@acme.com")
    # Defaults must match examples/enterprise_rbac/reset_test_env.py.
    password = _env("PASSWORD", "Testpass1!")
    agent_email = _env("AGENT_EMAIL", "agent@sf.acme.com")
    agent_password = _env("AGENT_PASSWORD", "Testpass1!")

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

        # Seed ABAC via API: a smoke-only role whose holders may only act on
        # draft leads. This demonstrates wiring from permission checks ->
        # PolicyEvaluationEngine (and flips the "any conditions exist" fast
        # path, so the checks below run through full ABAC evaluation).
        # NOTE: earlier versions attached the condition to the seeded "agent"
        # role — that role is a protected system role now, and mutating shared
        # seed data made reruns order-dependent, so the smoke creates its own
        # role and user instead.
        roles = (
            await _request(client, "GET", "/roles/", params={"page": 1, "limit": 100})
        ).json()
        role_items = roles.get("items", [])
        agent_role = next((r for r in role_items if r.get("name") == "agent"), None)
        if not agent_role:
            raise RuntimeError("Could not find 'agent' role in /roles/")

        marker = uuid.uuid4().hex[:6]
        smoke_role = (
            await _request(
                client,
                "POST",
                "/roles/",
                json={
                    "name": f"smoke-abac-{marker}",
                    "display_name": "Smoke ABAC Agent",
                    "description": "Throwaway role for the ABAC smoke scenario",
                    "permissions": agent_role.get("permissions", []),
                    "is_global": agent_role.get("is_global", False),
                    "root_entity_id": agent_role.get("root_entity_id"),
                },
            )
        ).json()
        smoke_role_id = smoke_role["id"]
        await _confirm_visible(client, f"/roles/{smoke_role_id}")

        # Scenario 1 conditions on USER attributes, which are always present
        # in the ABAC context. Scenario 2 (further down) conditions on
        # RESOURCE attributes supplied via the X-Resource-Context header.
        smoke_email = f"smoke-abac-{marker}@example.com"
        await _request(
            client,
            "POST",
            f"/roles/{smoke_role_id}/conditions",
            json={
                "attribute": "user.email",
                "operator": "equals",
                "value": smoke_email,
                "value_type": "string",
                "description": "Smoke role only grants to the designated smoke user",
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

        # Pick a parent that can hold a "team" child. The previous lookup keyed
        # on a hardcoded slug and silently fell back to items[0] (the org root,
        # which only allows "region" children) when the seed's slugs drifted.
        parent = next(
            (e for e in items if e.get("entity_type") == "office"),
            None,
        ) or next(
            (e for e in items if "team" in (e.get("allowed_child_types") or [])),
            None,
        )
        if parent is None:
            raise RuntimeError("No seeded entity accepts 'team' children")
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
        await _confirm_visible(client, f"/entities/{child_id}")

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

        # Pick the entity for the ABAC scenario. It must NOT carry an
        # auto-assigned default role: sf_residential's seeded
        # sf_team_member_default grants lead:create unconditionally to every
        # new member, which would mask the condition under test. The seeded
        # sf_commercial team sits outside the auto-assignment scope.
        agent_entity = next(
            (e for e in items if "commercial" in (e.get("name") or "").lower()),
            None,
        )
        if agent_entity is None:
            raise RuntimeError("Could not find the sf_commercial team entity")
        agent_entity_id = agent_entity["id"]

        # ABAC smoke (non-superuser): two users hold the SAME condition-guarded
        # role on the same entity; only the one matching the user.email
        # condition may create leads. Proves role-level ABAC gating end-to-end.
        async def _register_member(email: str, role_id: str) -> str:
            registered = await _request(
                client,
                "POST",
                "/auth/register",
                json={
                    "email": email,
                    "password": agent_password,
                    "first_name": "Smoke",
                    "last_name": "Abac",
                },
            )
            user_id = registered.json()["id"]
            await _confirm_visible(client, f"/users/{user_id}")
            await _request(
                client,
                "POST",
                "/memberships/",
                json={
                    "entity_id": agent_entity_id,
                    "user_id": user_id,
                    "role_ids": [role_id],
                },
            )
            return user_id

        other_email = f"smoke-abac-other-{marker}@example.com"
        await _register_member(smoke_email, smoke_role_id)
        await _register_member(other_email, smoke_role_id)

        async def _login(email: str) -> str:
            response = await _request(
                client,
                "POST",
                "/auth/login",
                json={"email": email, "password": agent_password},
            )
            return response.json()["access_token"]

        def _lead_request(
            token: str, tag: str, resource_context: dict | None = None
        ) -> dict:
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Entity-Context": agent_entity_id,
            }
            if resource_context is not None:
                headers["X-Resource-Context"] = json.dumps(resource_context)
            return {
                "json": {
                    "entity_id": agent_entity_id,
                    "first_name": "Smoke",
                    "last_name": "Lead",
                    "email": f"smoke.lead.{tag}.{marker}@example.com",
                    "phone": "+15555550123",
                    "lead_type": "buyer",
                    "source": "smoke_test",
                },
                "headers": headers,
            }

        # Test 1: same role, wrong user attribute -> ABAC denies.
        denied = await client.post("/leads", **_lead_request(await _login(other_email), "denied"))
        if denied.status_code != 403:
            raise RuntimeError(
                f"Expected 403 for ABAC denied lead create, got {denied.status_code}: {denied.text}"
            )

        # Test 2: matching user attribute -> ABAC allows.
        await _request(
            client,
            "POST",
            "/leads",
            **_lead_request(await _login(smoke_email), "allowed"),
        )

        # Scenario 2: RESOURCE-attribute ABAC via X-Resource-Context. The
        # example calls instrument_fastapi(include_resource_context=True) with
        # trust_resource_context_header=True (demo-only wiring), so the
        # client-supplied header JSON lands in the ABAC context as resource.*.
        # This role may only act on draft leads.
        res_role = (
            await _request(
                client,
                "POST",
                "/roles/",
                json={
                    "name": f"smoke-abac-res-{marker}",
                    "display_name": "Smoke ABAC Resource Agent",
                    "description": "Throwaway role for the resource-context ABAC smoke scenario",
                    "permissions": agent_role.get("permissions", []),
                    "is_global": agent_role.get("is_global", False),
                    "root_entity_id": agent_role.get("root_entity_id"),
                },
            )
        ).json()
        res_role_id = res_role["id"]
        await _confirm_visible(client, f"/roles/{res_role_id}")
        await _request(
            client,
            "POST",
            f"/roles/{res_role_id}/conditions",
            json={
                "attribute": "resource.lead_status",
                "operator": "equals",
                "value": "draft",
                "value_type": "string",
                "description": "Holders may only act on draft leads",
            },
        )

        res_email = f"smoke-abac-res-{marker}@example.com"
        await _register_member(res_email, res_role_id)
        res_token = await _login(res_email)

        # Test 3: resource context says draft -> ABAC allows.
        await _request(
            client,
            "POST",
            "/leads",
            **_lead_request(
                res_token, "res-allowed", resource_context={"lead_status": "draft"}
            ),
        )

        # Test 4: resource context says published -> ABAC denies.
        denied_resource = await client.post(
            "/leads",
            **_lead_request(
                res_token, "res-denied", resource_context={"lead_status": "published"}
            ),
        )
        if denied_resource.status_code != 403:
            raise RuntimeError(
                "Expected 403 for ABAC lead create with resource.lead_status=published, "
                f"got {denied_resource.status_code}: {denied_resource.text}"
            )

        # Test 5: header absent -> resource.lead_status unresolvable -> ABAC
        # fails closed and denies.
        denied_missing = await client.post(
            "/leads", **_lead_request(res_token, "res-missing")
        )
        if denied_missing.status_code != 403:
            raise RuntimeError(
                "Expected 403 for ABAC lead create without X-Resource-Context, "
                f"got {denied_missing.status_code}: {denied_missing.text}"
            )


if __name__ == "__main__":
    asyncio.run(main())
