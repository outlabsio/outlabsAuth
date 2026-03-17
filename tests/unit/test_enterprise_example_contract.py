from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_enterprise_example_does_not_shadow_auth_config_route():
    example_main = (ROOT / "examples/enterprise_rbac/main.py").read_text()

    assert '@app.get("/v1/auth/config"' not in example_main
