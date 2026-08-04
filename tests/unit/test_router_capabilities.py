from types import SimpleNamespace

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
import pytest

from outlabs_auth.routers import (
    assert_auth_surfaces,
    discover_mounted_auth_surfaces,
    get_capabilities_router,
    missing_auth_surfaces,
)
from outlabs_auth.routers.capabilities import mark_auth_surface


def _auth():
    config = SimpleNamespace(
        enable_entity_hierarchy=False,
        enable_context_aware_roles=False,
        enable_abac=False,
        enable_invitations=True,
        enable_magic_links=False,
        enable_access_codes=False,
    )
    return SimpleNamespace(config=config)


def _marked_router(surface: str) -> APIRouter:
    router = APIRouter()

    @router.get(f"/{surface}")
    async def endpoint():
        return {"surface": surface}

    return mark_auth_surface(router, surface)


def test_capabilities_report_only_actually_mounted_surfaces():
    app = FastAPI()
    app.include_router(get_capabilities_router(_auth(), prefix="/v1/auth"))
    app.include_router(_marked_router("session"), prefix="/v1")
    _marked_router("users")  # Constructed, but deliberately not included.

    response = TestClient(app).get("/v1/auth/config")

    assert response.status_code == 200
    assert response.json()["mounted_surfaces"] == ["capabilities", "session"]
    assert discover_mounted_auth_surfaces(app) == ["capabilities", "session"]
    assert missing_auth_surfaces(app, ["capabilities", "users"]) == ["users"]


def test_assert_auth_surfaces_is_a_host_contract_helper():
    app = FastAPI()
    app.include_router(_marked_router("audit"))

    assert_auth_surfaces(app, ["audit"])
    with pytest.raises(AssertionError, match="api_key_admin, users"):
        assert_auth_surfaces(app, ["users", "api_key_admin"])
