from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_simple_example_does_not_shadow_auth_config_route():
    example_main = (ROOT / "examples/simple_rbac/main.py").read_text()

    assert '@app.get("/v1/auth/config"' not in example_main


def test_simple_example_mounts_shared_admin_routers_only():
    example_main = (ROOT / "examples/simple_rbac/main.py").read_text()

    assert "SimpleRBAC(" in example_main
    assert 'get_auth_router(auth_instance, prefix="/v1/auth"' in example_main
    assert 'get_users_router(auth_instance, prefix="/v1/users"' in example_main
    assert 'get_roles_router(auth_instance, prefix="/v1/roles"' in example_main
    assert 'get_permissions_router(auth_instance, prefix="/v1/permissions"' in example_main
    assert 'get_api_keys_router(auth_instance, prefix="/v1/api-keys"' in example_main

    assert "get_entities_router(" not in example_main
    assert "get_memberships_router(" not in example_main
    assert "get_config_router(" not in example_main
    assert "get_api_key_admin_router(" not in example_main
