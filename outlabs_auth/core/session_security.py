"""Durable account proof generations; independent of wall-clock precision."""

from typing import Any, Mapping, cast
from uuid import UUID

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm.util import identity_key

from outlabs_auth.core.transaction_callbacks import mark_authority_change
from outlabs_auth.models.sql.user import User


def epoch(user: Any) -> int:
    return int(getattr(user, "session_security_epoch", None) or 0)


def proof_is_current(payload: Mapping[str, Any], user: Any) -> bool:
    # Legacy claims remain valid only before the first security event. Equality
    # rejects future as well as older generations, independent of iat rounding.
    claimed = payload.get("security_epoch", 0)
    return type(claimed) is int and claimed >= 0 and claimed == epoch(user)


async def advance_epoch(session: AsyncSession, user_id: UUID | str) -> int:
    identifier = UUID(str(user_id))
    stmt = (
        update(User)
        .where(cast(Any, User.id) == identifier)
        .values(session_security_epoch=func.coalesce(cast(Any, User.session_security_epoch), 0) + 1)
        .returning(cast(Any, User.session_security_epoch))
        .execution_options(synchronize_session=False)
    )
    result = await session.execute(stmt)
    value = result.scalar_one_or_none()
    if value is None:
        return 0
    user = session.identity_map.get(identity_key(User, identifier))
    if user is not None:
        set_committed_value(user, "session_security_epoch", value)
    mark_authority_change(session)
    return int(value)
