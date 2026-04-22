"""
Access scope resolution for authenticated principals.

This service provides a generic, reusable way to resolve which entities a
principal can access, including descendant expansion via closure tables.
"""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, cast
from uuid import UUID

from sqlalchemy import literal, or_, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import MembershipStatus
from outlabs_auth.models.sql.user import User


def _coerce_uuid(value: Any) -> Optional[UUID]:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except Exception:
        return None


def _sorted_uuid_list(values: Iterable[UUID]) -> list[UUID]:
    return sorted({value for value in values if value is not None}, key=str)


@dataclass
class PrincipalEntityScope:
    """
    Resolved entity access scope for a principal.

    `entity_ids` represents the effective set of accessible entities.
    """

    source: str
    is_global: bool = False
    principal_user_id: Optional[UUID] = None
    api_key_id: Optional[UUID] = None
    api_key_entity_id: Optional[UUID] = None
    includes_descendants: bool = False
    direct_entity_ids: list[UUID] = field(default_factory=list)
    root_entity_ids: list[UUID] = field(default_factory=list)
    entity_ids: list[UUID] = field(default_factory=list)
    member_user_ids: list[UUID] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "is_global": self.is_global,
            "principal_user_id": str(self.principal_user_id) if self.principal_user_id else None,
            "api_key_id": str(self.api_key_id) if self.api_key_id else None,
            "api_key_entity_id": str(self.api_key_entity_id) if self.api_key_entity_id else None,
            "includes_descendants": self.includes_descendants,
            "direct_entity_ids": [str(entity_id) for entity_id in self.direct_entity_ids],
            "root_entity_ids": [str(entity_id) for entity_id in self.root_entity_ids],
            "entity_ids": [str(entity_id) for entity_id in self.entity_ids],
            "member_user_ids": [str(user_id) for user_id in self.member_user_ids],
        }


