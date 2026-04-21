"""
Roles router factory.

Provides ready-to-use role management routes (DD-041).
"""

from enum import Enum
from typing import Any, List, Optional, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.exceptions import InvalidInputError, RoleNotFoundError
from outlabs_auth.models.sql.enums import RoleScope
from outlabs_auth.models.sql.role import ConditionGroup, Role, RoleCondition
from outlabs_auth.observability import (
    ObservabilityContext,
    get_observability_dependency,
)
from outlabs_auth.response_builders import build_role_response, build_role_responses
from outlabs_auth.schemas.abac import (
    AbacConditionCreateRequest,
    AbacConditionResponse,
    AbacConditionUpdateRequest,
    ConditionGroupCreateRequest,
    ConditionGroupResponse,
    ConditionGroupUpdateRequest,
    parse_uuid,
)
from outlabs_auth.schemas.common import PaginatedResponse
from outlabs_auth.schemas.role import (
    RoleCreateRequest,
    RoleResponse,
    RoleScopeEnum,
    RoleUpdateRequest,
)


def get_roles_router(auth: Any, prefix: str = "", tags: Optional[list[str | Enum]] = None) -> APIRouter:
    """
    Generate role management router.

    Args:
        auth: OutlabsAuth instance (SimpleRBAC or EnterpriseRBAC)
        prefix: Router prefix (default: "")
        tags: OpenAPI tags (default: ["roles"])

    Returns:
        APIRouter with role management endpoints

    Routes:
        GET / - List all roles
        POST / - Create new role
        GET /{role_id} - Get role details
        PATCH /{role_id} - Update role
        DELETE /{role_id} - Delete role
        POST /{role_id}/permissions - Add permissions to role
        DELETE /{role_id}/permissions - Remove permissions from role

    Example:
        ```python
        from outlabs_auth import SimpleRBAC
        from outlabs_auth.routers import get_roles_router

        auth = SimpleRBAC(database=db)
        app.include_router(get_roles_router(auth, prefix="/roles"))
        ```
    """
    router = APIRouter(prefix=prefix, tags=tags or ["roles"])
    get_obs = get_observability_dependency(auth.observability)

    def _role_is_system_wide(role: Role) -> bool:
        return role.is_global and role.root_entity_id is None and role.scope_entity_id is None

    async def _resolve_actor_scope(
        session: AsyncSession,
        auth_result: dict[str, Any],
    ) -> dict[str, Any]:
        scope = cast(
            dict[str, Any],
            await auth.access_scope_service.resolve_for_auth_result(
                session,
                auth_result,
                include_member_user_ids=False,
            ),
        )
        if not auth.config.enable_entity_hierarchy:
            scope["is_global"] = True
        return scope

    async def _get_role_or_404(
        session: AsyncSession,
        role_id: UUID,
        *,
        load_permissions: bool = False,
    ) -> Role:
        role = await auth.role_service.get_role_by_id(
            session,
            role_id,
            load_permissions=load_permissions,
        )
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )
        return cast(Role, role)

    def _role_is_visible_in_scope(role: Role, scope: dict[str, Any]) -> bool:
        if scope.get("is_global"):
            return True

        if _role_is_system_wide(role):
            return False

        entity_ids = set(scope.get("entity_ids") or [])
        root_entity_ids = set(scope.get("root_entity_ids") or [])

        if role.scope_entity_id is not None:
            return str(role.scope_entity_id) in entity_ids

        if role.root_entity_id is not None:
            return str(role.root_entity_id) in root_entity_ids

        return False

    async def _require_role_visibility(
        session: AsyncSession,
        auth_result: dict[str, Any],
        role: Role,
    ) -> dict[str, Any]:
        scope = await _resolve_actor_scope(session, auth_result)
        if _role_is_visible_in_scope(role, scope):
            return scope

        detail = "Role is outside your accessible scope"
        if _role_is_system_wide(role):
            detail = "Only superusers can access system-wide roles"

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )

    async def _require_role_create_scope(
        session: AsyncSession,
        auth_result: dict[str, Any],
        data: RoleCreateRequest,
    ) -> dict[str, Any]:
        scope = await _resolve_actor_scope(session, auth_result)
        if scope.get("is_global"):
            return scope

        if data.is_global and not data.root_entity_id and not data.scope_entity_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superusers can create system-wide roles",
            )

        if data.scope_entity_id:
            if data.scope_entity_id in set(scope.get("entity_ids") or []):
                return scope
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role scope entity is outside your accessible entity scope",
            )

        if data.root_entity_id:
            if data.root_entity_id in set(scope.get("root_entity_ids") or []):
                return scope
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role root scope is outside your accessible organization scope",
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scoped admins can only create roles within their allowed root or entity scope",
        )

    def _parse_scope_uuid_list(scope: dict[str, Any], key: str) -> list[UUID]:
        return [UUID(str(value)) for value in (scope.get(key) or [])]

    @router.get(
        "/",
        response_model=PaginatedResponse[RoleResponse],
        summary="List roles",
        description="List all roles with pagination (requires role:read permission)",
    )
    async def list_roles(
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(20, ge=1, le=100, description="Results per page"),
        search: Optional[str] = Query(None, description="Search by role name, display name, or description"),
        is_global: Optional[bool] = Query(None, description="Filter by global/non-global roles"),
        root_entity_id: Optional[UUID] = Query(None, description="Filter by root entity that owns the role"),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:read")),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        """List all roles with pagination and optional filtering."""
        try:
            scope = await _resolve_actor_scope(session, auth_result)
            manageable_root_entity_ids: Optional[list[UUID]] = None
            manageable_entity_ids: Optional[list[UUID]] = None
            include_system_global = True

            if not scope.get("is_global"):
                manageable_root_entity_ids = _parse_scope_uuid_list(
                    scope,
                    "root_entity_ids",
                )
                manageable_entity_ids = _parse_scope_uuid_list(scope, "entity_ids")
                include_system_global = False

            roles, total = await auth.role_service.list_roles(
                session,
                page=page,
                limit=limit,
                search=search,
                is_global=is_global,
                root_entity_id=root_entity_id,
                manageable_root_entity_ids=manageable_root_entity_ids,
                manageable_entity_ids=manageable_entity_ids,
                include_system_global=include_system_global,
            )

            # Calculate total pages
            pages = (total + limit - 1) // limit if total > 0 else 0

            items = await build_role_responses(session, roles)

            return PaginatedResponse(items=items, total=total, page=page, limit=limit, pages=pages)
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, page=page, limit=limit, search=search, is_global=is_global)
            raise

    @router.get(
        "/entity/{entity_id}",
        response_model=PaginatedResponse[RoleResponse],
        summary="List roles for entity",
        description=("List roles available for a specific entity (requires role:read_tree permission)"),
    )
    async def list_roles_for_entity(
        entity_id: UUID,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(20, ge=1, le=100, description="Results per page"),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("role:read", "entity_id", source="path")),
        obs: ObservabilityContext = Depends(get_obs),
    ):
        """List roles available for a specific entity."""
        try:
            roles, total = await auth.role_service.get_roles_for_entity(
                session, entity_id=entity_id, page=page, limit=limit
            )

            pages = (total + limit - 1) // limit if total > 0 else 0

            items = await build_role_responses(session, roles)

            return PaginatedResponse(items=items, total=total, page=page, limit=limit, pages=pages)
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(e, entity_id=str(entity_id), page=page, limit=limit)
            raise

    @router.post(
        "/",
        response_model=RoleResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create role",
        description="Create new role (requires role:create permission)",
    )
    async def create_role(
        data: RoleCreateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:create")),
    ):
        """Create a new role."""
        await _require_role_create_scope(session, auth_result, data)

        # Map schema scope enum to model enum
        scope = RoleScope.HIERARCHY
        if data.scope == RoleScopeEnum.ENTITY_ONLY:
            scope = RoleScope.ENTITY_ONLY

        role = await auth.role_service.create_role(
            session,
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            permission_names=data.permissions,
            is_global=data.is_global,
            status=data.status,
            root_entity_id=UUID(data.root_entity_id) if data.root_entity_id else None,
            scope_entity_id=UUID(data.scope_entity_id) if data.scope_entity_id else None,
            scope=scope,
            is_auto_assigned=data.is_auto_assigned,
            assignable_at_types=data.assignable_at_types,
            created_by_id=UUID(auth_result["user_id"]),
        )

        if role.is_auto_assigned:
            await auth.membership_service.apply_auto_assigned_role(session, role.id)

        permission_names = await auth.role_service.get_role_permission_names(session, role.id)

        return await build_role_response(session, role, permission_names)

    @router.get(
        "/{role_id}",
        response_model=RoleResponse,
        summary="Get role",
        description="Get role details by ID",
    )
    async def get_role(
        role_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:read")),
    ):
        """Get role details by ID."""
        role = await _get_role_or_404(session, role_id, load_permissions=True)
        await _require_role_visibility(session, auth_result, role)
        permission_names = await auth.role_service.get_role_permission_names(session, role.id)
        return await build_role_response(session, role, permission_names)

    @router.patch(
        "/{role_id}",
        response_model=RoleResponse,
        summary="Update role",
        description="Update role details (requires role:update permission)",
    )
    async def update_role(
        role_id: UUID,
        data: RoleUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        """Update role details."""
        current_role = await _get_role_or_404(session, role_id)
        await _require_role_visibility(session, auth_result, current_role)

        update_dict = data.model_dump(exclude_unset=True)
        was_auto_assigned = current_role.is_auto_assigned

        # Map schema scope enum to model enum if provided
        scope = None
        if "scope" in update_dict and update_dict["scope"] is not None:
            scope = RoleScope.ENTITY_ONLY if update_dict["scope"] == RoleScopeEnum.ENTITY_ONLY else RoleScope.HIERARCHY

        role = await auth.role_service.update_role(
            session,
            role_id=role_id,
            display_name=update_dict.get("display_name"),
            description=update_dict.get("description"),
            is_global=update_dict.get("is_global"),
            status=update_dict.get("status"),
            scope=scope,
            is_auto_assigned=update_dict.get("is_auto_assigned"),
            assignable_at_types=update_dict.get("assignable_at_types"),
            permission_names=update_dict.get("permissions"),
            update_permissions="permissions" in update_dict,
            changed_by_id=UUID(auth_result["user_id"]),
        )

        if not was_auto_assigned and role.is_auto_assigned:
            await auth.membership_service.apply_auto_assigned_role(session, role.id)

        permission_names = await auth.role_service.get_role_permission_names(session, role.id)

        return await build_role_response(session, role, permission_names)

    @router.delete(
        "/{role_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete role",
        description="Delete role (requires role:delete permission)",
    )
    async def delete_role(
        role_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:delete")),
    ):
        """Delete a role."""
        role = await _get_role_or_404(session, role_id)
        await _require_role_visibility(session, auth_result, role)

        deleted = await auth.role_service.delete_role(
            session,
            role_id,
            deleted_by_id=UUID(auth_result["user_id"]),
        )
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        return None

    @router.post(
        "/{role_id}/permissions",
        response_model=RoleResponse,
        summary="Add permissions",
        description="Add permissions to role (requires role:update permission)",
    )
    async def add_permissions(
        role_id: UUID,
        permissions: List[str],
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        """Add permissions to a role."""
        current_role = await _get_role_or_404(session, role_id)
        await _require_role_visibility(session, auth_result, current_role)

        role = await auth.role_service.add_permissions_by_name(
            session,
            role_id=role_id,
            permission_names=permissions,
            changed_by_id=UUID(auth_result["user_id"]),
        )
        return await build_role_response(session, role, role.get_permission_names())

    @router.delete(
        "/{role_id}/permissions",
        response_model=RoleResponse,
        summary="Remove permissions",
        description="Remove permissions from role (requires role:update permission)",
    )
    async def remove_permissions(
        role_id: UUID,
        permissions: List[str],
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        """Remove permissions from a role."""
        current_role = await _get_role_or_404(session, role_id)
        await _require_role_visibility(session, auth_result, current_role)

        role = await auth.role_service.remove_permissions_by_name(
            session,
            role_id=role_id,
            permission_names=permissions,
            changed_by_id=UUID(auth_result["user_id"]),
        )
        return await build_role_response(session, role, role.get_permission_names())

    # ---------------------------------------------------------------------
    # ABAC: Role condition groups + conditions
    # ---------------------------------------------------------------------

    @router.get(
        "/{role_id}/condition-groups",
        response_model=List[ConditionGroupResponse],
        summary="List role condition groups",
        description="List ABAC condition groups for a role (requires role:read permission)",
    )
    async def list_role_condition_groups(
        role_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:read")),
    ):
        role = await _get_role_or_404(session, role_id)
        await _require_role_visibility(session, auth_result, role)

        groups = await session.execute(select(ConditionGroup).where(cast(Any, ConditionGroup.role_id) == role_id))
        return [
            ConditionGroupResponse(
                id=str(g.id),
                operator=g.operator,
                description=g.description,
                role_id=str(g.role_id) if g.role_id else None,
                permission_id=str(g.permission_id) if g.permission_id else None,
            )
            for g in groups.scalars().all()
        ]

    @router.post(
        "/{role_id}/condition-groups",
        response_model=ConditionGroupResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create role condition group",
        description="Create an ABAC condition group for a role (requires role:update permission)",
    )
    async def create_role_condition_group(
        role_id: UUID,
        data: ConditionGroupCreateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        role = await _get_role_or_404(session, role_id)
        await _require_role_visibility(session, auth_result, role)
        try:
            group = await auth.role_service.create_role_condition_group(
                session,
                role_id,
                operator=data.operator,
                description=data.description,
                changed_by_id=UUID(auth_result["user_id"]),
            )
        except RoleNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc.message)) from exc
        except InvalidInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc.message)) from exc
        return ConditionGroupResponse(
            id=str(group.id),
            operator=group.operator,
            description=group.description,
            role_id=str(role_id),
            permission_id=None,
        )

    @router.patch(
        "/{role_id}/condition-groups/{group_id}",
        response_model=ConditionGroupResponse,
        summary="Update role condition group",
        description="Update an ABAC condition group (requires role:update permission)",
    )
    async def update_role_condition_group(
        role_id: UUID,
        group_id: UUID,
        data: ConditionGroupUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        role = await _get_role_or_404(session, role_id)
        await _require_role_visibility(session, auth_result, role)
        try:
            group = await auth.role_service.update_role_condition_group(
                session,
                role_id,
                group_id,
                fields_set=set(data.model_fields_set),
                operator=data.operator,
                description=data.description,
                changed_by_id=UUID(auth_result["user_id"]),
            )
        except RoleNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc.message)) from exc
        except InvalidInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc.message)) from exc

        if group is None:
            raise HTTPException(status_code=404, detail="Condition group not found")
        return ConditionGroupResponse(
            id=str(group.id),
            operator=group.operator,
            description=group.description,
            role_id=str(group.role_id) if group.role_id else None,
            permission_id=str(group.permission_id) if group.permission_id else None,
        )

    @router.delete(
        "/{role_id}/condition-groups/{group_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete role condition group",
        description="Delete an ABAC condition group (requires role:update permission)",
    )
    async def delete_role_condition_group(
        role_id: UUID,
        group_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        role = await _get_role_or_404(session, role_id)
        await _require_role_visibility(session, auth_result, role)
        try:
            deleted = await auth.role_service.delete_role_condition_group(
                session,
                role_id,
                group_id,
                changed_by_id=UUID(auth_result["user_id"]),
            )
        except RoleNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc.message)) from exc
        except InvalidInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc.message)) from exc

        if not deleted:
            raise HTTPException(status_code=404, detail="Condition group not found")
        return None

    @router.get(
        "/{role_id}/conditions",
        response_model=List[AbacConditionResponse],
        summary="List role conditions",
        description="List ABAC conditions for a role (requires role:read permission)",
    )
    async def list_role_conditions(
        role_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:read")),
    ):
        role = await _get_role_or_404(session, role_id)
        await _require_role_visibility(session, auth_result, role)

        result = await session.execute(select(RoleCondition).where(cast(Any, RoleCondition.role_id) == role_id))
        conditions = result.scalars().all()
        return [
            AbacConditionResponse(
                id=str(c.id),
                attribute=c.attribute,
                operator=c.operator,
                value=c.value,
                value_type=c.value_type,
                description=c.description,
                condition_group_id=str(c.condition_group_id) if c.condition_group_id else None,
            )
            for c in conditions
        ]

    @router.post(
        "/{role_id}/conditions",
        response_model=AbacConditionResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create role condition",
        description="Create an ABAC condition for a role (requires role:update permission)",
    )
    async def create_role_condition(
        role_id: UUID,
        data: AbacConditionCreateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        role = await _get_role_or_404(session, role_id)
        await _require_role_visibility(session, auth_result, role)
        try:
            cond = await auth.role_service.create_role_condition(
                session,
                role_id,
                condition_group_id=parse_uuid(data.condition_group_id),
                attribute=data.attribute,
                operator=data.operator,
                value=data.value,
                value_type=data.value_type,
                description=data.description,
                changed_by_id=UUID(auth_result["user_id"]),
            )
        except RoleNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc.message)) from exc
        except InvalidInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc.message)) from exc
        return AbacConditionResponse(
            id=str(cond.id),
            attribute=cond.attribute,
            operator=cond.operator,
            value=cond.value,
            value_type=cond.value_type,
            description=cond.description,
            condition_group_id=str(cond.condition_group_id) if cond.condition_group_id else None,
        )

    @router.patch(
        "/{role_id}/conditions/{condition_id}",
        response_model=AbacConditionResponse,
        summary="Update role condition",
        description="Update an ABAC condition for a role (requires role:update permission)",
    )
    async def update_role_condition(
        role_id: UUID,
        condition_id: UUID,
        data: AbacConditionUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        role = await _get_role_or_404(session, role_id)
        await _require_role_visibility(session, auth_result, role)
        try:
            cond = await auth.role_service.update_role_condition(
                session,
                role_id,
                condition_id,
                fields_set=set(data.model_fields_set),
                condition_group_id=(
                    parse_uuid(data.condition_group_id) if "condition_group_id" in data.model_fields_set else None
                ),
                attribute=data.attribute,
                operator=data.operator,
                value=data.value,
                value_type=data.value_type,
                description=data.description,
                changed_by_id=UUID(auth_result["user_id"]),
            )
        except RoleNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc.message)) from exc
        except InvalidInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc.message)) from exc

        if cond is None:
            raise HTTPException(status_code=404, detail="Condition not found")
        return AbacConditionResponse(
            id=str(cond.id),
            attribute=cond.attribute,
            operator=cond.operator,
            value=cond.value,
            value_type=cond.value_type,
            description=cond.description,
            condition_group_id=str(cond.condition_group_id) if cond.condition_group_id else None,
        )

    @router.delete(
        "/{role_id}/conditions/{condition_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete role condition",
        description="Delete an ABAC condition for a role (requires role:update permission)",
    )
    async def delete_role_condition(
        role_id: UUID,
        condition_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_permission("role:update")),
    ):
        role = await _get_role_or_404(session, role_id)
        await _require_role_visibility(session, auth_result, role)
        try:
            deleted = await auth.role_service.delete_role_condition(
                session,
                role_id,
                condition_id,
                changed_by_id=UUID(auth_result["user_id"]),
            )
        except RoleNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc.message)) from exc
        except InvalidInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc.message)) from exc

        if not deleted:
            raise HTTPException(status_code=404, detail="Condition not found")
        return None

    return router
