"""
Shared per-request unit-of-work state.

``OutlabsAuth.uow`` registers the request's session in the ASGI scope under
``UOW_SCOPE_KEY`` so ``UnitOfWorkMiddleware`` can commit or roll back BEFORE
the response starts. FastAPI (>=0.106) runs dependency teardown only after
the response has been sent, so a commit there races the client's next
request — see ``outlabs_auth.middleware.uow`` for the full story.

Kept free of project imports so the core class and the middleware can both
use it without dragging in the service layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

#: HTTP methods whose unit of work commits on success; all others roll back.
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: ASGI-scope key holding the request's list of ``UnitOfWorkState`` records
#: (a list so multiple OutlabsAuth instances on one app cannot clobber each
#: other's sessions).
UOW_SCOPE_KEY = "outlabs_auth.uow_states"


class UnitOfWorkState:
    """One request-scoped session and whether its unit of work is finalized.

    ``finalized`` flips exactly once — by the middleware at response start,
    or by the dependency's teardown fallback — so commit/rollback never runs
    twice for the same request.
    """

    __slots__ = ("session", "finalized")

    def __init__(self, session: "AsyncSession") -> None:
        self.session = session
        self.finalized = False