class AccessScopeService:
    """
    Resolve principal access scope from auth context + EnterpriseRBAC data.
    """

    def __init__(self, config: AuthConfig):
        self.config = config

    async def resolve_for_auth_result(
        self,
        session: AsyncSession,
        auth_result: Optional[dict[str, Any]],
        *,
        include_member_user_ids: bool = True,
    ) -> dict[str, Any]:
        """
        Resolve scope from an auth result produced by AuthDeps.require_auth().
        """
        if not auth_result:
            return self._with_principal_member(
                PrincipalEntityScope(source="anonymous"),
                include_member_user_ids=include_member_user_ids,
            ).to_dict()

        source = str(auth_result.get("source") or "unknown")
        user = auth_result.get("user")
        user_id = _coerce_uuid(auth_result.get("user_id") or getattr(user, "id", None))

        if bool(getattr(user, "is_superuser", False)):
            return self._with_principal_member(
                PrincipalEntityScope(
                    source=source,
                    is_global=True,
                    principal_user_id=user_id,
                ),
                include_member_user_ids=include_member_user_ids,
            ).to_dict()

        if source == "api_key":
            return (
                await self.resolve_for_api_key(
                    session=session,
                    api_key=auth_result.get("api_key"),
                    principal_user_id=user_id,
                    include_member_user_ids=include_member_user_ids,
                )
            ).to_dict()

        if user_id is None:
            return self._with_principal_member(
                PrincipalEntityScope(source=source),
                include_member_user_ids=include_member_user_ids,
            ).to_dict()

        return (
            await self.resolve_for_user(
                session=session,
                user_id=user_id,
                source=source,
                user=user,
                include_member_user_ids=include_member_user_ids,
            )
        ).to_dict()

    async def resolve_for_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        source: str = "jwt",
        user: Optional[Any] = None,
        include_member_user_ids: bool = True,
    ) -> PrincipalEntityScope:
        """
        Resolve user scope from root entity + active memberships.
        """
        expand_descendants = bool(self.config.enable_entity_hierarchy)
        root_entity_ids, direct_entity_ids, descendant_entity_ids_by_ancestor = (
            await self._resolve_user_scope_inputs(
                session,
                user_id=user_id,
                user=user,
                expand_descendants=expand_descendants,
            )
        )

        seed_entity_ids = root_entity_ids | direct_entity_ids
        effective_entity_ids = set(seed_entity_ids)
        includes_descendants = bool(seed_entity_ids) and expand_descendants

        if includes_descendants:
            for descendant_entity_ids in descendant_entity_ids_by_ancestor.values():
                effective_entity_ids.update(descendant_entity_ids)

        scope = PrincipalEntityScope(
            source=source,
            principal_user_id=user_id,
            includes_descendants=includes_descendants,
            direct_entity_ids=_sorted_uuid_list(direct_entity_ids),
            root_entity_ids=_sorted_uuid_list(root_entity_ids),
            entity_ids=_sorted_uuid_list(effective_entity_ids),
        )
        if include_member_user_ids:
            scope.member_user_ids = await self._resolve_member_user_ids(
                session,
                self._select_member_projection_entity_ids(
                    scope,
                    descendant_entity_ids_by_ancestor=descendant_entity_ids_by_ancestor,
                ),
            )
        return self._with_principal_member(scope, include_member_user_ids=include_member_user_ids)

    async def resolve_for_api_key(
        self,
        session: AsyncSession,
        *,
        api_key: Optional[Any],
        principal_user_id: Optional[UUID] = None,
        include_member_user_ids: bool = True,
    ) -> PrincipalEntityScope:
        """
        Resolve scope from API key entity scoping fields.

        Rules:
        - no `entity_id` on key => global scope
        - `entity_id` only => entity-local scope
        - `entity_id` + `inherit_from_tree` => entity + descendants
        """
        if api_key is None:
            return self._with_principal_member(
                PrincipalEntityScope(
                    source="api_key",
                    principal_user_id=principal_user_id,
                ),
                include_member_user_ids=include_member_user_ids,
            )

        api_key_id = _coerce_uuid(getattr(api_key, "id", None))
        api_key_entity_id = _coerce_uuid(getattr(api_key, "entity_id", None))
        inherit_from_tree = bool(getattr(api_key, "inherit_from_tree", False))

        if api_key_entity_id is None:
            return self._with_principal_member(
                PrincipalEntityScope(
                    source="api_key",
                    is_global=True,
                    principal_user_id=principal_user_id,
                    api_key_id=api_key_id,
                ),
                include_member_user_ids=include_member_user_ids,
            )

        effective_entity_ids: set[UUID] = {api_key_entity_id}
        includes_descendants = bool(self.config.enable_entity_hierarchy and inherit_from_tree)
        descendant_entity_ids_by_ancestor: dict[UUID, set[UUID]] = {}

        if includes_descendants:
            descendant_entity_ids_by_ancestor = await self._resolve_descendant_entity_ids_by_ancestor(
                session,
                {api_key_entity_id},
            )
            effective_entity_ids.update(descendant_entity_ids_by_ancestor.get(api_key_entity_id, set()))

        scope = PrincipalEntityScope(
            source="api_key",
            principal_user_id=principal_user_id,
            api_key_id=api_key_id,
            api_key_entity_id=api_key_entity_id,
            includes_descendants=includes_descendants,
            direct_entity_ids=[api_key_entity_id],
            entity_ids=_sorted_uuid_list(effective_entity_ids),
        )
        if include_member_user_ids:
            scope.member_user_ids = await self._resolve_member_user_ids(
                session,
                self._select_member_projection_entity_ids(
                    scope,
                    descendant_entity_ids_by_ancestor=descendant_entity_ids_by_ancestor,
                ),
            )
        return self._with_principal_member(scope, include_member_user_ids=include_member_user_ids)

    async def _resolve_user_scope_inputs(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        user: Optional[Any] = None,
        expand_descendants: bool = True,
    ) -> tuple[set[UUID], set[UUID], dict[UUID, set[UUID]]]:
        """
        Resolve root, direct membership, and descendant entity ids in one round trip.

        Uses a CTE that unions the user's root entity (either hydrated literal or
        a User lookup) with active membership entity ids, optionally LEFT JOINed
        against the closure table to expand descendants.
        """
        hydrated_root: Optional[UUID] = None
        if user is not None:
            hydrated_root = _coerce_uuid(getattr(user, "root_entity_id", None))

        if user is not None:
            if hydrated_root is not None:
                root_select = select(
                    literal("root").label("source"),
                    literal(hydrated_root, type_=PG_UUID(as_uuid=True)).label("entity_id"),
                )
            else:
                root_select = None
        else:
            root_select = (
                select(
                    literal("root").label("source"),
                    cast(Any, User.root_entity_id).label("entity_id"),
                )
                .where(cast(Any, User.id) == user_id)
                .where(cast(Any, User.root_entity_id).is_not(None))
            )

        direct_select = select(
            literal("direct").label("source"),
            cast(Any, EntityMembership.entity_id).label("entity_id"),
        ).where(
            cast(Any, EntityMembership.user_id) == user_id,
            cast(Any, EntityMembership.status) == MembershipStatus.ACTIVE,
        )

        seeds = (
            root_select.union_all(direct_select) if root_select is not None else direct_select
        ).cte("seeds")

        if expand_descendants:
            stmt = select(
                seeds.c.source,
                seeds.c.entity_id,
                cast(Any, EntityClosure.descendant_id),
            ).select_from(
                seeds.outerjoin(
                    EntityClosure,
                    cast(Any, EntityClosure.ancestor_id) == seeds.c.entity_id,
                )
            )
        else:
            stmt = select(seeds.c.source, seeds.c.entity_id)

        result = await session.execute(stmt)
        rows = result.all()

        root_entity_ids: set[UUID] = set()
        direct_entity_ids: set[UUID] = set()
        descendant_entity_ids_by_ancestor: dict[UUID, set[UUID]] = {}

        for row in rows:
            row_source = row[0]
            entity_id = row[1]
            if entity_id is None:
                continue
            entity_uuid = cast(UUID, entity_id)

            if row_source == "root":
                root_entity_ids.add(entity_uuid)
            elif row_source == "direct":
                direct_entity_ids.add(entity_uuid)

            if expand_descendants:
                descendant_entity_ids_by_ancestor.setdefault(entity_uuid, set())
                descendant_id = row[2]
                if descendant_id is not None:
                    descendant_entity_ids_by_ancestor[entity_uuid].add(cast(UUID, descendant_id))

        return root_entity_ids, direct_entity_ids, descendant_entity_ids_by_ancestor

    async def _expand_descendant_entity_ids(
        self,
        session: AsyncSession,
        ancestor_entity_ids: set[UUID],
    ) -> set[UUID]:
        descendant_entity_ids_by_ancestor = await self._resolve_descendant_entity_ids_by_ancestor(
            session,
            ancestor_entity_ids,
        )
        descendant_entity_ids: set[UUID] = set()
        for resolved_entity_ids in descendant_entity_ids_by_ancestor.values():
            descendant_entity_ids.update(resolved_entity_ids)
        return descendant_entity_ids

    async def _resolve_descendant_entity_ids_by_ancestor(
        self,
        session: AsyncSession,
        ancestor_entity_ids: set[UUID],
    ) -> dict[UUID, set[UUID]]:
        if not ancestor_entity_ids:
            return {}

        closure_stmt = select(
            cast(Any, EntityClosure.ancestor_id),
            cast(Any, EntityClosure.descendant_id),
        ).where(cast(Any, EntityClosure.ancestor_id).in_(ancestor_entity_ids))
        closure_result = await session.execute(closure_stmt)
        descendants_by_ancestor: dict[UUID, set[UUID]] = {
            ancestor_entity_id: set() for ancestor_entity_id in ancestor_entity_ids
        }
        for ancestor_id, descendant_id in closure_result.all():
            if ancestor_id is None or descendant_id is None:
                continue
            descendants_by_ancestor.setdefault(cast(UUID, ancestor_id), set()).add(cast(UUID, descendant_id))
        return descendants_by_ancestor

    async def _resolve_member_user_ids(
        self,
        session: AsyncSession,
        entity_ids: list[UUID],
        *,
        include_descendants: bool = False,
    ) -> list[UUID]:
        if not entity_ids:
            return []

        scoped_entity_ids = set(entity_ids)
        if include_descendants:
            scoped_entity_ids.update(await self._expand_descendant_entity_ids(session, set(entity_ids)))

        if not scoped_entity_ids:
            return []

        now = datetime.now(timezone.utc)
        stmt = select(cast(Any, EntityMembership.user_id)).where(
            cast(Any, EntityMembership.entity_id).in_(_sorted_uuid_list(scoped_entity_ids)),
            cast(Any, EntityMembership.status) == MembershipStatus.ACTIVE,
            or_(
                cast(Any, EntityMembership.valid_from).is_(None),
                cast(Any, EntityMembership.valid_from) <= now,
            ),
            or_(
                cast(Any, EntityMembership.valid_until).is_(None),
                cast(Any, EntityMembership.valid_until) >= now,
            ),
        )
        result = await session.execute(stmt)
        return _sorted_uuid_list(user_id for (user_id,) in result.all() if user_id is not None)

    def _select_member_projection_entity_ids(
        self,
        scope: PrincipalEntityScope,
        *,
        descendant_entity_ids_by_ancestor: Optional[dict[UUID, set[UUID]]] = None,
    ) -> list[UUID]:
        if scope.direct_entity_ids:
            projected_entity_ids = set(scope.direct_entity_ids)
            if scope.includes_descendants and descendant_entity_ids_by_ancestor:
                for direct_entity_id in scope.direct_entity_ids:
                    projected_entity_ids.update(descendant_entity_ids_by_ancestor.get(direct_entity_id, set()))
            return _sorted_uuid_list(projected_entity_ids)
        return _sorted_uuid_list(scope.entity_ids)

    def _with_principal_member(
        self,
        scope: PrincipalEntityScope,
        *,
        include_member_user_ids: bool = True,
    ) -> PrincipalEntityScope:
        if not include_member_user_ids or scope.principal_user_id is None:
            return scope
        scope.member_user_ids = _sorted_uuid_list([*scope.member_user_ids, scope.principal_user_id])
        return scope
