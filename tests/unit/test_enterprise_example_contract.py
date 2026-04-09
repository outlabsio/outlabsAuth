from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_enterprise_example_does_not_shadow_auth_config_route():
    example_main = (ROOT / "examples/enterprise_rbac/main.py").read_text()

    assert '@app.get("/v1/auth/config"' not in example_main


def test_enterprise_example_wires_transactional_mail_service():
    example_main = (ROOT / "examples/enterprise_rbac/main.py").read_text()

    assert "transactional_mail_service=build_enterprise_example_transactional_mail_service(" in example_main
    assert "auth.user_service = RealEstateUserService(" not in example_main
    assert "Custom user service with invite/reset email hooks enabled" not in example_main
    assert "tables=[Lead.__table__, LeadNote.__table__]" in example_main
    assert 'get_team_directory_router(auth, prefix="/v1")' in example_main
    assert 'get_integration_principals_router(auth, prefix="/v1/admin")' in example_main


def test_enterprise_example_documents_host_query_integration_route():
    team_directory = (ROOT / "examples/enterprise_rbac/team_directory.py").read_text()

    assert "auth.host_query_service" in team_directory
    assert '"/entities/{entity_id}/team-directory"' in team_directory
    assert "without joining" in team_directory


def test_enterprise_example_reset_script_uses_migrations_and_full_data_clear():
    reset_script = (ROOT / "examples/enterprise_rbac/reset_test_env.py").read_text()

    assert "EnterpriseRBAC(" in reset_script
    assert "run_migrations(DATABASE_URL)" in reset_script
    assert "auto_migrate=False" in reset_script
    assert "TRUNCATE TABLE" in reset_script
    assert "outlabs_auth_alembic_version" in reset_script
    assert "tables=[Lead.__table__, LeadNote.__table__]" in reset_script
