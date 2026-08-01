"""
Blog Domain Models - SimpleRBAC Example

Demonstrates domain-specific models for a blog application.
Uses SQLModel for PostgreSQL integration.
"""
from datetime import datetime, timezone
from typing import List, Literal, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, Index, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID, TIMESTAMP
from sqlmodel import Field, SQLModel


class BlogPost(SQLModel, table=True):
    """
    A blog post in the system.

    This model demonstrates SimpleRBAC permissions:
    - Public can read published posts
    - Writers can create posts
    - Editors can update their own posts
    - Admins can update/delete any post
    """

    __tablename__ = "blog_posts"
    __table_args__ = (
        Index("ix_blog_posts_author_id", "author_id"),
        Index("ix_blog_posts_status", "status"),
        Index("ix_blog_posts_status_created", "status", "created_at"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_type=PG_UUID(as_uuid=True),
        primary_key=True,
    )
    title: str = Field(max_length=200)
    content: str = Field(sa_column=Column(Text, nullable=False))
    author_id: UUID = Field(sa_type=PG_UUID(as_uuid=True))

    status: str = Field(default="draft", max_length=20)  # draft, published, archived
    tags: List[str] = Field(default_factory=list, sa_column=Column(ARRAY(Text)))

    # Metadata
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )
    view_count: int = Field(default=0)

    def increment_views(self):
        """Increment view count"""
        self.view_count += 1

    def can_be_edited_by(self, user_id: UUID, user_permissions: List[str]) -> bool:
        """Check if user can edit this post"""
        # Admin can edit any post
        if "post:update" in user_permissions or "post:delete" in user_permissions:
            return True

        # Editor can edit own posts
        if "post:update_own" in user_permissions and self.author_id == user_id:
            return True

        return False


class Comment(SQLModel, table=True):
    """
    A comment on a blog post.

    This model demonstrates comment permissions:
    - Writers can add comments
    - Users can edit/delete their own comments
    - Admins can delete any comment
    """

    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_post_id", "post_id"),
        Index("ix_comments_author_id", "author_id"),
        Index("ix_comments_post_created", "post_id", "created_at"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_type=PG_UUID(as_uuid=True),
        primary_key=True,
    )
    post_id: UUID = Field(sa_type=PG_UUID(as_uuid=True))
    author_id: UUID = Field(sa_type=PG_UUID(as_uuid=True))
    content: str = Field(max_length=1000)

    # Metadata
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )

    def can_be_deleted_by(self, user_id: UUID, user_permissions: List[str]) -> bool:
        """Check if user can delete this comment"""
        # Admin can delete any comment
        if "comment:delete" in user_permissions:
            return True

        # User can delete own comment
        if self.author_id == user_id:
            return True

        return False
