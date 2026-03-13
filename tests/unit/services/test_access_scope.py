from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from outlabs_auth.services.access_scope import AccessScopeService


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_for_user_prefers_direct_entities_for_member_projection(monkeypatch: pytest.MonkeyPatch):
    service = AccessScopeService(SimpleNamespace(enable_entity_hierarchy=True))
    root_entity_id = uuid4()
    direct_entity_id = uuid4()
    descendant_entity_id = uuid4()
    member_user_id = uuid4()
    principal_user_id = uuid4()
    captured: dict[str, object] = {}

    async def _fake_resolve_root_entity_ids(_session, *, user_id, user=None):
        assert user_id == principal_user_id
        return {root_entity_id}

    async def _fake_resolve_direct_entity_ids(_session, *, user_id):
        assert user_id == principal_user_id
        return {direct_entity_id}

    async def _fake_expand_descendant_entity_ids(_session, ancestor_entity_ids):
        assert ancestor_entity_ids == {root_entity_id, direct_entity_id}
        return {descendant_entity_id}

    async def _fake_resolve_member_user_ids(_session, entity_ids, *, include_descendants=False):
        captured["entity_ids"] = entity_ids
        captured["include_descendants"] = include_descendants
        return [member_user_id]

    monkeypatch.setattr(service, "_resolve_root_entity_ids", _fake_resolve_root_entity_ids)
    monkeypatch.setattr(service, "_resolve_direct_entity_ids", _fake_resolve_direct_entity_ids)
    monkeypatch.setattr(service, "_expand_descendant_entity_ids", _fake_expand_descendant_entity_ids)
    monkeypatch.setattr(service, "_resolve_member_user_ids", _fake_resolve_member_user_ids)

    scope = await service.resolve_for_user(SimpleNamespace(), principal_user_id)

    assert scope.source == "jwt"
    assert scope.includes_descendants is True
    assert set(scope.root_entity_ids) == {root_entity_id}
    assert set(scope.direct_entity_ids) == {direct_entity_id}
    assert set(scope.entity_ids) == {root_entity_id, direct_entity_id, descendant_entity_id}
    assert captured["entity_ids"] == [direct_entity_id]
    assert captured["include_descendants"] is True
    assert set(scope.member_user_ids) == {member_user_id, principal_user_id}
    assert set(scope.to_dict()["member_user_ids"]) == {str(member_user_id), str(principal_user_id)}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_for_api_key_includes_scoped_member_users(monkeypatch: pytest.MonkeyPatch):
    service = AccessScopeService(SimpleNamespace(enable_entity_hierarchy=True))
    principal_user_id = uuid4()
    api_key_id = uuid4()
    scoped_entity_id = uuid4()
    descendant_entity_id = uuid4()
    member_user_id = uuid4()
    captured: dict[str, object] = {}

    async def _fake_expand_descendant_entity_ids(_session, ancestor_entity_ids):
        assert ancestor_entity_ids == {scoped_entity_id}
        return {descendant_entity_id}

    async def _fake_resolve_member_user_ids(_session, entity_ids, *, include_descendants=False):
        captured["entity_ids"] = entity_ids
        captured["include_descendants"] = include_descendants
        return [member_user_id]

    monkeypatch.setattr(service, "_expand_descendant_entity_ids", _fake_expand_descendant_entity_ids)
    monkeypatch.setattr(service, "_resolve_member_user_ids", _fake_resolve_member_user_ids)

    scope = await service.resolve_for_api_key(
        SimpleNamespace(),
        api_key=SimpleNamespace(id=api_key_id, entity_id=scoped_entity_id, inherit_from_tree=True),
        principal_user_id=principal_user_id,
    )

    assert scope.api_key_id == api_key_id
    assert scope.api_key_entity_id == scoped_entity_id
    assert scope.includes_descendants is True
    assert set(scope.entity_ids) == {scoped_entity_id, descendant_entity_id}
    assert captured["entity_ids"] == [scoped_entity_id]
    assert captured["include_descendants"] is True
    assert set(scope.member_user_ids) == {member_user_id, principal_user_id}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_for_auth_result_superuser_is_global_and_keeps_principal_member():
    service = AccessScopeService(SimpleNamespace(enable_entity_hierarchy=True))
    principal_user_id = uuid4()

    payload = await service.resolve_for_auth_result(
        SimpleNamespace(),
        {
            "source": "jwt",
            "user_id": principal_user_id,
            "user": SimpleNamespace(id=principal_user_id, is_superuser=True),
        },
    )

    assert payload["is_global"] is True
    assert payload["principal_user_id"] == str(principal_user_id)
    assert payload["member_user_ids"] == [str(principal_user_id)]
