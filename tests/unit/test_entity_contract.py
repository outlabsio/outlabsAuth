from outlabs_auth.schemas.entity import (
    EntityCreateRequest,
    EntityResponse,
    EntityUpdateRequest,
)


def test_entity_schemas_match_live_persisted_contract():
    create_fields = EntityCreateRequest.model_fields
    update_fields = EntityUpdateRequest.model_fields
    response_fields = EntityResponse.model_fields

    for fields in (create_fields, update_fields, response_fields):
        assert "direct_permissions" not in fields
        assert "metadata" not in fields

    for field_name in (
        "valid_from",
        "valid_until",
        "allowed_child_classes",
        "allowed_child_types",
        "max_members",
    ):
        assert field_name in create_fields
        assert field_name in update_fields
        assert field_name in response_fields
