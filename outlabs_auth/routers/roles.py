"""
Roles router factory.

Provides ready-to-use role management routes (DD-041).
"""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.models.sql.enums import RoleScope
from outlabs_auth.models.sql.role import ConditionGroup, RoleCondition
from outlabs_auth.observability import ObservabilityContext, get_observability_with_auth
from outlabs_auth.schemas.abac import (
    AbacConditionCreateRequest,
    AbacConditionResponse,
    AbacConditionUpdateRequest,
    ConditionGroupCreateRequest,
    ConditionGroupResponse,
    ConditionGroupUpdateRequest,
    parse_uuid,
    serialize_condition_value,
)
from outlabs_auth.schemas.common import PaginatedResponse
from outlabs_auth.schemas.role import (
    RoleCreateRequest,
    RoleResponse,
    RoleScopeEnum,
    RoleUpdateRequest,
)


async def _build_role_response(
    session, role, permission_names: List[str]
) -> RoleResponse:
    """Build a RoleResponse from a Role model with permissions."""
    from outlabs_auth.models.sql import Entity
    from outlabs_auth.models.sql.permission import Permission
    from outlabs_auth.models.sql.role import RoleEntityTypePermission
    from sqlalchemy import select

    # Get root entity name (fetch from DB to avoid lazy loading issues)
    root_entity_name = None
    if role.root_entity_id:
        root_entity = await session.get(Entity, role.root_entity_id)
        if root_entity:
            root_entity_name = root_entity.display_name

    # Get scope entity name
    scope_entity_name = None
    if role.scope_entity_id:
        scope_entity = await session.get(Entity, role.scope_entity_id)
        if scope_entity:
            scope_entity_name = scope_entity.display_name

    # Map RoleScope enum to schema enum
    scope_value = RoleScopeEnum.HIERARCHY
    if role.scope == RoleScope.ENTITY_ONLY:
        scope_value = RoleScopeEnum.ENTITY_ONLY

    entity_type_permissions = {}
    entries = await session.execute(
        select(RoleEntityTypePermission.entity_type, Permission.name)
        .join(Permission, Permission.id == RoleEntityTypePermission.permission_id)
        .where(RoleEntityTypePermission.role_id == role.id)
    )
    for entity_type, permission_name in entries.all():
        entity_type_permissions.setdefault(entity_type, []).append(permission_name)

    return RoleResponse(
        id=str(role.id),
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        permissions=permission_names,
        entity_type_permissions=entity_type_permissions or None,
        is_system_role=role.is_system_role,
        is_global=role.is_global,
        root_entity_id=str(role.root_entity_id) if role.root_entity_id else None,
        root_entity_name=root_entity_name,
        scope_entity_id=str(role.scope_entity_id) if role.scope_entity_id else None,
        scope_entity_name=scope_entity_name,
        scope=scope_value,
        is_auto_assigned=role.is_auto_assigned,
        assignable_at_types=[],
    )


