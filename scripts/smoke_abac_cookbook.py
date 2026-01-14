#!/usr/bin/env python3
"""
ABAC cookbook smoke test (real-world endpoint runner).

Assumes examples/abac_cookbook/main.py is running and seeded via:
  uv run python examples/abac_cookbook/reset_test_env.py

This test demonstrates:
  - Permission-level ABAC conditions (not role-level)
  - Editor can read all documents
  - Editor can only update documents with status "draft" or "review"
  - Editor cannot update "published" documents
"""

import asyncio
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
    base_url = _env("BASE_URL", "http://localhost:8005/v1").rstrip("/")

    admin_email = _env("ADMIN_EMAIL", "admin@cookbook.example.com")
    admin_password = _env("ADMIN_PASSWORD", "Test123!!")
    editor_email = _env("EDITOR_EMAIL", "editor@cookbook.example.com")
    editor_password = _env("EDITOR_PASSWORD", "Test123!!")

    async with httpx.AsyncClient(
        base_url=base_url, timeout=20.0, follow_redirects=True
    ) as client:
        # =====================================================================
        # 1. Login as admin (superuser) to configure ABAC via API
        # =====================================================================
        print("Logging in as admin...")
        login = await _request(
            client,
            "POST",
            "/auth/login",
            json={"email": admin_email, "password": admin_password},
        )
        access_token = login.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {access_token}"})

        # =====================================================================
        # 2. Find the document:update permission
        # =====================================================================
        print("Finding document:update permission...")
        perms = (
            await _request(
                client, "GET", "/permissions/", params={"page": 1, "limit": 100}
            )
        ).json()
        doc_update_perm = next(
            (p for p in perms.get("items", []) if p.get("name") == "document:update"),
            None,
        )
        if not doc_update_perm:
            raise RuntimeError("Could not find 'document:update' permission")
        perm_id = doc_update_perm["id"]
        print(f"Found document:update permission: {perm_id}")

        # =====================================================================
        # 3. Clean existing conditions on the permission for deterministic runs
        # =====================================================================
        print("Cleaning existing ABAC conditions...")
        existing_conditions = await _request(
            client, "GET", f"/permissions/{perm_id}/conditions"
        )
        for cond in existing_conditions.json():
            await _request(
                client, "DELETE", f"/permissions/{perm_id}/conditions/{cond['id']}"
            )

        existing_groups = await _request(
            client, "GET", f"/permissions/{perm_id}/condition-groups"
        )
        for g in existing_groups.json():
            await _request(
                client, "DELETE", f"/permissions/{perm_id}/condition-groups/{g['id']}"
            )

        # =====================================================================
        # 4. Add ABAC conditions to document:update permission
        #    Condition: resource.status must be "draft" OR "review"
        # =====================================================================
        print("Creating ABAC condition group (OR: draft, review)...")
        group = await _request(
            client,
            "POST",
            f"/permissions/{perm_id}/condition-groups",
            json={"operator": "OR", "description": "status is draft OR review"},
        )
        group_id = group.json()["id"]

        for status in ("draft", "review"):
            await _request(
                client,
                "POST",
                f"/permissions/{perm_id}/conditions",
                json={
                    "attribute": "resource.status",
                    "operator": "equals",
                    "value": status,
                    "value_type": "string",
                    "condition_group_id": group_id,
                },
            )
        print("ABAC conditions added to document:update permission")

        # =====================================================================
        # 5. Login as editor (non-superuser) to verify ABAC enforcement
        # =====================================================================
        print("Logging in as editor...")
        editor_login = await _request(
            client,
            "POST",
            "/auth/login",
            json={"email": editor_email, "password": editor_password},
        )
        editor_access = editor_login.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {editor_access}"})

        # =====================================================================
        # 6. Verify editor can LIST documents (read should work)
        # =====================================================================
        print("Testing: Editor can list documents...")
        docs = await _request(client, "GET", "/documents")
        items = docs.json()
        print(f"  Listed {len(items)} documents")

        draft = next((d for d in items if d.get("status") == "draft"), None)
        review = next((d for d in items if d.get("status") == "review"), None)
        published = next((d for d in items if d.get("status") == "published"), None)

        if not draft or not published:
            raise RuntimeError("Expected seeded draft and published documents")
        print(f"  Found draft doc: {draft['id']}")
        print(f"  Found published doc: {published['id']}")

        # =====================================================================
        # 7. Verify editor CANNOT update published document (ABAC denies)
        # =====================================================================
        print("Testing: Editor cannot update published document...")
        denied = await client.patch(
            f"/documents/{published['id']}",
            json={"title": "should be denied"},
        )
        if denied.status_code != 403:
            raise RuntimeError(
                f"Expected 403 for published update, got {denied.status_code}: {denied.text}"
            )
        print("  Correctly denied (403)")

        # =====================================================================
        # 8. Verify editor CAN update draft document (ABAC allows)
        # =====================================================================
        print("Testing: Editor can update draft document...")
        await _request(
            client,
            "PATCH",
            f"/documents/{draft['id']}",
            json={"title": "allowed update on draft"},
        )
        print("  Successfully updated draft document")

        # =====================================================================
        # 9. Verify editor CAN update review document (ABAC allows)
        # =====================================================================
        if review:
            print("Testing: Editor can update review document...")
            await _request(
                client,
                "PATCH",
                f"/documents/{review['id']}",
                json={"title": "allowed update on review"},
            )
            print("  Successfully updated review document")

        print("\n✓ All ABAC smoke tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
