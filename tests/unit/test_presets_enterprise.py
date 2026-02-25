import warnings

from outlabs_auth.presets import EnterpriseRBAC


def test_enterprise_preset_init_has_no_legacy_migration_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        auth = EnterpriseRBAC(
            database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test",
            secret_key="test-secret-key",
        )

    messages = [str(item.message) for item in caught]
    assert not messages
    assert auth.config.enable_entity_hierarchy is True
