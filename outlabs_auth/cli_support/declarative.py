"""Declarative state planning, drift detection, and ordered application."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from outlabs_auth.cli_support.client import RemoteClient, RemoteTarget
from outlabs_auth.cli_support.runtime import (
    CliError,
    EXIT_CONFLICT,
    EXIT_OPERATION_FAILED,
    EXIT_PARTIAL,
    EXIT_USAGE,
)

MANIFEST_VERSION = "outlabs-auth.state/v1alpha1"
PLAN_VERSION = "outlabs-auth.plan/v1alpha1"

_RESOURCE_ORDER = ("permissions", "entities", "roles", "memberships")
_PERMISSION_FIELDS = (
    "display_name",
    "description",
    "is_system",
    "status",
    "is_active",
    "tags",
)
_ENTITY_FIELDS = (
    "name",
    "display_name",
    "description",
    "entity_class",
    "entity_type",
    "status",
    "valid_from",
    "valid_until",
    "allowed_child_classes",
    "allowed_child_types",
    "max_members",
    "child_name_pattern",
    "child_display_name_pattern",
    "child_slug_pattern",
    "child_naming_guidance",
)
_ROLE_FIELDS = (
    "display_name",
    "description",
    "permissions",
    "is_global",
    "status",
    "assignable_at_types",
    "scope",
    "is_auto_assigned",
)
_MEMBERSHIP_FIELDS = ("status", "valid_from", "valid_until")
_ALLOWED_ITEM_FIELDS = {
    "permissions": {"name", "state", *_PERMISSION_FIELDS},
    "entities": {"slug", "state", "parent", *_ENTITY_FIELDS},
    "roles": {"name", "state", "root_entity", "scope_entity", *_ROLE_FIELDS},
    "memberships": {"user", "entity", "state", "roles", "reason", *_MEMBERSHIP_FIELDS},
}


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        normalized = [_canonical(item) for item in value]
        if all(isinstance(item, (str, int, float, bool)) or item is None for item in normalized):
            return sorted(normalized, key=lambda item: (type(item).__name__, str(item)))
        return normalized
    return value


def object_hash(value: Any) -> str:
    encoded = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def validate_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("api_version") != MANIFEST_VERSION or raw.get("kind") != "OutlabsAuthState":
        raise CliError(
            code="INVALID_STATE_MANIFEST",
            message="State manifest api_version or kind is unsupported.",
            exit_code=EXIT_USAGE,
            details={"expected_api_version": MANIFEST_VERSION, "expected_kind": "OutlabsAuthState"},
        )
    spec = raw.get("spec")
    if not isinstance(spec, dict):
        raise CliError(
            code="INVALID_STATE_MANIFEST",
            message="State manifest spec must be an object.",
            exit_code=EXIT_USAGE,
        )
    unknown = sorted(set(spec) - set(_RESOURCE_ORDER))
    if unknown:
        raise CliError(
            code="UNKNOWN_STATE_RESOURCE",
            message="State manifest contains unknown resource groups.",
            exit_code=EXIT_USAGE,
            details={"resources": unknown, "allowed": list(_RESOURCE_ORDER)},
        )
    normalized: dict[str, list[dict[str, Any]]] = {}
    identity_fields = {
        "permissions": ("name",),
        "entities": ("slug",),
        "roles": ("name",),
        "memberships": ("user", "entity"),
    }
    for resource in _RESOURCE_ORDER:
        items = spec.get(resource, [])
        if not isinstance(items, list):
            raise CliError(
                code="INVALID_STATE_MANIFEST",
                message=f"spec.{resource} must be an array.",
                exit_code=EXIT_USAGE,
            )
        parsed: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise CliError(
                    code="INVALID_STATE_MANIFEST",
                    message=f"spec.{resource}[{index}] must be an object.",
                    exit_code=EXIT_USAGE,
                )
            state = item.get("state", "present")
            if state not in {"present", "absent"}:
                raise CliError(
                    code="INVALID_RESOURCE_STATE",
                    message=f"spec.{resource}[{index}].state must be present or absent.",
                    exit_code=EXIT_USAGE,
                )
            unknown_fields = sorted(set(item) - _ALLOWED_ITEM_FIELDS[resource])
            if unknown_fields:
                raise CliError(
                    code="UNKNOWN_DECLARATIVE_FIELD",
                    message=f"spec.{resource}[{index}] contains unknown fields.",
                    exit_code=EXIT_USAGE,
                    details={"fields": unknown_fields},
                )
            missing = [
                field for field in identity_fields[resource] if not isinstance(item.get(field), str) or not item[field]
            ]
            if missing:
                raise CliError(
                    code="DECLARATIVE_IDENTITY_MISSING",
                    message=f"spec.{resource}[{index}] is missing identity fields.",
                    exit_code=EXIT_USAGE,
                    details={"fields": missing},
                )
            identity = _identity(resource, item)
            if identity in seen:
                raise CliError(
                    code="DUPLICATE_DECLARATIVE_IDENTITY",
                    message=f"spec.{resource} contains duplicate identity '{identity}'.",
                    exit_code=EXIT_USAGE,
                )
            seen.add(identity)
            parsed.append(dict(item) | {"state": state})
        normalized[resource] = parsed
    return normalized


def _identity(resource: str, item: dict[str, Any]) -> str:
    if resource == "permissions":
        return str(item["name"])
    if resource == "entities":
        return str(item["slug"])
    if resource == "roles":
        return str(item["name"])
    return f"{str(item['user']).casefold()}@{str(item['entity']).casefold()}"


def _items_by_identity(resource: str, items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        try:
            result[_identity(resource, item).casefold()] = item
        except KeyError:
            continue
    return result


def _fetch_snapshot(client: RemoteClient, desired: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    needs_permissions = bool(desired["permissions"])
    needs_entities = bool(
        desired["entities"]
        or desired["memberships"]
        or any(item.get("root_entity") or item.get("scope_entity") for item in desired["roles"])
    )
    needs_roles = bool(desired["roles"] or desired["memberships"])
    needs_users = bool(desired["memberships"])

    permission_items: list[dict[str, Any]] = []
    entity_items: list[dict[str, Any]] = []
    role_items: list[dict[str, Any]] = []
    user_items: list[dict[str, Any]] = []
    if needs_permissions:
        permissions, _ = client.paginate("/permissions/", all_pages=True, max_limit=1000)
        permission_items = [item for item in permissions["items"] if isinstance(item, dict)]
    if needs_entities:
        entities, _ = client.paginate("/entities/", all_pages=True, max_limit=1000)
        entity_items = [item for item in entities["items"] if isinstance(item, dict)]
    if needs_roles:
        roles, _ = client.paginate("/roles/", all_pages=True, max_limit=100)
        role_items = [item for item in roles["items"] if isinstance(item, dict)]
    if needs_users:
        users, _ = client.paginate("/users/", all_pages=True, max_limit=100)
        user_items = [item for item in users["items"] if isinstance(item, dict)]

    users_by_email = {str(item.get("email", "")).casefold(): item for item in user_items if item.get("email")}
    entities_by_slug = {str(item.get("slug", "")).casefold(): item for item in entity_items if item.get("slug")}
    membership_items: list[dict[str, Any]] = []
    fetched_users: set[str] = set()
    for desired_membership in desired["memberships"]:
        email_key = str(desired_membership["user"]).casefold()
        user = users_by_email.get(email_key)
        if user is None:
            if desired_membership["state"] == "absent":
                continue
            raise CliError(
                code="DECLARATIVE_REFERENCE_NOT_FOUND",
                message=f"Membership user '{desired_membership['user']}' does not exist.",
                exit_code=EXIT_USAGE,
            )
        if str(user["id"]) in fetched_users:
            continue
        result, _ = client.request(
            "GET",
            f"/memberships/user/{user['id']}",
            params={"page": 1, "limit": 100, "include_inactive": True},
        )
        if not isinstance(result, list):
            raise CliError(
                code="REMOTE_PROTOCOL_ERROR",
                message="The memberships endpoint returned an invalid response.",
                exit_code=EXIT_OPERATION_FAILED,
            )
        for membership in result:
            if not isinstance(membership, dict):
                continue
            entity = next(
                (item for item in entity_items if str(item.get("id")) == str(membership.get("entity_id"))),
                None,
            )
            if entity:
                membership_items.append(dict(membership) | {"user": user["email"], "entity": entity["slug"]})
        fetched_users.add(str(user["id"]))

    return {
        "permissions": permission_items,
        "entities": entity_items,
        "roles": role_items,
        "users": user_items,
        "memberships": membership_items,
        "users_by_email": users_by_email,
        "entities_by_slug": entities_by_slug,
    }


def _ref(resource: str, identity: str) -> dict[str, Any]:
    return {"$outlabs_ref": {"resource": resource, "identity": identity}}


def _lookup_or_ref(
    *,
    resource: str,
    identity: str,
    current: dict[str, dict[str, Any]],
    desired_present: set[str],
) -> Any:
    item = current.get(identity.casefold())
    if item is not None:
        return item["id"]
    if identity.casefold() in desired_present:
        return _ref(resource, identity)
    raise CliError(
        code="DECLARATIVE_REFERENCE_NOT_FOUND",
        message=f"Referenced {resource} '{identity}' is neither present nor declared.",
        exit_code=EXIT_USAGE,
    )


def _managed_diff(current: dict[str, Any], desired: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in fields:
        if field in desired and _canonical(current.get(field)) != _canonical(desired[field]):
            result[field] = desired[field]
    return result


def _operation(
    *,
    resource: str,
    identity: str,
    action: str,
    method: str,
    path: str,
    body: Any,
    before: Optional[dict[str, Any]],
    summary: str,
    destructive: bool = False,
) -> dict[str, Any]:
    return {
        "id": f"{resource}:{identity}:{action}",
        "resource": resource,
        "identity": identity,
        "action": action,
        "method": method,
        "path": path,
        "body": body,
        "before_hash": object_hash(before) if before is not None else None,
        "before": before,
        "destructive": destructive,
        "summary": summary,
    }


def _topological_entities(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending = {_identity("entities", item).casefold(): item for item in items}
    ordered: list[dict[str, Any]] = []
    resolved: set[str] = set()
    while pending:
        ready = [
            key
            for key, item in pending.items()
            if not item.get("parent")
            or str(item["parent"]).casefold() not in pending
            or str(item["parent"]).casefold() in resolved
        ]
        if not ready:
            raise CliError(
                code="DECLARATIVE_ENTITY_CYCLE",
                message="Declared entity parent references contain a cycle.",
                exit_code=EXIT_USAGE,
                details={"entities": sorted(pending)},
            )
        for key in sorted(ready):
            ordered.append(pending.pop(key))
            resolved.add(key)
    return ordered


def build_plan(
    client: RemoteClient,
    target: RemoteTarget,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    desired = validate_manifest(manifest)
    snapshot = _fetch_snapshot(client, desired)
    current_permissions = _items_by_identity("permissions", snapshot["permissions"])
    current_entities = _items_by_identity("entities", snapshot["entities"])
    current_roles = _items_by_identity("roles", snapshot["roles"])
    current_memberships = _items_by_identity("memberships", snapshot["memberships"])
    desired_entities_present = {
        _identity("entities", item).casefold() for item in desired["entities"] if item["state"] == "present"
    }
    desired_roles_present = {
        _identity("roles", item).casefold() for item in desired["roles"] if item["state"] == "present"
    }

    permission_ops: list[dict[str, Any]] = []
    permission_deletes: list[dict[str, Any]] = []
    for item in desired["permissions"]:
        identity = _identity("permissions", item)
        current = current_permissions.get(identity.casefold())
        if item["state"] == "absent":
            if current:
                permission_deletes.append(
                    _operation(
                        resource="permissions",
                        identity=identity,
                        action="delete",
                        method="DELETE",
                        path=f"/permissions/{current['id']}",
                        body=None,
                        before=current,
                        summary=f"Archive permission {identity}",
                        destructive=True,
                    )
                )
            continue
        body = {field: item[field] for field in ("name", *_PERMISSION_FIELDS) if field in item}
        if current is None:
            if "display_name" not in body:
                raise _missing_create_fields("permission", identity, ["display_name"])
            permission_ops.append(
                _operation(
                    resource="permissions",
                    identity=identity,
                    action="create",
                    method="POST",
                    path="/permissions/",
                    body=body,
                    before=None,
                    summary=f"Create permission {identity}",
                )
            )
        else:
            changes = _managed_diff(current, item, _PERMISSION_FIELDS)
            if changes:
                permission_ops.append(
                    _operation(
                        resource="permissions",
                        identity=identity,
                        action="update",
                        method="PATCH",
                        path=f"/permissions/{current['id']}",
                        body=changes,
                        before=current,
                        summary=f"Update permission {identity}: {', '.join(sorted(changes))}",
                    )
                )

    entity_ops: list[dict[str, Any]] = []
    entity_deletes: list[dict[str, Any]] = []
    present_entities = [item for item in desired["entities"] if item["state"] == "present"]
    for item in _topological_entities(present_entities):
        identity = _identity("entities", item)
        current = current_entities.get(identity.casefold())
        parent_ref = item.get("parent")
        parent_id = None
        if isinstance(parent_ref, str) and parent_ref:
            parent_id = _lookup_or_ref(
                resource="entities",
                identity=parent_ref,
                current=current_entities,
                desired_present=desired_entities_present,
            )
        body = {field: item[field] for field in ("slug", *_ENTITY_FIELDS) if field in item}
        if current is None:
            missing = [field for field in ("name", "display_name", "entity_class", "entity_type") if field not in body]
            if missing:
                raise _missing_create_fields("entity", identity, missing)
            if parent_ref is not None:
                body["parent_entity_id"] = parent_id
            entity_ops.append(
                _operation(
                    resource="entities",
                    identity=identity,
                    action="create",
                    method="POST",
                    path="/entities/",
                    body=body,
                    before=None,
                    summary=f"Create entity {identity}",
                )
            )
        else:
            changes = _managed_diff(current, item, _ENTITY_FIELDS)
            if changes:
                entity_ops.append(
                    _operation(
                        resource="entities",
                        identity=identity,
                        action="update",
                        method="PATCH",
                        path=f"/entities/{current['id']}",
                        body=changes,
                        before=current,
                        summary=f"Update entity {identity}: {', '.join(sorted(changes))}",
                    )
                )
            if "parent" in item and _canonical(current.get("parent_entity_id")) != _canonical(parent_id):
                entity_ops.append(
                    _operation(
                        resource="entities",
                        identity=identity,
                        action="move",
                        method="POST",
                        path=f"/entities/{current['id']}/move",
                        body={"new_parent_id": parent_id},
                        before=current,
                        summary=f"Move entity {identity} under {parent_ref or 'root'}",
                    )
                )
    for item in desired["entities"]:
        if item["state"] != "absent":
            continue
        identity = _identity("entities", item)
        current = current_entities.get(identity.casefold())
        if current:
            entity_deletes.append(
                _operation(
                    resource="entities",
                    identity=identity,
                    action="delete",
                    method="DELETE",
                    path=f"/entities/{current['id']}",
                    body=None,
                    before=current,
                    summary=f"Archive entity {identity}",
                    destructive=True,
                )
            )

    role_ops: list[dict[str, Any]] = []
    role_deletes: list[dict[str, Any]] = []
    for item in desired["roles"]:
        identity = _identity("roles", item)
        current = current_roles.get(identity.casefold())
        if item["state"] == "absent":
            if current:
                role_deletes.append(
                    _operation(
                        resource="roles",
                        identity=identity,
                        action="delete",
                        method="DELETE",
                        path=f"/roles/{current['id']}",
                        body=None,
                        before=current,
                        summary=f"Archive role {identity}",
                        destructive=True,
                    )
                )
            continue
        body = {field: item[field] for field in ("name", *_ROLE_FIELDS) if field in item}
        for source, destination in (("root_entity", "root_entity_id"), ("scope_entity", "scope_entity_id")):
            if source in item:
                reference = item[source]
                body[destination] = (
                    _lookup_or_ref(
                        resource="entities",
                        identity=str(reference),
                        current=current_entities,
                        desired_present=desired_entities_present,
                    )
                    if reference
                    else None
                )
        if current is None:
            if "display_name" not in body:
                raise _missing_create_fields("role", identity, ["display_name"])
            role_ops.append(
                _operation(
                    resource="roles",
                    identity=identity,
                    action="create",
                    method="POST",
                    path="/roles/",
                    body=body,
                    before=None,
                    summary=f"Create role {identity}",
                )
            )
        else:
            changes = _managed_diff(current, item, _ROLE_FIELDS)
            if changes:
                role_ops.append(
                    _operation(
                        resource="roles",
                        identity=identity,
                        action="update",
                        method="PATCH",
                        path=f"/roles/{current['id']}",
                        body=changes,
                        before=current,
                        summary=f"Update role {identity}: {', '.join(sorted(changes))}",
                    )
                )

    membership_ops: list[dict[str, Any]] = []
    membership_deletes: list[dict[str, Any]] = []
    users_by_email = snapshot["users_by_email"]
    for item in desired["memberships"]:
        identity = _identity("memberships", item)
        current = current_memberships.get(identity.casefold())
        if item["state"] == "absent":
            if current:
                membership_deletes.append(
                    _operation(
                        resource="memberships",
                        identity=identity,
                        action="delete",
                        method="DELETE",
                        path=f"/memberships/{current['entity_id']}/{current['user_id']}",
                        body=None,
                        before=current,
                        summary=f"Revoke membership {identity}",
                        destructive=True,
                    )
                )
            continue
        user = users_by_email.get(str(item["user"]).casefold())
        if user is None:
            raise CliError(
                code="DECLARATIVE_REFERENCE_NOT_FOUND",
                message=f"Membership user '{item['user']}' does not exist.",
                exit_code=EXIT_USAGE,
            )
        entity_id = _lookup_or_ref(
            resource="entities",
            identity=str(item["entity"]),
            current=current_entities,
            desired_present=desired_entities_present,
        )
        roles = item.get("roles", [])
        if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
            raise CliError(
                code="INVALID_STATE_MANIFEST",
                message=f"Membership {identity} roles must be an array of role names.",
                exit_code=EXIT_USAGE,
            )
        role_ids = [
            _lookup_or_ref(
                resource="roles",
                identity=role,
                current=current_roles,
                desired_present=desired_roles_present,
            )
            for role in roles
        ]
        if current is None:
            body = {
                "user_id": user["id"],
                "entity_id": entity_id,
                "role_ids": role_ids,
                **{field: item[field] for field in _MEMBERSHIP_FIELDS if field in item},
            }
            if "reason" in item:
                body["reason"] = item["reason"]
            membership_ops.append(
                _operation(
                    resource="memberships",
                    identity=identity,
                    action="create",
                    method="POST",
                    path="/memberships/",
                    body=body,
                    before=None,
                    summary=f"Create membership {identity}",
                )
            )
        else:
            desired_update = {field: item[field] for field in _MEMBERSHIP_FIELDS if field in item}
            if "roles" in item:
                desired_update["role_ids"] = role_ids
            changes = {
                field: value
                for field, value in desired_update.items()
                if _canonical(current.get(field)) != _canonical(value)
            }
            if changes and "reason" in item:
                changes["reason"] = item["reason"]
            if changes:
                membership_ops.append(
                    _operation(
                        resource="memberships",
                        identity=identity,
                        action="update",
                        method="PATCH",
                        path=f"/memberships/{current['entity_id']}/{current['user_id']}",
                        body=changes,
                        before=current,
                        summary=f"Update membership {identity}: {', '.join(sorted(changes))}",
                    )
                )

    parent_by_id = {
        str(item.get("id")): str(item.get("parent_entity_id")) if item.get("parent_entity_id") else None
        for item in snapshot["entities"]
    }

    def entity_depth(operation: dict[str, Any]) -> int:
        current = operation.get("before") or {}
        parent_id = current.get("parent_entity_id")
        depth = 0
        visited: set[str] = set()
        while parent_id and str(parent_id) not in visited:
            visited.add(str(parent_id))
            depth += 1
            parent_id = parent_by_id.get(str(parent_id))
        return depth

    entity_deletes.sort(key=entity_depth, reverse=True)

    operations = (
        permission_ops
        + entity_ops
        + role_ops
        + membership_ops
        + membership_deletes
        + role_deletes
        + entity_deletes
        + permission_deletes
    )
    return {
        "plan_version": PLAN_VERSION,
        "created_at": _utc_now(),
        "target": {
            "profile": target.name,
            "base_url": target.base_url,
            "api_prefix": target.api_prefix,
        },
        "manifest_hash": object_hash(manifest),
        "operations": operations,
        "summary": {
            "operation_count": len(operations),
            "create": sum(op["action"] == "create" for op in operations),
            "update": sum(op["action"] in {"update", "move"} for op in operations),
            "delete": sum(op["action"] == "delete" for op in operations),
            "destructive": sum(bool(op["destructive"]) for op in operations),
        },
    }


def _missing_create_fields(resource: str, identity: str, fields: list[str]) -> CliError:
    return CliError(
        code="DECLARATIVE_CREATE_FIELDS_MISSING",
        message=f"Cannot create {resource} '{identity}' without required fields.",
        exit_code=EXIT_USAGE,
        details={"fields": fields},
    )


def validate_plan(raw: dict[str, Any], target: RemoteTarget) -> list[dict[str, Any]]:
    if raw.get("plan_version") != PLAN_VERSION:
        raise CliError(
            code="INVALID_DECLARATIVE_PLAN",
            message="Plan version is unsupported.",
            exit_code=EXIT_USAGE,
            details={"expected": PLAN_VERSION},
        )
    plan_target = raw.get("target")
    expected = {"profile": target.name, "base_url": target.base_url, "api_prefix": target.api_prefix}
    if plan_target != expected:
        raise CliError(
            code="PLAN_TARGET_MISMATCH",
            message="The saved plan is bound to a different API target.",
            exit_code=EXIT_CONFLICT,
            details={"planned": plan_target, "active": expected},
        )
    operations = raw.get("operations")
    if not isinstance(operations, list) or not all(isinstance(item, dict) for item in operations):
        raise CliError(
            code="INVALID_DECLARATIVE_PLAN",
            message="Plan operations must be an array of objects.",
            exit_code=EXIT_USAGE,
        )
    return operations


def _snapshot_for_plan_validation(client: RemoteClient, operations: list[dict[str, Any]]) -> dict[str, Any]:
    synthetic: dict[str, list[dict[str, Any]]] = {resource: [] for resource in _RESOURCE_ORDER}
    for operation in operations:
        resource = operation.get("resource")
        identity = str(operation.get("identity", ""))
        if resource == "permissions":
            synthetic["permissions"].append({"name": identity, "state": "absent"})
        elif resource == "entities":
            synthetic["entities"].append({"slug": identity, "state": "absent"})
        elif resource == "roles":
            synthetic["roles"].append({"name": identity, "state": "absent"})
        elif resource == "memberships":
            if "@" in identity:
                user, entity = identity.rsplit("@", 1)
                synthetic["memberships"].append({"user": user, "entity": entity, "state": "absent"})
    return _fetch_snapshot(client, synthetic)


def _current_for_operation(snapshot: dict[str, Any], operation: dict[str, Any]) -> Optional[dict[str, Any]]:
    resource = str(operation["resource"])
    identity = str(operation["identity"])
    items = snapshot.get(resource, [])
    return _items_by_identity(resource, (item for item in items if isinstance(item, dict))).get(identity.casefold())


def check_plan_drift(client: RemoteClient, operations: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot = _snapshot_for_plan_validation(client, operations)
    drift: list[dict[str, Any]] = []
    for operation in operations:
        current = _current_for_operation(snapshot, operation)
        expected_hash = operation.get("before_hash")
        actual_hash = object_hash(current) if current is not None else None
        if actual_hash != expected_hash:
            drift.append(
                {
                    "operation_id": operation.get("id"),
                    "resource": operation.get("resource"),
                    "identity": operation.get("identity"),
                    "expected_hash": expected_hash,
                    "actual_hash": actual_hash,
                    "actual_state": "present" if current is not None else "absent",
                }
            )
    if drift:
        raise CliError(
            code="PLAN_DRIFT_DETECTED",
            message="Remote state changed after this plan was created; nothing was applied.",
            exit_code=EXIT_CONFLICT,
            details={"drift": drift},
            hint="Generate and review a new plan.",
        )
    return snapshot


def _resolved_ids(snapshot: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        "permissions": {
            str(item["name"]).casefold(): str(item["id"])
            for item in snapshot["permissions"]
            if item.get("name") and item.get("id")
        },
        "entities": {
            str(item["slug"]).casefold(): str(item["id"])
            for item in snapshot["entities"]
            if item.get("slug") and item.get("id")
        },
        "roles": {
            str(item["name"]).casefold(): str(item["id"])
            for item in snapshot["roles"]
            if item.get("name") and item.get("id")
        },
    }


def _resolve_body_refs(value: Any, ids: dict[str, dict[str, str]]) -> Any:
    if isinstance(value, dict) and set(value) == {"$outlabs_ref"}:
        reference = value["$outlabs_ref"]
        if not isinstance(reference, dict):
            raise CliError(
                code="INVALID_DECLARATIVE_PLAN",
                message="Plan contains an invalid resource reference.",
                exit_code=EXIT_USAGE,
            )
        resource = str(reference.get("resource"))
        identity = str(reference.get("identity"))
        resolved = ids.get(resource, {}).get(identity.casefold())
        if resolved is None:
            raise CliError(
                code="DECLARATIVE_REFERENCE_NOT_FOUND",
                message=f"Cannot resolve planned {resource} reference '{identity}'.",
                exit_code=EXIT_CONFLICT,
            )
        return resolved
    if isinstance(value, dict):
        return {key: _resolve_body_refs(item, ids) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_body_refs(item, ids) for item in value]
    return value


def apply_plan(
    client: RemoteClient,
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    snapshot = check_plan_drift(client, operations)
    ids = _resolved_ids(snapshot)
    completed: list[dict[str, Any]] = []
    for operation in operations:
        try:
            body = _resolve_body_refs(operation.get("body"), ids)
            result, meta = client.request(
                str(operation["method"]),
                str(operation["path"]),
                json_body=body,
            )
            completed_item = {
                "operation_id": operation["id"],
                "resource": operation["resource"],
                "identity": operation["identity"],
                "action": operation["action"],
                "http_status": meta.get("http_status"),
                "request_id": meta.get("request_id"),
            }
            completed.append(completed_item)
            if operation["action"] == "create" and isinstance(result, dict) and result.get("id"):
                ids.setdefault(str(operation["resource"]), {})[str(operation["identity"]).casefold()] = str(
                    result["id"]
                )
        except CliError as exc:
            if not completed:
                raise
            raise CliError(
                code="APPLY_PARTIAL_FAILURE",
                message="The declarative apply stopped after a partial change.",
                exit_code=EXIT_PARTIAL,
                details={
                    "completed": completed,
                    "failed_operation": operation.get("id"),
                    "cause": {"code": exc.code, "message": exc.message, "details": dict(exc.details)},
                },
                hint="Inspect remote state and generate a fresh plan before retrying.",
            ) from exc
        except Exception as exc:
            if not completed:
                raise
            raise CliError(
                code="APPLY_PARTIAL_FAILURE",
                message="The declarative apply stopped after a partial change.",
                exit_code=EXIT_PARTIAL,
                details={
                    "completed": completed,
                    "failed_operation": operation.get("id"),
                    "cause": {"code": "INTERNAL_ERROR", "exception_type": type(exc).__name__},
                },
                hint="Inspect remote state and generate a fresh plan before retrying.",
            ) from exc
    return {"applied": len(completed), "operations": completed}


def write_plan_file(path_value: str, plan: dict[str, Any], *, force: bool = False) -> Path:
    path = Path(path_value).expanduser()
    if path.is_symlink():
        raise CliError(
            code="INSECURE_PLAN_PATH",
            message="Plan output must not be a symbolic link.",
            exit_code=EXIT_USAGE,
            details={"path": str(path)},
        )
    if path.exists() and not force:
        raise CliError(
            code="PLAN_FILE_EXISTS",
            message="Plan output already exists.",
            exit_code=EXIT_USAGE,
            details={"path": str(path)},
            hint="Choose another path or pass --force after reviewing the target.",
        )
    temp_name: Optional[str] = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".plan-", suffix=".json", dir=path.parent)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(plan, handle, indent=2, default=str)
            handle.write("\n")
        os.replace(temp_name, path)
        temp_name = None
        return path
    except OSError as exc:
        raise CliError(
            code="PLAN_WRITE_FAILED",
            message="Cannot write the declarative plan file.",
            exit_code=EXIT_USAGE,
            details={"path": str(path), "exception_type": type(exc).__name__},
        ) from exc
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
