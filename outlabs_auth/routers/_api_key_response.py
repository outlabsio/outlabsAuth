"""Shared API key response builders for router surfaces."""

from typing import Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.schemas.api_key import ApiKeyResponse


async def build_api_key_response(
    auth: Any,
    session: AsyncSession,
    api_key: Any,
) -> ApiKeyResponse:
    """Build a single API key response."""
    responses = await build_api_key_responses(auth, session, [api_key])
    return responses[0]


async def build_api_key_responses(
    auth: Any,
    session: AsyncSession,
    api_keys: List[Any],
) -> List[ApiKeyResponse]:
    """Build API key responses with batched scope, IP whitelist, and effectiveness lookups."""
    if not api_keys:
        return []

    key_ids = [api_key.id for api_key in api_keys]
    scopes_by_key_id = await auth.api_key_service.get_api_key_scopes_map(session, key_ids)
    ip_whitelist_by_key_id = await auth.api_key_service.get_api_key_ip_whitelist_map(session, key_ids)

    effectiveness_by_key_id = {}
    if getattr(auth, "api_key_policy_service", None) is not None:
        effectiveness_by_key_id = await auth.api_key_policy_service.evaluate_effectiveness_map(
            session,
            api_keys=api_keys,
            scopes_by_key_id=scopes_by_key_id,
        )

    responses: List[ApiKeyResponse] = []
    for api_key in api_keys:
        scopes = scopes_by_key_id.get(api_key.id, [])
        effectiveness = effectiveness_by_key_id.get(api_key.id)
        responses.append(
            ApiKeyResponse(
                id=str(api_key.id),
                prefix=api_key.prefix,
                name=api_key.name,
                key_kind=api_key.key_kind,
                scopes=scopes,
                ip_whitelist=ip_whitelist_by_key_id.get(api_key.id) or None,
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
                is_currently_effective=(effectiveness.is_currently_effective if effectiveness is not None else None),
                ineffective_reasons=(effectiveness.ineffective_reasons if effectiveness is not None else None),
            )
        )

    return responses
