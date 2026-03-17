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


def test_legacy_auth_ui_entity_types_match_backend_entity_contract():
    entity_types = _read("auth-ui/app/types/entity.ts")

    assert "direct_permissions" not in entity_types
    assert "metadata" not in entity_types
    assert "valid_from" in entity_types
    assert "valid_until" in entity_types
    assert "allowed_child_types" in entity_types
    assert "max_members" in entity_types


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


def test_settings_profile_updates_supported_me_fields_only():
    profile_page = _read("auth-ui/app/pages/settings/profile.vue")

    assert "authStore.apiCall('/v1/users/me'" in profile_page
    assert "first_name:" in profile_page
    assert "last_name:" in profile_page
    assert "simulate API call" not in profile_page
    assert "metadata" not in profile_page
    assert "username" not in profile_page
    assert "department" not in profile_page
    assert "Job Title" not in profile_page


def test_settings_index_removes_placeholder_controls_and_uses_backend_config():
    settings_page = _read("auth-ui/app/pages/settings/index.vue")

    assert "Mock Mode" not in settings_page
    assert "Email Notifications" not in settings_page
    assert "Delete Account" not in settings_page
    assert "Using mock data for development" not in settings_page
    assert "Enabled Capabilities" in settings_page
    assert "authStore.features" in settings_page


def test_settings_security_uses_real_security_signals():
    security_page = _read("auth-ui/app/pages/settings/security.vue")

    assert "simulate API call" not in security_page
    assert "Active Sessions" not in security_page
    assert "Authenticator App" not in security_page
    assert "Enable 2FA" not in security_page
    assert "last_password_change" in security_page
    assert "locked_until" in security_page
    assert "suspended_until" in security_page
    assert "last_login" in security_page
    assert "last_activity" in security_page
    assert 'to="/settings/password"' in security_page


def test_user_menu_uses_supported_avatar_field():
    user_menu = _read("auth-ui/app/components/UserMenu.vue")

    assert "avatar_url" in user_menu
    assert "metadata" not in user_menu


def test_api_key_surfaces_match_current_backend_contract():
    api_keys_api = _read("auth-ui/app/api/api-keys.ts")
    api_keys_queries = _read("auth-ui/app/queries/api-keys.ts")
    create_modal = _read("auth-ui/app/components/ApiKeyCreateModal.vue")
    update_modal = _read("auth-ui/app/components/ApiKeyUpdateModal.vue")
    detail_modal = _read("auth-ui/app/components/ApiKeyDetailModal.vue")
    api_keys_page = _read("auth-ui/app/pages/api-keys/index.vue")

    assert "501 Not Implemented" not in api_keys_api
    assert "Rotation not yet implemented" not in api_keys_queries
    assert "rate_limit_per_hour" not in create_modal
    assert "rate_limit_per_day" not in create_modal
    assert "expires_in_days" in create_modal
    assert "rate_limit_per_hour" not in update_modal
    assert "rate_limit_per_day" not in update_modal
    assert "never_expires" not in update_modal
    assert 'type="datetime-local"' not in update_modal
    assert 'requestKeyAction("rotate"' in api_keys_page
    assert 'label="Export"' not in api_keys_page
    assert 'label="Rotate Key"' in detail_modal


def test_abac_editor_is_wired_to_backend_role_and_permission_routes():
    abac_api = _read("auth-ui/app/api/abac.ts")
    abac_editor = _read("auth-ui/app/components/AbacConditionsEditor.vue")
    role_modal = _read("auth-ui/app/components/RoleUpdateModal.vue")
    permission_modal = _read("auth-ui/app/components/PermissionUpdateModal.vue")
    abac_types = _read("auth-ui/app/types/abac.ts")

    assert "/condition-groups" in abac_api
    assert "/conditions" in abac_api
    assert 'targetType === "role" ? "/v1/roles" : "/v1/permissions"' in abac_api
    assert "ABAC Conditions" in abac_editor
    assert "useCreateConditionGroupMutation" in abac_editor
    assert "useCreateConditionMutation" in abac_editor
    assert "Group removal not supported" not in abac_editor
    assert "condition_group_id?: string | null;" in abac_types
    assert "AbacConditionsEditor" in role_modal
    assert 'target-type="role"' in role_modal
    assert "AbacConditionsEditor" in permission_modal
    assert 'target-type="permission"' in permission_modal


def test_permissions_page_allows_editing_system_permissions_but_not_deleting_them():
    permissions_page = _read("auth-ui/app/pages/permissions/index.vue")
    roles_page = _read("auth-ui/app/pages/roles/index.vue")

    assert "System permissions cannot be edited" not in permissions_page
    assert "disabled: row.original.is_system," not in permissions_page
    assert "System permissions cannot be deleted" in permissions_page
    assert "disabled: row.original.is_system || isDeleting" in permissions_page
    assert 'label="Filter"' not in permissions_page
    assert 'label="Export"' not in permissions_page
    assert "// TODO: Add confirmation dialog" not in permissions_page
    assert 'label="Export"' not in roles_page


def test_dashboard_uses_real_backend_signals_instead_of_placeholder_activity_feed():
    dashboard = _read("auth-ui/app/pages/dashboard.vue")

    assert "Recent Activity" not in dashboard
    assert "No recent activity to display." not in dashboard
    assert "Account Signals" in dashboard
    assert "Enabled Capabilities" in dashboard
    assert "last_login" in dashboard
    assert "last_activity" in dashboard
    assert "last_password_change" in dashboard
    assert "authStore.features" in dashboard
