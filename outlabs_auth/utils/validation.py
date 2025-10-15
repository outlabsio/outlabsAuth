"""
Validation utilities for input data

Provides common validation functions used across services.
"""
import re
from typing import Optional
from pydantic import EmailStr

from outlabs_auth.core.exceptions import ValidationError, InvalidInputError


def validate_email(email: str) -> str:
    """
    Validate and normalize email address.

    Args:
        email: Email address to validate

    Returns:
        str: Normalized email (lowercase)

    Raises:
        InvalidInputError: If email is invalid

    Example:
        >>> validate_email("User@Example.COM")
        'user@example.com'
    """
    if not email or not isinstance(email, str):
        raise InvalidInputError(
            message="Email is required",
            details={"field": "email"}
        )

    # Normalize to lowercase
    email = email.lower().strip()

    # Basic email validation
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        raise InvalidInputError(
            message="Invalid email format",
            details={"field": "email", "value": email}
        )

    return email


def validate_name(name: str, field_name: str = "name", min_length: int = 1, max_length: int = 100) -> str:
    """
    Validate name fields (user names, role names, etc.).

    Args:
        name: Name to validate
        field_name: Name of the field (for error messages)
        min_length: Minimum length
        max_length: Maximum length

    Returns:
        str: Validated name (stripped)

    Raises:
        InvalidInputError: If name is invalid

    Example:
        >>> validate_name("  John Doe  ")
        'John Doe'
    """
    if not name or not isinstance(name, str):
        raise InvalidInputError(
            message=f"{field_name} is required",
            details={"field": field_name}
        )

    name = name.strip()

    if len(name) < min_length:
        raise InvalidInputError(
            message=f"{field_name} must be at least {min_length} characters",
            details={"field": field_name, "min_length": min_length}
        )

    if len(name) > max_length:
        raise InvalidInputError(
            message=f"{field_name} cannot exceed {max_length} characters",
            details={"field": field_name, "max_length": max_length}
        )

    return name


def validate_slug(slug: str, field_name: str = "slug") -> str:
    """
    Validate and normalize slug (URL-safe identifier).

    Args:
        slug: Slug to validate
        field_name: Name of the field (for error messages)

    Returns:
        str: Validated slug (lowercase, alphanumeric with hyphens/underscores)

    Raises:
        InvalidInputError: If slug is invalid

    Example:
        >>> validate_slug("My-Entity_123")
        'my-entity_123'
    """
    if not slug or not isinstance(slug, str):
        raise InvalidInputError(
            message=f"{field_name} is required",
            details={"field": field_name}
        )

    slug = slug.lower().strip()

    # Allow alphanumeric, hyphens, and underscores
    if not re.match(r'^[a-z0-9_-]+$', slug):
        raise InvalidInputError(
            message=f"{field_name} can only contain lowercase letters, numbers, hyphens, and underscores",
            details={"field": field_name, "value": slug}
        )

    if len(slug) < 2:
        raise InvalidInputError(
            message=f"{field_name} must be at least 2 characters",
            details={"field": field_name}
        )

    if len(slug) > 100:
        raise InvalidInputError(
            message=f"{field_name} cannot exceed 100 characters",
            details={"field": field_name}
        )

    return slug


def validate_permission_name(permission: str) -> str:
    """
    Validate permission name follows resource:action format.

    Args:
        permission: Permission name to validate

    Returns:
        str: Validated permission (lowercase)

    Raises:
        InvalidInputError: If permission format is invalid

    Example:
        >>> validate_permission_name("user:create")
        'user:create'
        >>> validate_permission_name("invalid")
        InvalidInputError: Permission must follow 'resource:action' format
    """
    if not permission or not isinstance(permission, str):
        raise InvalidInputError(
            message="Permission name is required",
            details={"field": "permission"}
        )

    permission = permission.lower().strip()

    # Check format: resource:action
    if ':' not in permission:
        raise InvalidInputError(
            message="Permission must follow 'resource:action' format (e.g., 'user:create')",
            details={"field": "permission", "value": permission}
        )

    parts = permission.split(':')
    if len(parts) != 2:
        raise InvalidInputError(
            message="Permission must have exactly one colon separating resource and action",
            details={"field": "permission", "value": permission}
        )

    resource, action = parts
    if not resource or not action:
        raise InvalidInputError(
            message="Both resource and action must be non-empty",
            details={"field": "permission", "value": permission}
        )

    # Validate characters (alphanumeric, underscore, hyphen, or asterisk for wildcard)
    if resource != '*' and not re.match(r'^[a-z0-9_-]+$', resource):
        raise InvalidInputError(
            message="Resource must contain only letters, numbers, underscores, hyphens, or asterisk",
            details={"field": "permission", "part": "resource", "value": resource}
        )

    if action != '*' and not re.match(r'^[a-z0-9_-]+$', action):
        raise InvalidInputError(
            message="Action must contain only letters, numbers, underscores, hyphens, or asterisk",
            details={"field": "permission", "part": "action", "value": action}
        )

    return permission


def validate_object_id(obj_id: str, field_name: str = "id") -> str:
    """
    Validate MongoDB ObjectId format.

    Args:
        obj_id: Object ID to validate
        field_name: Name of the field (for error messages)

    Returns:
        str: Validated object ID

    Raises:
        InvalidInputError: If ID format is invalid

    Example:
        >>> validate_object_id("507f1f77bcf86cd799439011")
        '507f1f77bcf86cd799439011'
    """
    if not obj_id or not isinstance(obj_id, str):
        raise InvalidInputError(
            message=f"{field_name} is required",
            details={"field": field_name}
        )

    obj_id = obj_id.strip()

    # MongoDB ObjectId is 24 hex characters
    if not re.match(r'^[a-fA-F0-9]{24}$', obj_id):
        raise InvalidInputError(
            message=f"Invalid {field_name} format (expected 24-character hex string)",
            details={"field": field_name, "value": obj_id}
        )

    return obj_id


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize string input (strip whitespace, limit length).

    Args:
        value: String to sanitize
        max_length: Maximum length (truncates if longer)

    Returns:
        str: Sanitized string

    Example:
        >>> sanitize_string("  hello world  ", max_length=5)
        'hello'
    """
    if not isinstance(value, str):
        return str(value)

    # Strip whitespace
    value = value.strip()

    # Truncate if needed
    if max_length and len(value) > max_length:
        value = value[:max_length]

    return value


def validate_positive_integer(value: int, field_name: str = "value", min_value: int = 1) -> int:
    """
    Validate positive integer.

    Args:
        value: Integer to validate
        field_name: Name of the field (for error messages)
        min_value: Minimum allowed value

    Returns:
        int: Validated integer

    Raises:
        InvalidInputError: If value is not a positive integer

    Example:
        >>> validate_positive_integer(5)
        5
        >>> validate_positive_integer(0)
        InvalidInputError: value must be at least 1
    """
    if not isinstance(value, int):
        raise InvalidInputError(
            message=f"{field_name} must be an integer",
            details={"field": field_name, "value": value}
        )

    if value < min_value:
        raise InvalidInputError(
            message=f"{field_name} must be at least {min_value}",
            details={"field": field_name, "value": value, "min_value": min_value}
        )

    return value
