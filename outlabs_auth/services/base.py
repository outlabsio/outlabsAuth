"""
Base Service for SQLAlchemy Operations

Provides common CRUD patterns and session management.
"""

from typing import Any, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseService(Generic[ModelType]):
    """
    Base service class with common CRUD operations.

    All services receive an AsyncSession for database operations.
    Sessions are managed by the caller (typically via FastAPI dependencies).

    Usage:
        class UserService(BaseService[User]):
            def __init__(self):
                super().__init__(User)

            async def get_by_email(self, session: AsyncSession, email: str) -> Optional[User]:
                return await self.get_one(session, User.email == email)
    """

    def __init__(self, model: Type[ModelType]):
        """
        Initialize base service.

        Args:
            model: SQLModel class for this service
        """
        self.model = model

    async def get_by_id(
        self,
        session: AsyncSession,
        id: UUID,
        options: Optional[List[Any]] = None,
    ) -> Optional[ModelType]:
        """
        Get a record by ID.

        Args:
            session: Database session
            id: Record UUID
            options: Optional eager loading options (selectinload, joinedload)

        Returns:
            Record if found, None otherwise
        """
        stmt = select(self.model).where(self.model.id == id)
        if options:
            for opt in options:
                stmt = stmt.options(opt)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_one(
        self,
        session: AsyncSession,
        *filters,
        options: Optional[List[Any]] = None,
    ) -> Optional[ModelType]:
        """
        Get a single record matching filters.

        Args:
            session: Database session
            *filters: SQLAlchemy filter conditions
            options: Optional eager loading options

        Returns:
            First matching record or None
        """
        stmt = select(self.model).where(*filters)
        if options:
            for opt in options:
                stmt = stmt.options(opt)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many(
        self,
        session: AsyncSession,
        *filters,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[Any] = None,
        options: Optional[List[Any]] = None,
    ) -> List[ModelType]:
        """
        Get multiple records with pagination.

        Args:
            session: Database session
            *filters: SQLAlchemy filter conditions
            skip: Number of records to skip
            limit: Maximum records to return
            order_by: Column to order by
            options: Optional eager loading options

        Returns:
            List of matching records
        """
        stmt = select(self.model)
        if filters:
            stmt = stmt.where(*filters)
        if options:
            for opt in options:
                stmt = stmt.options(opt)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(skip).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def count(
        self,
        session: AsyncSession,
        *filters,
    ) -> int:
        """
        Count records matching filters.

        Args:
            session: Database session
            *filters: SQLAlchemy filter conditions

        Returns:
            Count of matching records
        """
        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = stmt.where(*filters)
        result = await session.execute(stmt)
        return result.scalar() or 0

    async def create(
        self,
        session: AsyncSession,
        obj: ModelType,
    ) -> ModelType:
        """
        Create a new record.

        Args:
            session: Database session
            obj: Record to create

        Returns:
            Created record with ID populated
        """
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return obj

    async def update(
        self,
        session: AsyncSession,
        obj: ModelType,
    ) -> ModelType:
        """
        Update an existing record.

        Args:
            session: Database session
            obj: Record to update

        Returns:
            Updated record
        """
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return obj

    async def delete(
        self,
        session: AsyncSession,
        obj: ModelType,
    ) -> bool:
        """
        Delete a record.

        Args:
            session: Database session
            obj: Record to delete

        Returns:
            True if deleted
        """
        await session.delete(obj)
        await session.flush()
        return True

    async def exists(
        self,
        session: AsyncSession,
        *filters,
    ) -> bool:
        """
        Check if a record matching filters exists.

        Args:
            session: Database session
            *filters: SQLAlchemy filter conditions

        Returns:
            True if exists
        """
        stmt = select(func.count()).select_from(self.model).where(*filters)
        result = await session.execute(stmt)
        return (result.scalar() or 0) > 0
