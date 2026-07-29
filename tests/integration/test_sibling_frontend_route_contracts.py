"""Cross-repository route contracts for the known consumer frontends (DD-059).

Each test asserts that the frontend profile a host is expected to declare
matches the routes the actual frontend repository implements TODAY — the
executable version of section 8 of docs/MULTI_FRONTEND_SUPPORT.md. Tests
skip when the sibling checkout is not present on this machine, so CI without
the fleet stays green while developer machines get the real check.

These declarations are the reference profiles for the consumer migrations;
when a host adopts profiles it should copy this shape and carry its own
contract test.
"""

import subprocess
from pathlib import Path

import pytest

from outlabs_auth.frontend import FrontendProfile, FrontendRoutes
from outlabs_auth.frontend.contract import (
    assert_profile_routes,
    routes_from_path_names,
    routes_from_route_constants,
    routes_from_tanstack_route_dir,
)

PROJECTS = Path.home() / "Documents" / "projects"


def _skip_unless(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"sibling checkout not present: {path}")


def _nuxt_routes_from_git(repo: Path, ref: str, pages_dir: str) -> set[str]:
    """Nuxt page routes read from a git ref, independent of the checked-out branch."""
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", ref, "--", pages_dir],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"ref {ref!r} unavailable in {repo}: {result.stderr.strip()}")
    names = [
        line[len(pages_dir) :].lstrip("/")
        for line in result.stdout.splitlines()
        if line.startswith(pages_dir)
    ]
    return routes_from_path_names(names)


@pytest.mark.integration
def test_outlabs_auth_ui_console_profile_contract():
    repo = PROJECTS / "OutlabsAuthUI"
    constants = repo / "src" / "lib" / "constants" / "routes.ts"
    _skip_unless(constants)

    profile = FrontendProfile(
        key="console",
        app_name="Auth Console",
        public_origins=("https://auth.example.com",),
        routes=FrontendRoutes(
            login="/auth/login",
            password_reset="/auth/reset-password?token={token}",
            accept_invite="/auth/accept-invite?token={token}",
            magic_link="/auth/magic-link?token={token}",
            access_code="/auth/access-code",
            oauth_success="/auth/oauth/callback",
        ),
    )
    assert_profile_routes(profile, routes_from_route_constants(constants))


@pytest.mark.integration
def test_referral_collection_profile_contract():
    repo = PROJECTS / "diverse-referral-collection"
    routes_dir = repo / "src" / "app" / "router" / "routes"
    _skip_unless(routes_dir)

    available = routes_from_tanstack_route_dir(routes_dir)
    profile = FrontendProfile(
        key="referral-collection",
        app_name="Referral Collection",
        public_origins=("https://staging.referralcollection.com",),
        routes=FrontendRoutes(
            # The audited truth: RC signs in at /auth/sign-in (NOT /auth/login,
            # which the d09eb10 workaround wrongly assumed) and has no
            # accept-invite page — self-serve signup only.
            login="/auth/sign-in",
            password_reset="/auth/reset-password?token={token}",
            accept_invite=None,
        ),
    )
    assert_profile_routes(profile, available)
    assert "/auth/login" not in available, (
        "RC grew an /auth/login route; revisit the profile and the workaround notes"
    )


@pytest.mark.integration
def test_agent_portal_profile_contract():
    repo = PROJECTS / "agentPanel"
    _skip_unless(repo)

    available = _nuxt_routes_from_git(repo, "origin/postgres", "app/pages")
    profile = FrontendProfile(
        key="portal",
        app_name="Agent Portal",
        public_origins=("https://portal.meetdiverse.com",),
        routes=FrontendRoutes(
            login="/login",
            password_reset="/recovery/{token}",
            # Audited gap: the portal has no accept-invite page, so agent
            # invites cannot land here until it ships one.
            accept_invite=None,
        ),
    )
    assert_profile_routes(profile, available)
    assert "/accept-invite" not in available, (
        "agentPanel gained an accept-invite page — flip the portal profile's "
        "accept_invite route on and route agent invites to the portal"
    )


@pytest.mark.integration
def test_admin_console_profile_contract():
    repo = PROJECTS / "DiverseAdminPanel"
    _skip_unless(repo)

    available = _nuxt_routes_from_git(repo, "origin/postgres", "app/pages")
    profile = FrontendProfile(
        key="admin-console",
        app_name="Diverse Console",
        public_origins=("https://admin.meetdiverse.com",),
        routes=FrontendRoutes(
            login="/login",
            password_reset="/recovery/{token}",
            accept_invite="/accept-invite?token={token}",
        ),
    )
    assert_profile_routes(profile, available)
