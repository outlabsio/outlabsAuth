"""
HTTP-level integration checks for the seeded EnterpriseRBAC example.

This is the release-strategy companion to ``reset_test_env.py``: where the
library test suite exercises services in-process, this script drives the REAL
running API over HTTP against the seeded scenario data and asserts the
behavior an operator cares about before shipping — auth, entity-scoped and
sibling/cross-root isolation, and (critically) that permission mutations take
effect on the very next request even with Redis caching enabled.

Usage:
    python reset_test_env.py                       # seed known state
    uvicorn main:app --port 8004                   # start the API
    python api_integration_check.py                # run the checks
    python api_integration_check.py --base-url http://staging-host:8004

Exit code 0 = all checks passed. Non-destructive beyond the seeded dataset:
it creates a few leads, one temporary membership (removed again), and one
API key (revoked again).
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid

import httpx

PASSWORD = "Testpass1!"
PERSONAS = {
    "admin": "admin@acme.com",
    "regional_admin": "regional-admin@acme.com",
    "sf_manager": "manager@sf.acme.com",
    "sf_agent": "agent@sf.acme.com",
    "sf_commercial": "commercial@sf.acme.com",
    "auditor": "auditor@acme.com",
    "summit_agent": "agent@austin.summit.com",
    "summit_admin": "summit-admin@summit.com",
}

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{f'  ({detail})' if detail else ''}")


def lead_payload(entity_id: str) -> dict:
    marker = uuid.uuid4().hex[:8]
    return {
        "entity_id": entity_id,
        "first_name": "Integration",
        "last_name": f"Check-{marker}",
        "email": f"lead-{marker}@example.com",
        "phone": "+1-555-0000",
        "lead_type": "buyer",
        "source": "api-integration-check",
    }


def create_lead(client: httpx.Client, token: str, entity_id: str) -> httpx.Response:
    return client.post(
        "/v1/leads",
        json=lead_payload(entity_id),
        headers={"Authorization": f"Bearer {token}", "X-Entity-Context": entity_id},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8004")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=15.0)

    print(f"\n== EnterpriseRBAC API integration check against {args.base_url} ==\n")

    # ---- 0. API reachable -------------------------------------------------
    try:
        spec = client.get("/openapi.json")
        check("API reachable (openapi.json)", spec.status_code == 200)
    except httpx.HTTPError as exc:
        check("API reachable (openapi.json)", False, str(exc))
        return finish()

    # ---- 1. Every persona can log in --------------------------------------
    tokens: dict[str, str] = {}
    for persona, email in PERSONAS.items():
        response = client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
        token = response.json().get("access_token") if response.status_code == 200 else None
        if token:
            tokens[persona] = token
        check(f"login {email}", bool(token), f"http {response.status_code}")
    if len(tokens) != len(PERSONAS):
        return finish()

    def get(persona: str, path: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {tokens[persona]}"
        return client.get(path, headers=headers, **kwargs)

    # ---- 2. Resolve seeded entities and roles as admin --------------------
    entities = get("admin", "/v1/entities/", params={"limit": 100}).json()
    entity_rows = entities.get("items", entities) if isinstance(entities, dict) else entities
    by_name = {row["name"]: row["id"] for row in entity_rows}
    sf_residential = next((v for k, v in by_name.items() if "residential" in k.lower()), None)
    sf_commercial = next((v for k, v in by_name.items() if "commercial" in k.lower()), None)
    check("seeded entities resolvable", bool(sf_residential and sf_commercial), f"{len(entity_rows)} entities")
    if not (sf_residential and sf_commercial):
        return finish()

    roles = get("admin", "/v1/roles/", params={"limit": 100}).json()
    role_rows = roles.get("items", roles) if isinstance(roles, dict) else roles
    agent_role = next((r for r in role_rows if r["name"] == "agent"), None)
    check("seeded 'agent' role resolvable", agent_role is not None, f"{len(role_rows)} roles")
    if agent_role is None:
        return finish()

    # ---- 3. Authenticated identity ----------------------------------------
    me = get("sf_agent", "/v1/users/me")
    check("GET /v1/users/me (JWT path)", me.status_code == 200 and me.json()["email"] == PERSONAS["sf_agent"])

    # ---- 4. Entity-scoped grants and isolation ----------------------------
    # NOTE: the seeded agent personas also hold the DIRECT "agent" role, which
    # by design (DD-054) grants org-wide — so sibling/cross-root isolation is
    # asserted with a membership-ONLY user created here through the API.
    response = create_lead(client, tokens["sf_agent"], sf_residential)
    check("sf agent creates lead in own team (201)", response.status_code == 201, f"http {response.status_code}")

    scoped_email = f"scoped-{uuid.uuid4().hex[:8]}@example.com"
    registered = client.post(
        "/v1/auth/register",
        json={"email": scoped_email, "password": PASSWORD, "first_name": "Scoped", "last_name": "Member"},
    )
    scoped_id = registered.json().get("id")
    login = client.post("/v1/auth/login", json={"email": scoped_email, "password": PASSWORD})
    scoped_token = login.json().get("access_token")
    check(
        "membership-only user registered + logged in",
        bool(scoped_id and scoped_token),
        f"http {registered.status_code}/{login.status_code}",
    )

    grant = client.post(
        "/v1/memberships/",
        json={"entity_id": sf_commercial, "user_id": scoped_id, "role_ids": [agent_role["id"]]},
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    check("admin grants commercial-team membership", grant.status_code in (200, 201), f"http {grant.status_code}")

    response = create_lead(client, scoped_token, sf_commercial)
    check(
        "membership user creates lead in OWN entity (201)", response.status_code == 201, f"http {response.status_code}"
    )

    response = create_lead(client, scoped_token, sf_residential)
    check(
        "sibling-team entity denied (403) — membership does not leak",
        response.status_code == 403,
        f"http {response.status_code}",
    )

    summit_entity = next((v for k, v in by_name.items() if "austin" in k.lower() or "summit" in k.lower()), None)
    if summit_entity:
        response = create_lead(client, scoped_token, summit_entity)
        check("cross-root entity denied (403/404)", response.status_code in (403, 404), f"http {response.status_code}")
    else:
        check("cross-root entity denied (403/404)", False, "no summit entity resolved")

    # ---- 5. Warm-cache repeats keep the same verdicts ----------------------
    timings = []
    for _ in range(3):
        start = time.perf_counter()
        repeat = create_lead(client, scoped_token, sf_residential)
        timings.append((time.perf_counter() - start) * 1000)
        if repeat.status_code != 403:
            break
    check(
        "denial verdict stable across repeats (cache-served)",
        repeat.status_code == 403,
        f"latencies ms: {', '.join(f'{t:.0f}' for t in timings)}",
    )

    timings = []
    for _ in range(3):
        start = time.perf_counter()
        repeat = get("sf_agent", "/v1/leads")
        timings.append((time.perf_counter() - start) * 1000)
    check(
        "read path stable across repeats (cache-served)",
        repeat.status_code == 200,
        f"latencies ms: {', '.join(f'{t:.0f}' for t in timings)}",
    )

    # ---- 6. THE release check: mutation -> next-request visibility --------
    # The auditor has no lead:create anywhere. Grant it via a membership, and
    # the very next request must succeed; remove it, and the very next request
    # must fail — proving the versioned cache invalidation through the whole
    # stack (HTTP -> deps -> services -> Redis), not just in unit tests.
    auditor_id = get("auditor", "/v1/users/me").json()["id"]

    response = create_lead(client, tokens["auditor"], sf_residential)
    check("auditor starts without lead:create (403)", response.status_code == 403, f"http {response.status_code}")

    grant = client.post(
        "/v1/memberships/",
        json={"entity_id": sf_residential, "user_id": auditor_id, "role_ids": [agent_role["id"]]},
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    check("admin grants membership+role to auditor", grant.status_code in (200, 201), f"http {grant.status_code}")

    response = create_lead(client, tokens["auditor"], sf_residential)
    check("grant visible on the NEXT request (201)", response.status_code == 201, f"http {response.status_code}")

    revoke = client.delete(
        f"/v1/memberships/{sf_residential}/{auditor_id}",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    check("admin revokes auditor membership", revoke.status_code in (200, 204), f"http {revoke.status_code}")

    response = create_lead(client, tokens["auditor"], sf_residential)
    check("revocation visible on the NEXT request (403)", response.status_code == 403, f"http {response.status_code}")

    # ---- 7. Batched permission-check endpoint ------------------------------
    response = client.post(
        "/v1/permissions/check",
        json={"user_id": auditor_id, "permissions": ["lead:create", "role:read"]},
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    body = response.json() if response.status_code == 200 else {}
    check(
        "POST /v1/permissions/check (batched)",
        response.status_code == 200 and body.get("results", {}).get("lead:create") is False,
        f"http {response.status_code} results={body.get('results')}",
    )

    # ---- 8. API-key lifecycle (snapshot path) ------------------------------
    created = client.post(
        "/v1/api-keys/",
        json={"name": "integration-check key", "scopes": ["lead:read"]},
        headers={"Authorization": f"Bearer {tokens['sf_agent']}"},
    )
    api_key = created.json().get("api_key") or created.json().get("key")
    key_id = created.json().get("id") or (created.json().get("api_key_record") or {}).get("id")
    check(
        "agent creates personal API key",
        created.status_code in (200, 201) and bool(api_key),
        f"http {created.status_code}",
    )

    if api_key:
        first = client.get("/v1/leads", headers={"X-API-Key": api_key})
        second = client.get("/v1/leads", headers={"X-API-Key": api_key})
        check(
            "API-key auth works (cold + warm snapshot)",
            first.status_code == 200 and second.status_code == 200,
            f"http {first.status_code}/{second.status_code}",
        )

        if key_id:
            revoked = client.delete(
                f"/v1/api-keys/{key_id}",
                headers={"Authorization": f"Bearer {tokens['sf_agent']}"},
            )
            after = client.get("/v1/leads", headers={"X-API-Key": api_key})
            check(
                "revoked API key rejected on the NEXT request",
                revoked.status_code in (200, 204) and after.status_code == 401,
                f"revoke http {revoked.status_code}, after http {after.status_code}",
            )
        else:
            check("revoked API key rejected on the NEXT request", False, "no key id in create response")

    admin_headers = {"Authorization": f"Bearer {tokens['admin']}"}
    marker = uuid.uuid4().hex[:6]
    acme_org = by_name.get("acme_realty") or next((v for k, v in by_name.items() if "acme" in k.lower()), None)
    west_coast = next((v for k, v in by_name.items() if "west" in k.lower()), None)
    east_coast = next((v for k, v in by_name.items() if "east" in k.lower()), None)
    sf_office = next((v for k, v in by_name.items() if "office" in k.lower()), None)

    def register_user(label: str) -> tuple[str, str]:
        email = f"{label}-{marker}@example.com"
        reg = client.post(
            "/v1/auth/register",
            json={"email": email, "password": PASSWORD, "first_name": "ITC", "last_name": label},
        )
        token = client.post("/v1/auth/login", json={"email": email, "password": PASSWORD}).json().get("access_token")
        return reg.json().get("id"), token

    # ---- 9. Tree permissions: ancestor membership grants on descendants ----
    # A *_tree permission held via a membership on west_coast must grant the
    # base action on descendant entities (closure-table path), and must NOT
    # grant on the sibling east_coast branch.
    tree_ok = bool(acme_org and west_coast and east_coast)
    check("tree-perm fixtures resolvable (org/west/east)", tree_ok)
    if tree_ok:
        # The seed defines lead:read_tree but not lead:create_tree — create it
        # through the API (tolerating "already exists" on re-runs against an
        # unreseeded database).
        perm = client.post(
            "/v1/permissions/",
            json={"name": "lead:create_tree", "display_name": "Create leads (tree)"},
            headers=admin_headers,
        )
        check(
            "lead:create_tree permission available",
            perm.status_code in (200, 201) or "already exists" in perm.text.lower(),
            f"http {perm.status_code}",
        )

        tree_role = client.post(
            "/v1/roles/",
            json={
                "name": f"itc-tree-{marker}",
                "display_name": "ITC Tree Creator",
                "permissions": ["lead:create_tree"],
                "is_global": False,
                "root_entity_id": acme_org,
            },
            headers=admin_headers,
        )
        tree_role_id = tree_role.json().get("id")
        tree_user_id, tree_token = register_user("tree")
        grant = client.post(
            "/v1/memberships/",
            json={"entity_id": west_coast, "user_id": tree_user_id, "role_ids": [tree_role_id]},
            headers=admin_headers,
        )
        check(
            "tree role created + granted at west_coast",
            tree_role.status_code in (200, 201) and grant.status_code in (200, 201),
            f"role http {tree_role.status_code}, grant http {grant.status_code}",
        )

        response = create_lead(client, tree_token, sf_residential)
        check(
            "tree permission grants on DESCENDANT entity (201)",
            response.status_code == 201,
            f"http {response.status_code}",
        )
        response = create_lead(client, tree_token, east_coast)
        check(
            "tree permission does NOT leak to sibling branch (403)",
            response.status_code == 403,
            f"http {response.status_code}",
        )

        # POST /v1/permissions/check honors entity_id (accepted but silently
        # ignored before 0.1.0a23): the same user+permission answers True in a
        # descendant of their tree grant and False in the sibling branch.
        def batched_check(payload: dict) -> httpx.Response:
            return client.post(
                "/v1/permissions/check",
                json=payload,
                headers={"Authorization": f"Bearer {tokens['admin']}"},
            )

        base = {"user_id": tree_user_id, "permissions": ["lead:create"]}
        in_descendant = batched_check({**base, "entity_id": sf_residential})
        in_sibling = batched_check({**base, "entity_id": east_coast})
        verdict_descendant = in_descendant.json().get("results", {}).get("lead:create")
        verdict_sibling = in_sibling.json().get("results", {}).get("lead:create")
        check(
            "permissions/check honors entity_id (descendant True, sibling False)",
            in_descendant.status_code == 200
            and in_sibling.status_code == 200
            and verdict_descendant is True
            and verdict_sibling is False,
            f"descendant={verdict_descendant} sibling={verdict_sibling}",
        )

        malformed = batched_check({**base, "entity_id": "not-a-uuid"})
        check(
            "permissions/check rejects malformed entity_id (400)",
            malformed.status_code == 400,
            f"http {malformed.status_code}",
        )

    # ---- 10. Role-permission edit -> next-request visibility ----------------
    # Adding/removing a permission on a role must affect its holders on their
    # very next request (the role-edit per-user fan-out invalidation).
    edit_role = client.post(
        "/v1/roles/",
        json={
            "name": f"itc-edit-{marker}",
            "display_name": "ITC Editable Role",
            "permissions": ["lead:read"],
            "is_global": False,
            "root_entity_id": acme_org,
        },
        headers=admin_headers,
    )
    edit_role_id = edit_role.json().get("id")
    edit_user_id, edit_token = register_user("roleedit")
    client.post(
        "/v1/memberships/",
        json={"entity_id": sf_commercial, "user_id": edit_user_id, "role_ids": [edit_role_id]},
        headers=admin_headers,
    )

    response = create_lead(client, edit_token, sf_commercial)
    check("holder starts without lead:create (403)", response.status_code == 403, f"http {response.status_code}")

    added = client.post(f"/v1/roles/{edit_role_id}/permissions", json=["lead:create"], headers=admin_headers)
    response = create_lead(client, edit_token, sf_commercial)
    check(
        "permission ADDED to role -> visible on NEXT request (201)",
        added.status_code in (200, 201) and response.status_code == 201,
        f"add http {added.status_code}, create http {response.status_code}",
    )

    removed = client.request(
        "DELETE",
        f"/v1/roles/{edit_role_id}/permissions",
        json=["lead:create"],
        headers=admin_headers,
    )
    response = create_lead(client, edit_token, sf_commercial)
    check(
        "permission REMOVED from role -> denied on NEXT request (403)",
        removed.status_code in (200, 204) and response.status_code == 403,
        f"remove http {removed.status_code}, create http {response.status_code}",
    )

    # ---- 11. Membership suspend / reactivate --------------------------------
    # Uses the membership-only user from section 4 (agent role at commercial).
    suspended = client.patch(
        f"/v1/memberships/{sf_commercial}/{scoped_id}",
        json={"status": "suspended", "reason": "integration check"},
        headers=admin_headers,
    )
    response = create_lead(client, scoped_token, sf_commercial)
    check(
        "suspended membership denied on NEXT request (403)",
        suspended.status_code == 200 and response.status_code == 403,
        f"patch http {suspended.status_code}, create http {response.status_code}",
    )

    reactivated = client.patch(
        f"/v1/memberships/{sf_commercial}/{scoped_id}",
        json={"status": "active", "reason": "integration check"},
        headers=admin_headers,
    )
    response = create_lead(client, scoped_token, sf_commercial)
    check(
        "reactivated membership allowed on NEXT request (201)",
        reactivated.status_code == 200 and response.status_code == 201,
        f"patch http {reactivated.status_code}, create http {response.status_code}",
    )

    # ---- 12. Entity archive revokes member access ---------------------------
    archive_ok = bool(sf_office)
    check("entity-archive fixture resolvable (sf office)", archive_ok)
    if archive_ok:
        created_entity = client.post(
            "/v1/entities/",
            json={
                "name": f"itc_team_{marker}",
                "display_name": f"ITC Team {marker}",
                "slug": f"itc-team-{marker}",
                "entity_class": "structural",
                "entity_type": "team",
                "parent_entity_id": sf_office,
            },
            headers=admin_headers,
        )
        temp_entity_id = created_entity.json().get("id")
        arch_user_id, arch_token = register_user("archive")
        client.post(
            "/v1/memberships/",
            json={"entity_id": temp_entity_id, "user_id": arch_user_id, "role_ids": [agent_role["id"]]},
            headers=admin_headers,
        )
        response = create_lead(client, arch_token, temp_entity_id)
        check(
            "member creates lead in throwaway entity (201)",
            created_entity.status_code in (200, 201) and response.status_code == 201,
            f"entity http {created_entity.status_code}, create http {response.status_code}",
        )

        archived = client.delete(f"/v1/entities/{temp_entity_id}", headers=admin_headers)
        response = create_lead(client, arch_token, temp_entity_id)
        check(
            "entity archived -> member denied on NEXT request (403/404)",
            archived.status_code in (200, 204) and response.status_code in (403, 404),
            f"archive http {archived.status_code}, create http {response.status_code}",
        )

    # ---- 13. Refresh-token flow + logout ------------------------------------
    fresh_login = client.post("/v1/auth/login", json={"email": PERSONAS["sf_agent"], "password": PASSWORD}).json()
    refresh_token = fresh_login.get("refresh_token")
    refreshed = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    new_access = refreshed.json().get("access_token") if refreshed.status_code == 200 else None
    me_after = client.get("/v1/users/me", headers={"Authorization": f"Bearer {new_access}"})
    check(
        "refresh token rotates into a working access token",
        bool(new_access) and me_after.status_code == 200,
        f"refresh http {refreshed.status_code}, me http {me_after.status_code}",
    )

    logout = client.post(
        "/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {new_access}"},
    )
    refreshed_again = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    check(
        "logout revokes the refresh token",
        logout.status_code in (200, 204) and refreshed_again.status_code == 401,
        f"logout http {logout.status_code}, refresh http {refreshed_again.status_code}",
    )

    # ---- 14. Cross-root admin isolation (DD-056) ----------------------------
    response = client.get(
        f"/v1/users/{auditor_id}",
        headers={"Authorization": f"Bearer {tokens['summit_admin']}"},
    )
    check(
        "other-root admin cannot read ACME user (404 anti-enumeration)",
        response.status_code == 404,
        f"http {response.status_code}",
    )

    return finish()


def finish() -> int:
    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n== {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed ==")
    if failed:
        print("FAILED:", *[f"  - {name}" for name in failed], sep="\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