def get_roles_router(
    auth: Any, prefix: str = "", tags: Optional[list[str]] = None
) -> APIRouter:
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

    @router.get(
        "/",
        response_model=PaginatedResponse[RoleResponse],
        summary="List roles",
        description="List all roles with pagination (requires role:read permission)",
    )
    async def list_roles(
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(20, ge=1, le=100, description="Results per page"),
        search: Optional[str] = Query(
            None, description="Search by role name, display name, or description"
        ),
        is_global: Optional[bool] = Query(
            None, description="Filter by global/non-global roles"
        ),
        root_entity_id: Optional[UUID] = Query(
            None, description="Filter by root entity that owns the role"
        ),
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.deps.require_permission("role:read"),
            )
        ),
    ):
        """List all roles with pagination and optional filtering."""
        try:
            roles, total = await auth.role_service.list_roles(
                session,
                page=page,
                limit=limit,
                search=search,
                is_global=is_global,
                root_entity_id=root_entity_id,
            )

            # Calculate total pages
            pages = (total + limit - 1) // limit if total > 0 else 0

            items: List[RoleResponse] = []
            for role in roles:
                permission_names = await auth.role_service.get_role_permission_names(
                    session, role.id
                )
                items.append(
                    await _build_role_response(session, role, permission_names)
                )

            return PaginatedResponse(
                items=items, total=total, page=page, limit=limit, pages=pages
            )
        except HTTPException:
            raise
        except Exception as e:
            obs.log_500_error(
                e, page=page, limit=limit, search=search, is_global=is_global
            )
            raise

    @router.get(
        "/entity/{entity_id}",
        response_model=PaginatedResponse[RoleResponse],
        summary="List roles for entity",
        description=(
            "List roles available for a specific entity (requires role:read_tree permission)"
        ),
    )
    async def list_roles_for_entity(
        entity_id: UUID,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        limit: int = Query(20, ge=1, le=100, description="Results per page"),
        session: AsyncSession = Depends(auth.uow),
        obs: ObservabilityContext = Depends(
            get_observability_with_auth(
                auth.observability,
                auth.require_tree_permission("role:read", "entity_id", source="path"),
            )
        ),
    ):
        """List roles available for a specific entity."""
        try:
            roles, total = await auth.role_service.get_roles_for_entity(
                session, entity_id=entity_id, page=page, limit=limit
            )

            pages = (total + limit - 1) // limit if total > 0 else 0

            items: List[RoleResponse] = []
            for role in roles:
                permission_names = await auth.role_service.get_role_permission_names(
                    session, role.id
                )
                items.append(
                    await _build_role_response(session, role, permission_names)
                )

            return PaginatedResponse(
                items=items, total=total, page=page, limit=limit, pages=pages
            )
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
            root_entity_id=UUID(data.root_entity_id) if data.root_entity_id else None,
            scope_entity_id=UUID(data.scope_entity_id)
            if data.scope_entity_id
            else None,
            scope=scope,
            is_auto_assigned=data.is_auto_assigned,
            entity_type_permissions=data.entity_type_permissions,
        )

        permission_names = await auth.role_service.get_role_permission_names(
            session, role.id
        )

        return await _build_role_response(session, role, permission_names)

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
        role = await auth.role_service.get_role_by_id(
            session, role_id, load_permissions=True
        )
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )

        return await _build_role_response(session, role, role.get_permission_names())

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
        update_dict = data.model_dump(exclude_unset=True)

        # Map schema scope enum to model enum if provided
        scope = None
        if "scope" in update_dict and update_dict["scope"] is not None:
            scope = (
                RoleScope.ENTITY_ONLY
                if update_dict["scope"] == RoleScopeEnum.ENTITY_ONLY
                else RoleScope.HIERARCHY
            )

        role = await auth.role_service.update_role(
            session,
            role_id=role_id,
            display_name=update_dict.get("display_name"),
            description=update_dict.get("description"),
            is_global=update_dict.get("is_global"),
            scope=scope,
            is_auto_assigned=update_dict.get("is_auto_assigned"),
        )

        if "permissions" in update_dict and update_dict["permissions"] is not None:
            role = await auth.role_service.set_permissions_by_name(
                session,
                role_id=role_id,
                permission_names=update_dict["permissions"],
            )

        if "entity_type_permissions" in update_dict:
            role = await auth.role_service.set_entity_type_permissions(
                session,
                role_id=role_id,
                entity_type_permissions=update_dict["entity_type_permissions"],
            )

        permission_names = await auth.role_service.get_role_permission_names(
            session, role.id
        )

        return await _build_role_response(session, role, permission_names)

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
        deleted = await auth.role_service.delete_role(session, role_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
            )
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
        role = await auth.role_service.add_permissions_by_name(
            session,
            role_id=role_id,
            permission_names=permissions,
        )
        return await _build_role_response(session, role, role.get_permission_names())

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
        role = await auth.role_service.remove_permissions_by_name(
            session,
            role_id=role_id,
            permission_names=permissions,
        )
        return await _build_role_response(session, role, role.get_permission_names())

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
        groups = await session.execute(
            select(ConditionGroup).where(ConditionGroup.role_id == role_id)
        )
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
        role = await auth.role_service.get_role_by_id(session, role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")

        group = ConditionGroup(
            role_id=role_id, operator=data.operator, description=data.description
        )
        session.add(group)
        await session.flush()
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
        group = await session.get(ConditionGroup, group_id)
        if not group or group.role_id != role_id:
            raise HTTPException(status_code=404, detail="Condition group not found")

        fields_set = data.model_fields_set

        if "operator" in fields_set and data.operator is not None:
            group.operator = data.operator
        if "description" in fields_set:
            group.description = data.description

        await session.flush()
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
        group = await session.get(ConditionGroup, group_id)
        if not group or group.role_id != role_id:
            raise HTTPException(status_code=404, detail="Condition group not found")
        await session.delete(group)
        await session.flush()
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
        result = await session.execute(
            select(RoleCondition).where(RoleCondition.role_id == role_id)
        )
        conditions = result.scalars().all()
        return [
            AbacConditionResponse(
                id=str(c.id),
                attribute=c.attribute,
                operator=c.operator,
                value=c.value,
                value_type=c.value_type,
                description=c.description,
                condition_group_id=str(c.condition_group_id)
                if c.condition_group_id
                else None,
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
        role = await auth.role_service.get_role_by_id(session, role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")

        group_id = parse_uuid(data.condition_group_id)
        if group_id is not None:
            group = await session.get(ConditionGroup, group_id)
            if not group or group.role_id != role_id:
                raise HTTPException(
                    status_code=400, detail="Invalid condition_group_id"
                )

        cond = RoleCondition(
            role_id=role_id,
            condition_group_id=group_id,
            attribute=data.attribute,
            operator=data.operator,
            value=serialize_condition_value(data.value, data.value_type),
            value_type=data.value_type,
            description=data.description,
        )
        session.add(cond)
        await session.flush()
        return AbacConditionResponse(
            id=str(cond.id),
            attribute=cond.attribute,
            operator=cond.operator,
            value=cond.value,
            value_type=cond.value_type,
            description=cond.description,
            condition_group_id=str(cond.condition_group_id)
            if cond.condition_group_id
            else None,
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
        cond = await session.get(RoleCondition, condition_id)
        if not cond or cond.role_id != role_id:
            raise HTTPException(status_code=404, detail="Condition not found")

        fields_set = data.model_fields_set

        if "condition_group_id" in fields_set:
            group_id = parse_uuid(data.condition_group_id)
            if group_id is not None:
                group = await session.get(ConditionGroup, group_id)
                if not group or group.role_id != role_id:
                    raise HTTPException(
                        status_code=400, detail="Invalid condition_group_id"
                    )
            cond.condition_group_id = group_id

        if "attribute" in fields_set and data.attribute is not None:
            cond.attribute = data.attribute
        if "operator" in fields_set and data.operator is not None:
            cond.operator = data.operator
        if "value_type" in fields_set and data.value_type is not None:
            cond.value_type = data.value_type
        if "value" in fields_set or "value_type" in fields_set:
            cond.value = serialize_condition_value(
                data.value, data.value_type or cond.value_type
            )
        if "description" in fields_set:
            cond.description = data.description

        await session.flush()
        return AbacConditionResponse(
            id=str(cond.id),
            attribute=cond.attribute,
            operator=cond.operator,
            value=cond.value,
            value_type=cond.value_type,
            description=cond.description,
            condition_group_id=str(cond.condition_group_id)
            if cond.condition_group_id
            else None,
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
        cond = await session.get(RoleCondition, condition_id)
        if not cond or cond.role_id != role_id:
            raise HTTPException(status_code=404, detail="Condition not found")
        await session.delete(cond)
        await session.flush()
        return None

    return router
