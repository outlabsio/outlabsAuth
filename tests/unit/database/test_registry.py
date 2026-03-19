from __future__ import annotations

from sqlmodel import SQLModel

from outlabs_auth.database.registry import ModelRegistry


def _names(models) -> set[str]:
    return {model.__name__ for model in models}


def test_model_registry_names_and_tables_reflect_simple_and_enterprise_presets():
    simple_names = ModelRegistry.get_model_names(enable_entity_hierarchy=False)
    enterprise_names = ModelRegistry.get_model_names(enable_entity_hierarchy=True)
    simple_tables = ModelRegistry.get_table_names(enable_entity_hierarchy=False)
    enterprise_tables = ModelRegistry.get_table_names(enable_entity_hierarchy=True)

    assert "UserRoleMembership" in simple_names
    assert "UserRoleMembership" not in enterprise_names
    assert "EntityMembership" in enterprise_names
    assert "EntityMembershipHistory" in enterprise_names

    assert "user_role_memberships" in simple_tables
    assert "entities" not in simple_tables
    assert "entities" in enterprise_tables
    assert "entity_membership_history" in enterprise_tables


def test_model_registry_get_models_includes_all_core_and_preset_specific_models():
    simple_models = _names(ModelRegistry.get_models(enable_entity_hierarchy=False))
    enterprise_models = _names(ModelRegistry.get_models(enable_entity_hierarchy=True))

    core_expected = {
        "User",
        "Role",
        "Permission",
        "RefreshToken",
        "APIKey",
        "SocialAccount",
        "OAuthState",
        "ActivityMetric",
        "RoleDefinitionHistory",
        "PermissionDefinitionHistory",
        "UserAuditEvent",
    }

    assert core_expected.issubset(simple_models)
    assert core_expected.issubset(enterprise_models)
    assert "UserRoleMembership" in simple_models
    assert "UserRoleMembership" not in enterprise_models
    assert {"Entity", "EntityMembership", "EntityClosure", "EntityMembershipHistory"}.issubset(
        enterprise_models
    )


def test_model_registry_get_metadata_returns_sqlmodel_metadata(monkeypatch):
    calls: list[bool] = []

    def fake_get_models(*, enable_entity_hierarchy: bool = False):
        calls.append(enable_entity_hierarchy)
        return []

    monkeypatch.setattr(ModelRegistry, "get_models", fake_get_models)

    metadata = ModelRegistry.get_metadata(enable_entity_hierarchy=True)

    assert metadata is SQLModel.metadata
    assert calls == [True]
