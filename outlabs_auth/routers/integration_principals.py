"""Enterprise integration-principal router factory."""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.exceptions import InvalidInputError
from outlabs_auth.models.sql.enums import (
    APIKeyKind,
    APIKeyStatus,
    IntegrationPrincipalScopeKind,
    IntegrationPrincipalStatus,
)
from outlabs_auth.schemas.api_key import (
    ApiKeyCreateResponse,
    ApiKeyResponse,
    SystemIntegrationApiKeyCreateRequest,
    SystemIntegrationApiKeyUpdateRequest,
)
from outlabs_auth.schemas.common import PaginatedResponse
from outlabs_auth.schemas.integration_principal import (
    IntegrationPrincipalCreateRequest,
    IntegrationPrincipalResponse,
    IntegrationPrincipalUpdateRequest,
)


def get_integration_principals_router(auth: Any, prefix: str = "", tags: Optional[list[str]] = None) -> APIRouter:
    """Generate EnterpriseRBAC routes for integration principals and owned system API keys."""
    if not getattr(auth.config, "enable_entity_hierarchy", False):
        raise ValueError("Integration principals require EnterpriseRBAC")

    router = APIRouter(prefix=prefix, tags=tags or ["integration-principals"])

    def _actor_user_id(auth_result: dict) -> UUID:
        raw_user_id = auth_result.get("user_id")
        if not raw_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required",
            )
        return UUID(str(raw_user_id))

    async def _to_principal_response(principal) -> IntegrationPrincipalResponse:
        return IntegrationPrincipalResponse(
            id=str(principal.id),
            name=principal.name,
            description=principal.description,
            status=principal.status_enum,
            scope_kind=principal.scope_kind_enum,
            anchor_entity_id=str(principal.anchor_entity_id) if principal.anchor_entity_id else None,
            inherit_from_tree=principal.inherit_from_tree,
            allowed_scopes=list(principal.allowed_scopes or []),
            created_by_user_id=str(principal.created_by_user_id) if principal.created_by_user_id else None,
            created_at=principal.created_at,
            updated_at=principal.updated_at,
        )

    async def _to_api_key_response(session: AsyncSession, api_key) -> ApiKeyResponse:
        scopes = await auth.api_key_service.get_api_key_scopes(session, api_key.id)
        ip_whitelist = await auth.api_key_service.get_api_key_ip_whitelist(session, api_key.id)
        is_currently_effective = None
        ineffective_reasons = None
        if getattr(auth, "api_key_policy_service", None) is not None:
            effectiveness = await auth.api_key_policy_service.evaluate_effectiveness(
                session,
                api_key=api_key,
                scopes=scopes,
            )
            is_currently_effective = effectiveness.is_currently_effective
            ineffective_reasons = effectiveness.ineffective_reasons
        return ApiKeyResponse(
            id=str(api_key.id),
            prefix=api_key.prefix,
            name=api_key.name,
            key_kind=api_key.key_kind,
            scopes=scopes,
            ip_whitelist=ip_whitelist or None,
            rate_limit_per_minute=api_key.rate_limit_per_minute,
            status=api_key.status,
            usage_count=api_key.usage_count,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            description=api_key.description,
            entity_ids=[str(api_key.entity_id)] if api_key.entity_id else None,
            inherit_from_tree=api_key.inherit_from_tree,
            owner_id=str(api_key.resolved_owner_id) if api_key.resolved_owner_id else None,
            owner_type=api_key.owner_type,
            is_currently_effective=is_currently_effective,
            ineffective_reasons=ineffective_reasons,
        )

    async def _get_entity_principal(session: AsyncSession, entity_id: UUID, principal_id: UUID):
        principal = await auth.integration_principal_service.get_principal(session, principal_id)
        if (
            principal is None
            or principal.scope_kind_enum != IntegrationPrincipalScopeKind.ENTITY
            or principal.anchor_entity_id != entity_id
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration principal not found")
        return principal

    async def _get_system_principal(session: AsyncSession, principal_id: UUID):
        principal = await auth.integration_principal_service.get_principal(session, principal_id)
        if principal is None or principal.scope_kind_enum != IntegrationPrincipalScopeKind.PLATFORM_GLOBAL:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration principal not found")
        return principal

    async def _get_principal_api_key(session: AsyncSession, principal_id: UUID, key_id: UUID):
        api_key = await auth.api_key_service.get_api_key(session, key_id)
        if api_key is None or api_key.integration_principal_id != principal_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        return api_key

    @router.get(
        "/entities/{entity_id}/integration-principals",
        response_model=PaginatedResponse[IntegrationPrincipalResponse],
        summary="List entity integration principals",
    )
    async def list_entity_integration_principals(
        entity_id: UUID,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
        status_filter: Optional[IntegrationPrincipalStatus] = Query(default=None, alias="status"),
        search: Optional[str] = Query(default=None, min_length=1),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:read", "entity_id", source="path")),
    ):
        del auth_result
        principals, total = await auth.integration_principal_service.list_principals(
            session,
            scope_kind=IntegrationPrincipalScopeKind.ENTITY,
            anchor_entity_id=entity_id,
            status=status_filter,
            search=search,
            page=page,
            limit=limit,
        )
        pages = (total + limit - 1) // limit if total > 0 else 0
        return PaginatedResponse(
            items=[await _to_principal_response(principal) for principal in principals],
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )

    @router.post(
        "/entities/{entity_id}/integration-principals",
        response_model=IntegrationPrincipalResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create entity integration principal",
    )
    async def create_entity_integration_principal(
        entity_id: UUID,
        data: IntegrationPrincipalCreateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:create", "entity_id", source="path")),
    ):
        actor_user_id = _actor_user_id(auth_result)
        try:
            principal = await auth.integration_principal_service.create_principal(
                session,
                name=data.name,
                description=data.description,
                scope_kind=IntegrationPrincipalScopeKind.ENTITY,
                anchor_entity_id=entity_id,
                inherit_from_tree=data.inherit_from_tree,
                allowed_scopes=data.allowed_scopes,
                created_by_user_id=actor_user_id,
            )
        except InvalidInputError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
        return await _to_principal_response(principal)

    @router.get(
        "/entities/{entity_id}/integration-principals/{principal_id}",
        response_model=IntegrationPrincipalResponse,
        summary="Get entity integration principal",
    )
    async def get_entity_integration_principal(
        entity_id: UUID,
        principal_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:read", "entity_id", source="path")),
    ):
        del auth_result
        principal = await _get_entity_principal(session, entity_id, principal_id)
        return await _to_principal_response(principal)

    @router.patch(
        "/entities/{entity_id}/integration-principals/{principal_id}",
        response_model=IntegrationPrincipalResponse,
        summary="Update entity integration principal",
    )
    async def update_entity_integration_principal(
        entity_id: UUID,
        principal_id: UUID,
        data: IntegrationPrincipalUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:update", "entity_id", source="path")),
    ):
        await _get_entity_principal(session, entity_id, principal_id)
        try:
            principal = await auth.integration_principal_service.update_principal(
                session,
                principal_id,
                actor_user_id=_actor_user_id(auth_result),
                **data.model_dump(exclude_unset=True),
            )
        except InvalidInputError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
        if principal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration principal not found")
        return await _to_principal_response(principal)

    @router.delete(
        "/entities/{entity_id}/integration-principals/{principal_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Archive entity integration principal",
    )
    async def delete_entity_integration_principal(
        entity_id: UUID,
        principal_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:delete", "entity_id", source="path")),
    ):
        await _get_entity_principal(session, entity_id, principal_id)
        archived = await auth.integration_principal_service.archive_principal(
            session,
            principal_id,
            actor_user_id=_actor_user_id(auth_result),
            reason="Archived via entity integration principal route",
        )
        if not archived:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration principal not found")
        return None

    @router.get(
        "/entities/{entity_id}/integration-principals/{principal_id}/api-keys",
        response_model=PaginatedResponse[ApiKeyResponse],
        summary="List entity integration principal API keys",
    )
    async def list_entity_integration_principal_api_keys(
        entity_id: UUID,
        principal_id: UUID,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
        status_filter: Optional[APIKeyStatus] = Query(default=None, alias="status"),
        search: Optional[str] = Query(default=None, min_length=1),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:read", "entity_id", source="path")),
    ):
        del auth_result
        await _get_entity_principal(session, entity_id, principal_id)
        api_keys, total = await auth.api_key_service.list_integration_principal_api_keys_paginated(
            session,
            integration_principal_id=principal_id,
            status=status_filter,
            search=search,
            page=page,
            limit=limit,
        )
        pages = (total + limit - 1) // limit if total > 0 else 0
        return PaginatedResponse(
            items=[await _to_api_key_response(session, api_key) for api_key in api_keys],
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )

    @router.post(
        "/entities/{entity_id}/integration-principals/{principal_id}/api-keys",
        response_model=ApiKeyCreateResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create entity integration principal API key",
    )
    async def create_entity_integration_principal_api_key(
        entity_id: UUID,
        principal_id: UUID,
        data: SystemIntegrationApiKeyCreateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:create", "entity_id", source="path")),
    ):
        await _get_entity_principal(session, entity_id, principal_id)
        try:
            full_key, api_key_model = await auth.api_key_service.create_api_key(
                session,
                integration_principal_id=principal_id,
                name=data.name,
                scopes=data.scopes,
                prefix_type=data.prefix_type,
                ip_whitelist=data.ip_whitelist,
                rate_limit_per_minute=data.rate_limit_per_minute,
                expires_in_days=data.expires_in_days,
                description=data.description,
                key_kind=APIKeyKind.SYSTEM_INTEGRATION,
                actor_user_id=_actor_user_id(auth_result),
                event_source="integration_principals_router.create_entity_integration_principal_api_key",
            )
        except InvalidInputError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

        api_key_response = await _to_api_key_response(session, api_key_model)
        return ApiKeyCreateResponse(**api_key_response.model_dump(), api_key=full_key)

    @router.get(
        "/entities/{entity_id}/integration-principals/{principal_id}/api-keys/{key_id}",
        response_model=ApiKeyResponse,
        summary="Get entity integration principal API key",
    )
    async def get_entity_integration_principal_api_key(
        entity_id: UUID,
        principal_id: UUID,
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:read", "entity_id", source="path")),
    ):
        del auth_result
        await _get_entity_principal(session, entity_id, principal_id)
        api_key = await _get_principal_api_key(session, principal_id, key_id)
        return await _to_api_key_response(session, api_key)

    @router.patch(
        "/entities/{entity_id}/integration-principals/{principal_id}/api-keys/{key_id}",
        response_model=ApiKeyResponse,
        summary="Update entity integration principal API key",
    )
    async def update_entity_integration_principal_api_key(
        entity_id: UUID,
        principal_id: UUID,
        key_id: UUID,
        data: SystemIntegrationApiKeyUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:update", "entity_id", source="path")),
    ):
        await _get_entity_principal(session, entity_id, principal_id)
        await _get_principal_api_key(session, principal_id, key_id)
        try:
            api_key = await auth.api_key_service.update_api_key(
                session,
                key_id=key_id,
                actor_user_id=_actor_user_id(auth_result),
                event_source="integration_principals_router.update_entity_integration_principal_api_key",
                **data.model_dump(exclude_unset=True),
            )
        except InvalidInputError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
        if api_key is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        return await _to_api_key_response(session, api_key)

    @router.delete(
        "/entities/{entity_id}/integration-principals/{principal_id}/api-keys/{key_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Revoke entity integration principal API key",
    )
    async def delete_entity_integration_principal_api_key(
        entity_id: UUID,
        principal_id: UUID,
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:delete", "entity_id", source="path")),
    ):
        await _get_entity_principal(session, entity_id, principal_id)
        await _get_principal_api_key(session, principal_id, key_id)
        revoked = await auth.api_key_service.revoke_api_key(
            session,
            key_id,
            actor_user_id=_actor_user_id(auth_result),
            reason="API key revoked via integration principal route",
            event_source="integration_principals_router.delete_entity_integration_principal_api_key",
        )
        if not revoked:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        return None

    @router.post(
        "/entities/{entity_id}/integration-principals/{principal_id}/api-keys/{key_id}/rotate",
        response_model=ApiKeyCreateResponse,
        summary="Rotate entity integration principal API key",
    )
    async def rotate_entity_integration_principal_api_key(
        entity_id: UUID,
        principal_id: UUID,
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.require_tree_permission("api_key:update", "entity_id", source="path")),
    ):
        await _get_entity_principal(session, entity_id, principal_id)
        await _get_principal_api_key(session, principal_id, key_id)
        full_key, api_key = await auth.api_key_service.rotate_api_key(
            session,
            key_id,
            actor_user_id=_actor_user_id(auth_result),
            event_source="integration_principals_router.rotate_entity_integration_principal_api_key",
        )
        api_key_response = await _to_api_key_response(session, api_key)
        return ApiKeyCreateResponse(**api_key_response.model_dump(), api_key=full_key)

    @router.get(
        "/system/integration-principals",
        response_model=PaginatedResponse[IntegrationPrincipalResponse],
        summary="List platform-global integration principals",
    )
    async def list_system_integration_principals(
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
        status_filter: Optional[IntegrationPrincipalStatus] = Query(default=None, alias="status"),
        search: Optional[str] = Query(default=None, min_length=1),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_superuser()),
    ):
        del auth_result
        principals, total = await auth.integration_principal_service.list_principals(
            session,
            scope_kind=IntegrationPrincipalScopeKind.PLATFORM_GLOBAL,
            status=status_filter,
            search=search,
            page=page,
            limit=limit,
        )
        pages = (total + limit - 1) // limit if total > 0 else 0
        return PaginatedResponse(
            items=[await _to_principal_response(principal) for principal in principals],
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )

    @router.post(
        "/system/integration-principals",
        response_model=IntegrationPrincipalResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create platform-global integration principal",
    )
    async def create_system_integration_principal(
        data: IntegrationPrincipalCreateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_superuser()),
    ):
        try:
            principal = await auth.integration_principal_service.create_principal(
                session,
                name=data.name,
                description=data.description,
                scope_kind=IntegrationPrincipalScopeKind.PLATFORM_GLOBAL,
                anchor_entity_id=None,
                inherit_from_tree=False,
                allowed_scopes=data.allowed_scopes,
                created_by_user_id=_actor_user_id(auth_result),
            )
        except InvalidInputError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
        return await _to_principal_response(principal)

    @router.get(
        "/system/integration-principals/{principal_id}",
        response_model=IntegrationPrincipalResponse,
        summary="Get platform-global integration principal",
    )
    async def get_system_integration_principal(
        principal_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_superuser()),
    ):
        del auth_result
        principal = await _get_system_principal(session, principal_id)
        return await _to_principal_response(principal)

    @router.patch(
        "/system/integration-principals/{principal_id}",
        response_model=IntegrationPrincipalResponse,
        summary="Update platform-global integration principal",
    )
    async def update_system_integration_principal(
        principal_id: UUID,
        data: IntegrationPrincipalUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_superuser()),
    ):
        await _get_system_principal(session, principal_id)
        try:
            principal = await auth.integration_principal_service.update_principal(
                session,
                principal_id,
                actor_user_id=_actor_user_id(auth_result),
                **data.model_dump(exclude_unset=True),
            )
        except InvalidInputError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
        if principal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration principal not found")
        return await _to_principal_response(principal)

    @router.delete(
        "/system/integration-principals/{principal_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Archive platform-global integration principal",
    )
    async def delete_system_integration_principal(
        principal_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_superuser()),
    ):
        await _get_system_principal(session, principal_id)
        archived = await auth.integration_principal_service.archive_principal(
            session,
            principal_id,
            actor_user_id=_actor_user_id(auth_result),
            reason="Archived via system integration principal route",
        )
        if not archived:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration principal not found")
        return None

    @router.get(
        "/system/integration-principals/{principal_id}/api-keys",
        response_model=PaginatedResponse[ApiKeyResponse],
        summary="List platform-global integration principal API keys",
    )
    async def list_system_integration_principal_api_keys(
        principal_id: UUID,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
        status_filter: Optional[APIKeyStatus] = Query(default=None, alias="status"),
        search: Optional[str] = Query(default=None, min_length=1),
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_superuser()),
    ):
        del auth_result
        await _get_system_principal(session, principal_id)
        api_keys, total = await auth.api_key_service.list_integration_principal_api_keys_paginated(
            session,
            integration_principal_id=principal_id,
            status=status_filter,
            search=search,
            page=page,
            limit=limit,
        )
        pages = (total + limit - 1) // limit if total > 0 else 0
        return PaginatedResponse(
            items=[await _to_api_key_response(session, api_key) for api_key in api_keys],
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )

    @router.post(
        "/system/integration-principals/{principal_id}/api-keys",
        response_model=ApiKeyCreateResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create platform-global integration principal API key",
    )
    async def create_system_integration_principal_api_key(
        principal_id: UUID,
        data: SystemIntegrationApiKeyCreateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_superuser()),
    ):
        await _get_system_principal(session, principal_id)
        try:
            full_key, api_key_model = await auth.api_key_service.create_api_key(
                session,
                integration_principal_id=principal_id,
                name=data.name,
                scopes=data.scopes,
                prefix_type=data.prefix_type,
                ip_whitelist=data.ip_whitelist,
                rate_limit_per_minute=data.rate_limit_per_minute,
                expires_in_days=data.expires_in_days,
                description=data.description,
                key_kind=APIKeyKind.SYSTEM_INTEGRATION,
                actor_user_id=_actor_user_id(auth_result),
                event_source="integration_principals_router.create_system_integration_principal_api_key",
            )
        except InvalidInputError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

        api_key_response = await _to_api_key_response(session, api_key_model)
        return ApiKeyCreateResponse(**api_key_response.model_dump(), api_key=full_key)

    @router.get(
        "/system/integration-principals/{principal_id}/api-keys/{key_id}",
        response_model=ApiKeyResponse,
        summary="Get platform-global integration principal API key",
    )
    async def get_system_integration_principal_api_key(
        principal_id: UUID,
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_superuser()),
    ):
        del auth_result
        await _get_system_principal(session, principal_id)
        api_key = await _get_principal_api_key(session, principal_id, key_id)
        return await _to_api_key_response(session, api_key)

    @router.patch(
        "/system/integration-principals/{principal_id}/api-keys/{key_id}",
        response_model=ApiKeyResponse,
        summary="Update platform-global integration principal API key",
    )
    async def update_system_integration_principal_api_key(
        principal_id: UUID,
        key_id: UUID,
        data: SystemIntegrationApiKeyUpdateRequest,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_superuser()),
    ):
        await _get_system_principal(session, principal_id)
        await _get_principal_api_key(session, principal_id, key_id)
        try:
            api_key = await auth.api_key_service.update_api_key(
                session,
                key_id=key_id,
                actor_user_id=_actor_user_id(auth_result),
                event_source="integration_principals_router.update_system_integration_principal_api_key",
                **data.model_dump(exclude_unset=True),
            )
        except InvalidInputError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
        if api_key is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        return await _to_api_key_response(session, api_key)

    @router.delete(
        "/system/integration-principals/{principal_id}/api-keys/{key_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Revoke platform-global integration principal API key",
    )
    async def delete_system_integration_principal_api_key(
        principal_id: UUID,
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_superuser()),
    ):
        await _get_system_principal(session, principal_id)
        await _get_principal_api_key(session, principal_id, key_id)
        revoked = await auth.api_key_service.revoke_api_key(
            session,
            key_id,
            actor_user_id=_actor_user_id(auth_result),
            reason="API key revoked via system integration principal route",
            event_source="integration_principals_router.delete_system_integration_principal_api_key",
        )
        if not revoked:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        return None

    @router.post(
        "/system/integration-principals/{principal_id}/api-keys/{key_id}/rotate",
        response_model=ApiKeyCreateResponse,
        summary="Rotate platform-global integration principal API key",
    )
    async def rotate_system_integration_principal_api_key(
        principal_id: UUID,
        key_id: UUID,
        session: AsyncSession = Depends(auth.uow),
        auth_result=Depends(auth.deps.require_superuser()),
    ):
        await _get_system_principal(session, principal_id)
        await _get_principal_api_key(session, principal_id, key_id)
        full_key, api_key = await auth.api_key_service.rotate_api_key(
            session,
            key_id,
            actor_user_id=_actor_user_id(auth_result),
            event_source="integration_principals_router.rotate_system_integration_principal_api_key",
        )
        api_key_response = await _to_api_key_response(session, api_key)
        return ApiKeyCreateResponse(**api_key_response.model_dump(), api_key=full_key)

    return router
