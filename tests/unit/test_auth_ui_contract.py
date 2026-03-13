from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text()


def test_users_api_uses_backend_supported_filters():
    users_api = _read("auth-ui/app/api/users.ts")

    assert "status: filters.status" in users_api
    assert "root_entity_id: filters.root_entity_id" in users_api
    assert "entity_id: filters.entity_id" not in users_api
    assert "sort_by: params.sort_by" not in users_api


def test_roles_api_sends_permission_arrays_and_root_entity_filter():
    roles_api = _read("auth-ui/app/api/roles.ts")

    assert "root_entity_id: filters.root_entity_id" in roles_api
    assert "JSON.stringify(permissions)" in roles_api
    assert "JSON.stringify({ permissions })" not in roles_api
    assert "entity_id: filters.entity_id" not in roles_api


def test_user_detail_form_only_submits_supported_profile_fields():
    user_detail = _read("auth-ui/app/pages/users/[id]/index.vue")

    assert "first_name: state.first_name || undefined" in user_detail
    assert "last_name: state.last_name || undefined" in user_detail
    assert "full_name" not in user_detail
    assert "metadata" not in user_detail
    assert "is_active" not in user_detail


def test_activity_page_no_longer_uses_placeholder_metrics():
    activity_page = _read("auth-ui/app/pages/users/[id]/activity.vue")

    assert "Daily Active User (DAU)" not in activity_page
    assert "These fields would be provided by backend" not in activity_page
    assert "last_login" in activity_page
    assert "last_activity" in activity_page
