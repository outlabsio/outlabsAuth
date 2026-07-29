"""Unit tests for the DD-059 cross-repo route-contract helpers."""

import pytest

from outlabs_auth.frontend import FrontendProfile, FrontendRoutes
from outlabs_auth.frontend.contract import (
    assert_profile_routes,
    missing_frontend_routes,
    routes_from_nuxt_pages,
    routes_from_path_names,
    routes_from_route_constants,
    routes_from_tanstack_route_dir,
    template_path,
)


def _profile(**routes) -> FrontendProfile:
    return FrontendProfile(
        key="console",
        app_name="Console",
        public_origins=("https://console.example.com",),
        routes=FrontendRoutes(**routes),
    )


@pytest.mark.unit
def test_template_path_strips_query_and_keeps_path_tokens():
    assert template_path("/auth/reset-password?token={token}") == "/auth/reset-password"
    assert template_path("/recovery/{token}") == "/recovery/{token}"
    assert template_path("/login") == "/login"


@pytest.mark.unit
def test_missing_routes_reports_only_declared_absent_paths():
    profile = _profile(
        login="/login",
        password_reset="/recovery/{token}",
        accept_invite=None,
    )
    missing = missing_frontend_routes(profile, {"/login"})
    assert missing == {"password_reset": "/recovery/{token}"}

    with pytest.raises(AssertionError) as excinfo:
        assert_profile_routes(profile, {"/login"})
    assert "password_reset" in str(excinfo.value)

    assert_profile_routes(profile, {"/login", "/recovery/{token}"})
    assert_profile_routes(profile, {"/login"}, ignore={"password_reset"})


@pytest.mark.unit
def test_nuxt_adapter_maps_params_and_indexes(tmp_path):
    (tmp_path / "recovery").mkdir()
    (tmp_path / "recovery" / "[token].vue").write_text("", encoding="utf-8")
    (tmp_path / "login").mkdir()
    (tmp_path / "login" / "index.vue").write_text("", encoding="utf-8")
    (tmp_path / "accept-invite.vue").write_text("", encoding="utf-8")

    assert routes_from_nuxt_pages(tmp_path) == {
        "/recovery/{token}",
        "/login",
        "/accept-invite",
    }
    assert routes_from_path_names(["recovery/[token].vue", "login/index.vue"]) == {
        "/recovery/{token}",
        "/login",
    }


@pytest.mark.unit
def test_tanstack_adapter_maps_dotted_files(tmp_path):
    for name in ("auth.sign-in.tsx", "auth.reset-password.tsx", "__root.tsx", "index.tsx"):
        (tmp_path / name).write_text("", encoding="utf-8")

    assert routes_from_tanstack_route_dir(tmp_path) == {
        "/auth/sign-in",
        "/auth/reset-password",
        "/",
    }


@pytest.mark.unit
def test_constants_adapter_extracts_absolute_paths(tmp_path):
    source = tmp_path / "routes.ts"
    source.write_text(
        "export const ROUTES = { login: '/auth/login', reset: \"/auth/reset-password\" }\n"
        "const notARoute = 'auth/relative'\n",
        encoding="utf-8",
    )
    assert routes_from_route_constants(source) == {"/auth/login", "/auth/reset-password"}
