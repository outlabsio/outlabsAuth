"""
Blog Domain Models - SimpleRBAC Example

Demonstrates domain-specific models for a blog application.
Uses Beanie ODM for MongoDB integration.
"""
from datetime import datetime
from typing import List, Literal, Optional
from beanie import Document
from pydantic import Field


class BlogPost(Document):
    """
    A blog post in the system.

    This model demonstrates SimpleRBAC permissions:
    - Public can read published posts
    - Writers can create posts
    - Editors can update their own posts
    - Admins can update/delete any post
    """

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    author_id: str = Field(..., description="User ID who created the post")

    status: Literal["draft", "published", "archived"] = "draft"
    tags: List[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    view_count: int = 0

    class Settings:
        name = "blog_posts"
        indexes = [
            "author_id",
            "status",
            [("status", 1), ("created_at", -1)],  # For listing published posts
            "tags",
        ]

    def increment_views(self):
        """Increment view count"""
        self.view_count += 1

    def can_be_edited_by(self, user_id: str, user_permissions: List[str]) -> bool:
        """Check if user can edit this post"""
        # Admin can edit any post
        if "post:update" in user_permissions or "post:delete" in user_permissions:
            return True

        # Editor can edit own posts
        if "post:update_own" in user_permissions and self.author_id == user_id:
            return True

        return False


class Comment(Document):
    """
    A comment on a blog post.

    This model demonstrates comment permissions:
    - Writers can add comments
    - Users can edit/delete their own comments
    - Admins can delete any comment
    """

    post_id: str = Field(..., description="Blog post ID")
    author_id: str = Field(..., description="User ID who created the comment")
    content: str = Field(..., min_length=1, max_length=1000)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "comments"
        indexes = [
            "post_id",
            "author_id",
            [("post_id", 1), ("created_at", 1)],  # For listing comments on a post
        ]

    def can_be_deleted_by(self, user_id: str, user_permissions: List[str]) -> bool:
        """Check if user can delete this comment"""
        # Admin can delete any comment
        if "comment:delete" in user_permissions:
            return True

        # User can delete own comment
        if self.author_id == user_id:
            return True

        return False
