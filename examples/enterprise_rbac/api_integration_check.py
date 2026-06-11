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
