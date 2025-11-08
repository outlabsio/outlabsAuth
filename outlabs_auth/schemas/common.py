"""Common schemas shared across the library."""

from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response schema.

    Used for list endpoints that support pagination.

    Example:
        ```python
        @router.get("/users", response_model=PaginatedResponse[UserResponse])
        async def list_users(page: int = 1, limit: int = 20):
            users, total = await service.list_users(page, limit)
            return PaginatedResponse(
                items=users,
                total=total,
                page=page,
                limit=limit,
                pages=(total + limit - 1) // limit
            )
        ```
    """
    items: List[T] = Field(description="List of items for the current page")
    total: int = Field(description="Total number of items across all pages")
    page: int = Field(description="Current page number (1-indexed)")
    limit: int = Field(description="Number of items per page")
    pages: int = Field(description="Total number of pages")

    class Config:
        from_attributes = True
