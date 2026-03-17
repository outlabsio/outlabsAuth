"""
ABAC Cookbook Example

Shows how to:
  - Enable ABAC and resource context middleware
  - Configure role conditions via API (roles/{id}/condition-groups + roles/{id}/conditions)
  - Enforce ABAC using server-derived resource context (no client-trust)
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from models import Document
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from outlabs_auth import OutlabsAuth
from outlabs_auth.observability import ObservabilityPresets
from outlabs_auth.routers import (
    get_auth_router,
    get_permissions_router,
    get_roles_router,
    get_users_router,
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/abac_cookbook",
)
SECRET_KEY = os.getenv("SECRET_KEY", "abac-cookbook-secret-change-me")

auth: Optional[OutlabsAuth] = None


class DocumentCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    status: str = Field(default="draft")


class DocumentUpdateRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Convert UUID fields to strings before validation."""
        if hasattr(obj, "id") and not isinstance(obj.id, str):
            # Create a dict and convert UUID to string
            data = {
                "id": str(obj.id),
                "title": obj.title,
                "status": obj.status,
                "created_at": obj.created_at,
                "updated_at": obj.updated_at,
            }
            return super().model_validate(data, **kwargs)
        return super().model_validate(obj, **kwargs)


async def _document_resource_context(
    request,
    session: AsyncSession,
    auth_result: dict,
) -> dict:
    raw = request.path_params.get("doc_id")
    try:
        doc_id = UUID(str(raw))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid doc_id")

    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return {"status": doc.status, "document_id": str(doc.id)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global auth

    obs_config = ObservabilityPresets.development()
    obs_config.enable_metrics = False

    auth = OutlabsAuth(
        database_url=DATABASE_URL,
        secret_key=SECRET_KEY,
        enable_abac=True,
        observability_config=obs_config,
    )
    await auth.initialize()

    async with auth.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    auth.instrument_fastapi(
        app,
        debug=True,
        exception_handler_mode="global",
        include_metrics=False,
        include_correlation_id=True,
        include_resource_context=True,
    )

    app.include_router(get_auth_router(auth, prefix="/v1/auth"))
    app.include_router(get_users_router(auth, prefix="/v1/users"))
    app.include_router(get_roles_router(auth, prefix="/v1/roles"))
    app.include_router(get_permissions_router(auth, prefix="/v1/permissions"))

    yield


app = FastAPI(title="ABAC Cookbook", version="0.1.0", lifespan=lifespan)


def get_auth() -> OutlabsAuth:
    if auth is None:
        raise HTTPException(status_code=500, detail="Auth not initialized")
    return auth


async def get_session(request: Request):
    """Get database session from auth.uow"""
    async for session in get_auth().uow(request):
        yield session


async def require_document_read(
    request: Request, session: AsyncSession = Depends(get_session)
):
    """Dependency for document:read permission"""
    dep_fn = get_auth().deps.require_permission("document:read")
    return await dep_fn(request=request, session=session)


async def require_document_create(
    request: Request, session: AsyncSession = Depends(get_session)
):
    """Dependency for document:create permission"""
    dep_fn = get_auth().deps.require_permission("document:create")
    return await dep_fn(request=request, session=session)


async def require_document_update(
    request: Request, session: AsyncSession = Depends(get_session)
):
    """Dependency for document:update permission with resource context"""
    dep_fn = get_auth().deps.require_permission(
        "document:update",
        resource_context_provider=_document_resource_context,
    )
    return await dep_fn(request=request, session=session)


@app.get("/health")
async def health():
    return {"ok": True}


@app.get(
    "/v1/documents",
    response_model=list[DocumentResponse],
    summary="List documents",
)
async def list_documents(
    request: Request,
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_document_read),
):
    docs = (await session.execute(select(Document))).scalars().all()
    return [DocumentResponse.model_validate(d) for d in docs]


@app.post(
    "/v1/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create document",
)
async def create_document(
    data: DocumentCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_document_create),
):
    doc = Document(
        title=data.title,
        status=data.status,
        created_by=UUID(auth_result["user_id"]),
    )
    session.add(doc)
    await session.flush()
    return DocumentResponse.model_validate(doc)


@app.patch(
    "/v1/documents/{doc_id}",
    response_model=DocumentResponse,
    summary="Update document",
)
async def update_document(
    doc_id: UUID,
    data: DocumentUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_document_update),
):
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if data.title is not None:
        doc.title = data.title
    if data.status is not None:
        doc.status = data.status
    doc.updated_at = datetime.now(timezone.utc)

    await session.flush()
    return DocumentResponse.model_validate(doc)
