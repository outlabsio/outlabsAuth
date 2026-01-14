# OutlabsAuth: MongoDB to PostgreSQL Migration Guide

> **Status:** Planning Complete
> **Start Date:** TBD
> **Estimated Duration:** 6 weeks
> **Branch:** `library-redesign` (or create `postgres-migration`)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Decisions](#2-architecture-decisions)
3. [Local Development Setup](#3-local-development-setup)
4. [Phase 1: Database Infrastructure](#4-phase-1-database-infrastructure-week-1)
5. [Phase 2: Model Migration](#5-phase-2-model-migration-week-2)
6. [Phase 3: Alembic Setup](#6-phase-3-alembic-setup-week-3)
7. [Phase 4: Service Layer Migration](#7-phase-4-service-layer-migration-week-4)
8. [Phase 5: Core Auth Class Changes](#8-phase-5-core-auth-class-changes-week-5)
9. [Phase 6: Examples & Testing](#9-phase-6-examples--testing-week-6)
10. [Query Pattern Reference](#10-query-pattern-reference)
11. [Model Schema Reference](#11-model-schema-reference)
12. [Verification Checklist](#12-verification-checklist)

---

## 1. Executive Summary

### What We're Doing
Migrating OutlabsAuth from **Beanie/MongoDB** to **SQLModel/SQLAlchemy with PostgreSQL**.

### Why
- PostgreSQL is more widely deployed in enterprise environments
- SQLAlchemy/SQLModel provides better type safety and IDE support
- Relational model better suits the permission/role/entity relationships
- Alembic provides robust schema migration tooling

### Key Decisions Made
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database Backend | Replace MongoDB entirely | Simpler than dual-backend |
| Primary Keys | UUID | Globally unique, good for distributed systems |
| Migrations | Alembic | Industry standard for SQLAlchemy |
| ORM | SQLModel | Built on SQLAlchemy, Pydantic-native |
| Async Driver | asyncpg | Best performance for async PostgreSQL |

### What's NOT Changing
- Redis integration (caching, counters, activity tracking)
- API contracts (HTTP endpoints, request/response schemas)
- Business logic (permission resolution, ABAC, tree permissions)
- Auth flows (JWT, API keys, OAuth patterns)

---

## 2. Architecture Decisions

### 2.1 Library Pattern
OutlabsAuth is a **library** users install via pip. Database initialization must:
- Accept user-provided database URL
- Support auto-migration (dev) or manual migration (prod)
- Package migrations with the library

### 2.2 Session Management
SQLAlchemy async sessions are injected into services:

```python
# OLD (Beanie) - implicit database access
user = await UserModel.get(user_id)

# NEW (SQLAlchemy) - explicit session
user = await session.get(UserModel, user_id)
```

### 2.3 Feature Flag Model Registration
Models are registered based on preset:
- **SimpleRBAC**: users, roles, permissions, refresh_tokens, user_role_memberships, api_keys
- **EnterpriseRBAC**: adds entities, entity_memberships, entity_closure

### 2.4 Type Mappings
| Python Type | PostgreSQL Type |
|-------------|-----------------|
| `UUID` | `UUID` |
| `List[str]` | `ARRAY(VARCHAR)` |
| `Dict[str, Any]` | `JSONB` |
| `datetime` | `TIMESTAMP WITH TIMEZONE` |
| `Enum` | `VARCHAR` with constraint |
| `Link[Model]` (Beanie) | `ForeignKey` + `Relationship` |

---

## 3. Local Development Setup

### 3.1 PostgreSQL Container
Using existing container from `localDevServices`:

```bash
# Container already running at:
# - Host: localhost
# - Port: 5432
# - User: postgres
# - Password: postgres

# Verify it's running
docker ps | grep postgres

# Create the database
docker exec -it postgres psql -U postgres -c "CREATE DATABASE outlabs_auth;"

# Verify
docker exec -it postgres psql -U postgres -c "\l" | grep outlabs_auth
```

### 3.2 Connection Strings

**Development:**
```bash
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth"
```

**For sync operations (Alembic offline):**
```bash
DATABASE_URL_SYNC="postgresql://postgres:postgres@localhost:5432/outlabs_auth"
```

### 3.3 Test Database
```bash
docker exec -it postgres psql -U postgres -c "CREATE DATABASE outlabs_auth_test;"
```

---

## 4. Phase 1: Database Infrastructure (Week 1)

### 4.1 Add Dependencies

**File:** `pyproject.toml`

```toml
[project.dependencies]
# ... existing deps ...
sqlmodel = ">=0.0.22"
sqlalchemy = { version = ">=2.0.0", extras = ["asyncio"] }
asyncpg = ">=0.29.0"
alembic = ">=1.13.0"
```

### 4.2 Create Database Module

**Create directory:** `outlabs_auth/database/`

```
outlabs_auth/database/
├── __init__.py
├── engine.py          # Engine factory, session management
├── base.py            # SQLModel base class
├── registry.py        # Model registration by feature flags
└── tenant.py          # Multi-tenant query helpers
```

### 4.3 Engine Factory

**File:** `outlabs_auth/database/engine.py`

```python
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool


class DatabaseConfig:
    """Database configuration for OutlabsAuth."""

    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_pre_ping: bool = True,
        pool_recycle: int = 3600,
    ):
        self.database_url = database_url
        self.echo = echo
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_pre_ping = pool_pre_ping
        self.pool_recycle = pool_recycle


def create_engine(config: DatabaseConfig) -> AsyncEngine:
    """Create async SQLAlchemy engine."""
    return create_async_engine(
        config.database_url,
        echo=config.echo,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_pre_ping=config.pool_pre_ping,
        pool_recycle=config.pool_recycle,
        poolclass=AsyncAdaptedQueuePool,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_session(
    session_factory: async_sessionmaker,
) -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class DatabasePresets:
    """Pre-configured database settings."""

    @staticmethod
    def development(database_url: str) -> DatabaseConfig:
        return DatabaseConfig(
            database_url=database_url,
            pool_size=2,
            max_overflow=3,
            echo=True,
        )

    @staticmethod
    def production(database_url: str) -> DatabaseConfig:
        return DatabaseConfig(
            database_url=database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
```

### 4.4 Base Model

**File:** `outlabs_auth/database/base.py`

```python
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class BaseModel(SQLModel):
    """Base model for all OutlabsAuth tables."""

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=lambda: datetime.now(timezone.utc),
        ),
    )
    tenant_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String(36), index=True),
    )
```

### 4.5 Model Registry

**File:** `outlabs_auth/database/registry.py`

```python
from typing import List, Type
from sqlmodel import SQLModel


class ModelRegistry:
    """Registry for OutlabsAuth models based on feature flags."""

    @classmethod
    def get_models(
        cls,
        enable_entity_hierarchy: bool = False,
    ) -> List[Type[SQLModel]]:
        """Get list of models based on feature flags."""
        from outlabs_auth.models.sql import (
            User, Role, Permission, RefreshToken, APIKey,
            UserRoleMembership, Entity, EntityMembership, EntityClosure,
        )

        # Core models (always included)
        models = [User, Role, Permission, RefreshToken, APIKey]

        if enable_entity_hierarchy:
            # EnterpriseRBAC
            models.extend([Entity, EntityMembership, EntityClosure])
        else:
            # SimpleRBAC
            models.append(UserRoleMembership)

        return models
```

### 4.6 Week 1 Checklist

- [ ] Add SQLModel, SQLAlchemy, asyncpg, Alembic to `pyproject.toml`
- [ ] Create `outlabs_auth/database/` directory
- [ ] Implement `engine.py` with DatabaseConfig and factory functions
- [ ] Implement `base.py` with BaseModel class
- [ ] Implement `registry.py` with ModelRegistry
- [ ] Implement `tenant.py` with TenantMixin (optional)
- [ ] Create `outlabs_auth/database/__init__.py` with exports
- [ ] Run `uv sync` to install new dependencies
- [ ] Verify PostgreSQL connection works

---

## 5. Phase 2: Model Migration (Week 2)

### 5.1 Create Models Directory

**Create directory:** `outlabs_auth/models/sql/`

```
outlabs_auth/models/sql/
├── __init__.py
├── user.py
├── role.py
├── permission.py
├── token.py                  # RefreshToken
├── user_role_membership.py   # SimpleRBAC
├── entity.py                 # EnterpriseRBAC
├── entity_membership.py      # EnterpriseRBAC
├── closure.py                # EnterpriseRBAC
├── api_key.py
├── social_account.py
├── oauth_state.py
├── activity_metric.py
└── condition.py              # Pydantic only (JSONB)
```

### 5.2 Enums

**File:** `outlabs_auth/models/sql/enums.py`

```python
from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"
    DELETED = "deleted"


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING = "pending"
    REJECTED = "rejected"


class EntityClass(str, Enum):
    STRUCTURAL = "structural"
    ACCESS_GROUP = "access_group"


class APIKeyStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ConditionOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    LESS_THAN = "less_than"
    GREATER_THAN = "greater_than"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    # ... etc
```

### 5.3 User Model

**File:** `outlabs_auth/models/sql/user.py`

```python
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID, VARCHAR

from outlabs_auth.database.base import BaseModel
from .enums import UserStatus

if TYPE_CHECKING:
    from .token import RefreshToken
    from .api_key import APIKey


class User(BaseModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_status", "status"),
        Index("ix_users_tenant_id", "tenant_id"),
    )

    # Authentication
    email: str = Field(index=True, max_length=255)
    hashed_password: Optional[str] = Field(default=None, max_length=255)
    auth_methods: List[str] = Field(
        default=["PASSWORD"],
        sa_column=Column(ARRAY(VARCHAR(50)), nullable=False, server_default="{PASSWORD}"),
    )

    # Profile
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)

    # Status
    status: UserStatus = Field(default=UserStatus.ACTIVE)
    is_superuser: bool = Field(default=False)
    email_verified: bool = Field(default=False)
    suspended_until: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    # Security
    last_login: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    failed_login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = None

    # Password Reset
    password_reset_token: Optional[str] = Field(default=None, max_length=255)
    password_reset_expires: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )

    # Relationships
    refresh_tokens: List["RefreshToken"] = Relationship(back_populates="user")
    api_keys: List["APIKey"] = Relationship(back_populates="owner")

    @property
    def full_name(self) -> str:
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts) if parts else self.email.split("@")[0]

    @property
    def is_locked(self) -> bool:
        if self.locked_until:
            return datetime.now(timezone.utc) < self.locked_until
        return False

    def can_authenticate(self) -> bool:
        return self.status == UserStatus.ACTIVE and not self.is_locked
```

### 5.4 Entity Closure Table

**File:** `outlabs_auth/models/sql/closure.py`

```python
from typing import Optional
from uuid import UUID

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from outlabs_auth.database.base import BaseModel


class EntityClosure(BaseModel, table=True):
    """
    Closure table for O(1) ancestor/descendant queries.

    For hierarchy: Platform → Org → Dept → Team
    Records:
      (Platform, Platform, 0)  # self
      (Platform, Org, 1)       # direct child
      (Platform, Dept, 2)      # grandchild
      (Platform, Team, 3)      # great-grandchild
      (Org, Org, 0)            # self
      (Org, Dept, 1)           # direct child
      ... etc
    """
    __tablename__ = "entity_closure"
    __table_args__ = (
        UniqueConstraint("ancestor_id", "descendant_id", name="uq_entity_closure"),
        Index("ix_closure_ancestor_depth", "ancestor_id", "depth"),
        Index("ix_closure_descendant_depth", "descendant_id", "depth"),
    )

    ancestor_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    descendant_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    depth: int = Field(ge=0)
```

### 5.5 Junction Table for EntityMembership↔Role

**File:** `outlabs_auth/models/sql/entity_membership.py` (partial)

```python
# Junction table (no BaseModel inheritance - composite PK)
class EntityMembershipRole(SQLModel, table=True):
    """Junction table for EntityMembership <-> Role (many-to-many)."""
    __tablename__ = "entity_membership_roles"

    membership_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("entity_memberships.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    role_id: UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
```

### 5.6 Complete Model List

| Model File | Table Name | Key Features |
|------------|------------|--------------|
| `user.py` | `users` | ARRAY(auth_methods), JSONB(metadata) |
| `role.py` | `roles` | ARRAY(permissions), JSONB(conditions), FK→entities |
| `permission.py` | `permissions` | ARRAY(tags), JSONB(conditions) |
| `token.py` | `refresh_tokens` | FK→users |
| `user_role_membership.py` | `user_role_memberships` | FKs→users,roles; unique(user,role) |
| `entity.py` | `entities` | Self-ref FK(parent_id), ARRAY columns |
| `entity_membership.py` | `entity_memberships` | FKs→users,entities |
| `entity_membership.py` | `entity_membership_roles` | Junction table |
| `closure.py` | `entity_closure` | FKs→entities; unique(ancestor,descendant) |
| `api_key.py` | `api_keys` | FK→users, ARRAY(scopes, ip_whitelist) |
| `social_account.py` | `social_accounts` | FK→users, JSONB(provider_data) |
| `oauth_state.py` | `oauth_states` | FK→users (nullable) |
| `activity_metric.py` | `activity_metrics` | ARRAY(unique_user_ids) |

### 5.7 Week 2 Checklist

- [ ] Create `outlabs_auth/models/sql/` directory
- [ ] Create `enums.py` with all enum definitions
- [ ] Implement `User` model
- [ ] Implement `Role` model
- [ ] Implement `Permission` model
- [ ] Implement `RefreshToken` model
- [ ] Implement `UserRoleMembership` model
- [ ] Implement `Entity` model
- [ ] Implement `EntityMembership` model + junction table
- [ ] Implement `EntityClosure` model
- [ ] Implement `APIKey` model
- [ ] Implement `SocialAccount` model
- [ ] Implement `OAuthState` model
- [ ] Implement `ActivityMetric` model
- [ ] Keep `Condition`/`ConditionGroup` as Pydantic (stored in JSONB)
- [ ] Create `__init__.py` with all exports
- [ ] Write unit tests for model instantiation

---

## 6. Phase 3: Alembic Setup (Week 3)

### 6.1 Migrations Package Structure

**Create directory:** `outlabs_auth/migrations/`

```
outlabs_auth/migrations/
├── __init__.py
├── env.py
├── script.py.mako
└── versions/
    ├── 001_initial_core.py
    ├── 002_simple_rbac.py
    └── 003_enterprise_rbac.py
```

### 6.2 Alembic Environment

**File:** `outlabs_auth/migrations/env.py`

```python
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from sqlmodel import SQLModel

# Import all models to register them
from outlabs_auth.database.registry import ModelRegistry

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get feature flags from environment
enable_entity_hierarchy = os.getenv("OUTLABS_ENTITY_HIERARCHY", "false").lower() == "true"

# Register models
ModelRegistry.get_models(enable_entity_hierarchy=enable_entity_hierarchy)
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 6.3 CLI Commands

**File:** `outlabs_auth/cli.py`

```python
import click
import os
import pkg_resources
from alembic.config import Config
from alembic import command


@click.group()
def main():
    """OutlabsAuth CLI tools."""
    pass


@main.command()
@click.option("--database-url", envvar="DATABASE_URL", required=True)
@click.option("--entity-hierarchy/--no-entity-hierarchy", default=False)
@click.option("--revision", default="head")
def migrate(database_url: str, entity_hierarchy: bool, revision: str):
    """Run database migrations."""
    click.echo(f"Running migrations to {revision}...")

    migrations_path = pkg_resources.resource_filename("outlabs_auth", "migrations")

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", migrations_path)
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    os.environ["OUTLABS_ENTITY_HIERARCHY"] = str(entity_hierarchy).lower()

    command.upgrade(alembic_cfg, revision)
    click.echo("Migrations complete!")


@main.command()
@click.option("--database-url", envvar="DATABASE_URL", required=True)
def current(database_url: str):
    """Show current migration revision."""
    migrations_path = pkg_resources.resource_filename("outlabs_auth", "migrations")

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", migrations_path)
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    command.current(alembic_cfg)


@main.command()
@click.option("--database-url", envvar="DATABASE_URL", required=True)
def history(database_url: str):
    """Show migration history."""
    migrations_path = pkg_resources.resource_filename("outlabs_auth", "migrations")

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", migrations_path)
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    command.history(alembic_cfg, verbose=True)


if __name__ == "__main__":
    main()
```

**Add to `pyproject.toml`:**

```toml
[project.scripts]
outlabs-auth = "outlabs_auth.cli:main"
```

### 6.4 Migration Order (Foreign Key Dependencies)

1. `users` - no dependencies
2. `permissions` - no dependencies
3. `entities` - self-referential (nullable parent)
4. `roles` - FK → entities
5. `refresh_tokens` - FK → users
6. `user_role_memberships` - FK → users, roles
7. `entity_closure` - FK → entities
8. `entity_memberships` - FK → users, entities
9. `entity_membership_roles` - FK → entity_memberships, roles
10. `api_keys` - FK → users
11. `social_accounts` - FK → users
12. `oauth_states` - FK → users (nullable)
13. `activity_metrics` - no dependencies

### 6.5 Week 3 Checklist

- [ ] Create `outlabs_auth/migrations/` directory
- [ ] Implement `env.py` for async Alembic
- [ ] Create `script.py.mako` template
- [ ] Create `001_initial_core.py` migration (users, permissions, roles)
- [ ] Create `002_simple_rbac.py` migration (user_role_memberships, refresh_tokens)
- [ ] Create `003_enterprise_rbac.py` migration (entities, closure, entity_memberships)
- [ ] Create `004_supporting.py` migration (api_keys, social_accounts, oauth_states, activity_metrics)
- [ ] Implement `cli.py` with migrate/current/history commands
- [ ] Add entry point to `pyproject.toml`
- [ ] Test: `outlabs-auth migrate --database-url ...`
- [ ] Verify tables created in PostgreSQL

---

## 7. Phase 4: Service Layer Migration (Week 4)

### 7.1 Session Injection Pattern

**All services receive `AsyncSession` as first parameter:**

```python
# OLD (Beanie)
class UserService:
    async def get_user_by_id(self, user_id: str) -> Optional[UserModel]:
        return await UserModel.get(user_id)

# NEW (SQLAlchemy)
class UserService:
    async def get_user_by_id(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> Optional[User]:
        return await session.get(User, user_id)
```

### 7.2 Base Service Class

**File:** `outlabs_auth/services/base.py`

```python
from typing import TypeVar, Generic, Type, Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlmodel import SQLModel

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseService(Generic[ModelType]):
    """Base service with common CRUD operations."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get_by_id(
        self,
        session: AsyncSession,
        id: str,
        options: Optional[List[Any]] = None,
    ) -> Optional[ModelType]:
        query = select(self.model).where(self.model.id == id)
        if options:
            for opt in options:
                query = query.options(opt)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_one(
        self,
        session: AsyncSession,
        *filters,
    ) -> Optional[ModelType]:
        query = select(self.model).where(*filters)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_many(
        self,
        session: AsyncSession,
        *filters,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ModelType]:
        query = select(self.model).where(*filters).offset(skip).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        session: AsyncSession,
        *filters,
    ) -> int:
        query = select(func.count()).select_from(self.model).where(*filters)
        result = await session.execute(query)
        return result.scalar() or 0

    async def create(
        self,
        session: AsyncSession,
        obj: ModelType,
    ) -> ModelType:
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return obj

    async def delete(
        self,
        session: AsyncSession,
        obj: ModelType,
    ) -> bool:
        await session.delete(obj)
        await session.flush()
        return True
```

### 7.3 Services to Update

| Service File | Changes Required |
|--------------|------------------|
| `user.py` | Add session param to all methods, convert queries |
| `auth.py` | Add session param, update token queries |
| `role.py` | Add session param, update membership queries |
| `permission.py` | Add session param, update complex joins |
| `api_key.py` | Add session param (Redis logic unchanged) |
| `entity.py` | Add session param, closure table queries |
| `membership.py` | Add session param, update relationship loading |
| `activity_tracker.py` | Minimal changes (mostly Redis) |
| `redis_client.py` | No changes |

### 7.4 Week 4 Checklist

- [ ] Create `outlabs_auth/services/base.py` with BaseService
- [ ] Update `user.py` - all methods take session
- [ ] Update `auth.py` - all methods take session
- [ ] Update `role.py` - all methods take session
- [ ] Update `permission.py` - all methods take session
- [ ] Update `api_key.py` - all methods take session
- [ ] Update `entity.py` - all methods take session
- [ ] Update `membership.py` - all methods take session
- [ ] Update `activity_tracker.py` - minimal changes
- [ ] Write unit tests for each service
- [ ] Integration tests for cross-service operations

---

## 8. Phase 5: Core Auth Class Changes (Week 5)

### 8.1 Constructor Changes

**File:** `outlabs_auth/core/auth.py`

```python
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from outlabs_auth.database.engine import (
    DatabaseConfig,
    create_engine,
    create_session_factory,
)


class OutlabsAuth:
    def __init__(
        self,
        # NEW: PostgreSQL options
        database_url: Optional[str] = None,
        database_config: Optional[DatabaseConfig] = None,
        engine: Optional[AsyncEngine] = None,
        auto_migrate: bool = False,

        # Existing options
        secret_key: str,
        redis_url: Optional[str] = None,
        redis_enabled: bool = False,

        # Feature flags
        enable_entity_hierarchy: bool = False,
        enable_context_aware_roles: bool = False,
        enable_abac: bool = False,

        # ... other existing options
    ):
        # Database setup
        if database_url:
            config = database_config or DatabaseConfig(database_url)
            self._engine = create_engine(config)
        elif engine:
            self._engine = engine
        else:
            raise ConfigurationError("Must provide database_url or engine")

        self._session_factory = create_session_factory(self._engine)
        self._auto_migrate = auto_migrate

        # ... rest of existing init
```

### 8.2 Initialize Method

```python
async def initialize(self):
    """Initialize database and services."""
    if self._initialized:
        return

    # Run migrations if auto_migrate enabled
    if self._auto_migrate:
        await self._run_migrations()
    else:
        await self._validate_schema()

    # Initialize services (updated for SQLAlchemy)
    await self._init_services()

    self._initialized = True


async def _validate_schema(self):
    """Validate required tables exist."""
    from sqlalchemy import inspect

    async with self._engine.connect() as conn:
        def check_tables(sync_conn):
            inspector = inspect(sync_conn)
            existing = set(inspector.get_table_names())

            required = {"users", "roles", "permissions", "refresh_tokens", "api_keys"}
            if self.config.enable_entity_hierarchy:
                required.update({"entities", "entity_memberships", "entity_closure"})
            else:
                required.add("user_role_memberships")

            missing = required - existing
            if missing:
                raise ConfigurationError(
                    f"Missing tables: {missing}. "
                    f"Run 'outlabs-auth migrate' or set auto_migrate=True"
                )

        await conn.run_sync(check_tables)
```

### 8.3 Preset Updates

**File:** `outlabs_auth/presets/simple.py`

```python
class SimpleRBAC(OutlabsAuth):
    """Simple RBAC preset - flat role structure."""

    def __init__(
        self,
        database_url: str,
        secret_key: str,
        auto_migrate: bool = False,
        **kwargs,
    ):
        super().__init__(
            database_url=database_url,
            secret_key=secret_key,
            auto_migrate=auto_migrate,
            enable_entity_hierarchy=False,  # Fixed for SimpleRBAC
            **kwargs,
        )
```

**File:** `outlabs_auth/presets/enterprise.py`

```python
class EnterpriseRBAC(OutlabsAuth):
    """Enterprise RBAC preset - hierarchical entities."""

    def __init__(
        self,
        database_url: str,
        secret_key: str,
        auto_migrate: bool = False,
        enable_context_aware_roles: bool = True,
        enable_abac: bool = False,
        **kwargs,
    ):
        super().__init__(
            database_url=database_url,
            secret_key=secret_key,
            auto_migrate=auto_migrate,
            enable_entity_hierarchy=True,  # Fixed for EnterpriseRBAC
            enable_context_aware_roles=enable_context_aware_roles,
            enable_abac=enable_abac,
            **kwargs,
        )
```

### 8.4 Week 5 Checklist

- [ ] Update `OutlabsAuth.__init__()` to accept database_url
- [ ] Implement `_validate_schema()` method
- [ ] Implement `_run_migrations()` method (optional)
- [ ] Update `SimpleRBAC` preset
- [ ] Update `EnterpriseRBAC` preset
- [ ] Update all service initialization in `_init_services()`
- [ ] Update dependency injection (AuthDeps) for session management
- [ ] Integration tests with real PostgreSQL

---

## 9. Phase 6: Examples & Testing (Week 6)

### 9.1 Update SimpleRBAC Example

**File:** `examples/simple_rbac/main.py`

```python
import os
from fastapi import FastAPI, Depends
from outlabs_auth import SimpleRBAC
from outlabs_auth.dependencies import AuthDeps

# Environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_simple"
)
SECRET_KEY = os.getenv("SECRET_KEY", "simple-rbac-secret-key-change-in-production")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380")

# Initialize
app = FastAPI(title="Blog API (SimpleRBAC)")
auth = SimpleRBAC(
    database_url=DATABASE_URL,
    secret_key=SECRET_KEY,
    redis_url=REDIS_URL,
    redis_enabled=True,
    auto_migrate=True,  # For development
)
deps = AuthDeps(auth)


@app.on_event("startup")
async def startup():
    await auth.initialize()


# ... rest of routes
```

### 9.2 Update Reset Script

**File:** `examples/simple_rbac/reset_test_env.py`

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from outlabs_auth.models.sql import User, Role, Permission, UserRoleMembership

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_simple"


async def reset():
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession)

    async with async_session() as session:
        # Clear all data
        await session.execute(delete(UserRoleMembership))
        await session.execute(delete(User))
        await session.execute(delete(Role))
        await session.execute(delete(Permission))
        await session.commit()

        # Create permissions
        permissions = [
            Permission(name="user:create", display_name="Create User"),
            # ... etc
        ]
        session.add_all(permissions)

        # Create roles
        # ... etc

        await session.commit()

    await engine.dispose()
    print("Reset complete!")


if __name__ == "__main__":
    asyncio.run(reset())
```

### 9.3 Test Infrastructure

**File:** `tests/conftest.py`

```python
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlmodel import SQLModel

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()
```

### 9.4 Week 6 Checklist

- [ ] Update `examples/simple_rbac/main.py`
- [ ] Update `examples/simple_rbac/reset_test_env.py`
- [ ] Update `examples/enterprise_rbac/main.py` (if exists)
- [ ] Create `tests/conftest.py` with fixtures
- [ ] Write integration tests for auth flow
- [ ] Write integration tests for permissions
- [ ] Test with auth-ui frontend
- [ ] Remove old Beanie models (after verification)
- [ ] Update `CLAUDE.md` with new setup instructions
- [ ] Update `docs/` with PostgreSQL documentation

---

## 10. Query Pattern Reference

### Quick Reference Card

| Operation | Beanie | SQLAlchemy |
|-----------|--------|------------|
| Get by ID | `Model.get(id)` | `session.get(Model, id)` |
| Get by ID + load relations | `Model.get(id, fetch_links=True)` | `session.get(Model, id, options=[selectinload(...)])` |
| Find one | `Model.find_one(Model.field == val)` | `session.scalar(select(Model).where(Model.field == val))` |
| Find many | `Model.find(query).to_list()` | `session.execute(select(Model).where(...)).scalars().all()` |
| Find + paginate | `.skip(n).limit(m)` | `.offset(n).limit(m)` |
| Count | `Model.find(query).count()` | `session.scalar(select(func.count()).select_from(Model).where(...))` |
| Create | `obj = Model(...); await obj.save()` | `session.add(obj); await session.flush()` |
| Update | `obj.field = val; await obj.save()` | `obj.field = val; await session.flush()` |
| Delete | `await obj.delete()` | `await session.delete(obj)` |
| OR query | `{"$or": [...]}` | `or_(condition1, condition2)` |
| LIKE/regex | `{"$regex": "...", "$options": "i"}` | `Model.field.ilike("%...%")` |
| IN | `{"field": {"$in": [...]}}` | `Model.field.in_([...])` |

### Relationship Loading

```python
# Beanie
user = await UserModel.get(user_id, fetch_links=True)

# SQLAlchemy - select with eager loading
from sqlalchemy.orm import selectinload

result = await session.execute(
    select(User)
    .where(User.id == user_id)
    .options(selectinload(User.refresh_tokens))
)
user = result.scalar_one_or_none()
```

### Bulk Operations

```python
# Beanie
await Model.find(condition).update_many({"$set": {"field": value}})

# SQLAlchemy
from sqlalchemy import update

await session.execute(
    update(Model)
    .where(condition)
    .values(field=value)
)
await session.flush()
```

---

## 11. Model Schema Reference

### 11.1 Database Schema Diagram

```
┌──────────────────────┐
│       users          │
├──────────────────────┤
│ id (UUID, PK)        │
│ email (unique)       │
│ hashed_password      │
│ auth_methods[]       │
│ status               │
│ ...                  │
└──────────┬───────────┘
           │
           │ FK
           ▼
┌──────────────────────┐     ┌──────────────────────┐
│   refresh_tokens     │     │      api_keys        │
├──────────────────────┤     ├──────────────────────┤
│ id (UUID, PK)        │     │ id (UUID, PK)        │
│ user_id (FK)         │     │ owner_id (FK→users)  │
│ token_hash           │     │ prefix               │
│ expires_at           │     │ key_hash             │
│ ...                  │     │ scopes[]             │
└──────────────────────┘     └──────────────────────┘

┌──────────────────────┐     ┌──────────────────────┐
│       roles          │     │    permissions       │
├──────────────────────┤     ├──────────────────────┤
│ id (UUID, PK)        │     │ id (UUID, PK)        │
│ name                 │     │ name                 │
│ permissions[]        │     │ resource             │
│ entity_id (FK, null) │     │ action               │
│ conditions (JSONB)   │     │ tags[]               │
└──────────┬───────────┘     └──────────────────────┘
           │
           │ FK (SimpleRBAC)
           ▼
┌──────────────────────────────────────┐
│       user_role_memberships          │
├──────────────────────────────────────┤
│ id (UUID, PK)                        │
│ user_id (FK→users)                   │
│ role_id (FK→roles)                   │
│ status                               │
│ UNIQUE(user_id, role_id)             │
└──────────────────────────────────────┘

=== EnterpriseRBAC Only ===

┌──────────────────────┐
│      entities        │
├──────────────────────┤
│ id (UUID, PK)        │
│ name                 │
│ slug (unique)        │
│ entity_class         │
│ parent_id (FK→self)  │
│ ...                  │
└──────────┬───────────┘
           │
           │ FK
           ▼
┌──────────────────────┐     ┌──────────────────────┐
│   entity_closure     │     │  entity_memberships  │
├──────────────────────┤     ├──────────────────────┤
│ id (UUID, PK)        │     │ id (UUID, PK)        │
│ ancestor_id (FK)     │     │ user_id (FK→users)   │
│ descendant_id (FK)   │     │ entity_id (FK)       │
│ depth                │     │ status               │
└──────────────────────┘     └──────────┬───────────┘
                                        │
                                        │ M2M
                                        ▼
                             ┌──────────────────────────┐
                             │ entity_membership_roles  │
                             ├──────────────────────────┤
                             │ membership_id (FK, PK)   │
                             │ role_id (FK, PK)         │
                             └──────────────────────────┘
```

### 11.2 Index Summary

| Table | Indexes |
|-------|---------|
| users | email (unique), status, tenant_id |
| roles | name, is_global, entity_id, tenant_id |
| permissions | name, resource, is_system, is_active, tenant_id |
| refresh_tokens | token_hash (unique), user_id, expires_at, is_revoked |
| user_role_memberships | (user_id, role_id) unique, user_id+status, valid_until |
| entities | name, slug (unique), class+type, parent_id, status |
| entity_closure | (ancestor, descendant) unique, ancestor+depth, descendant+depth |
| entity_memberships | (user_id, entity_id) unique, user_id+status, entity_id |
| api_keys | prefix, owner_id, status, expires_at |

---

## 12. Verification Checklist

### Pre-Migration
- [ ] PostgreSQL container running on localhost:5432
- [ ] Database `outlabs_auth` created
- [ ] Test database `outlabs_auth_test` created
- [ ] Dependencies installed (`uv sync`)

### Phase 1 Complete
- [ ] `outlabs_auth/database/` module exists
- [ ] Engine connects to PostgreSQL
- [ ] BaseModel class defined

### Phase 2 Complete
- [ ] All 13 model files created
- [ ] Model unit tests pass
- [ ] Type hints complete

### Phase 3 Complete
- [ ] Alembic migrations run successfully
- [ ] All tables created
- [ ] CLI commands work (`outlabs-auth migrate`)

### Phase 4 Complete
- [ ] All services updated with session param
- [ ] Service unit tests pass
- [ ] No Beanie imports in services

### Phase 5 Complete
- [ ] OutlabsAuth accepts database_url
- [ ] SimpleRBAC/EnterpriseRBAC presets work
- [ ] Integration tests pass

### Phase 6 Complete
- [ ] Examples run with PostgreSQL
- [ ] auth-ui works with new backend
- [ ] Old Beanie models removed
- [ ] Documentation updated

### Final Verification
- [ ] Full auth flow: register → login → access protected route
- [ ] Role assignment and permission check
- [ ] API key creation and validation
- [ ] Entity hierarchy (EnterpriseRBAC)
- [ ] Redis caching still works
- [ ] All existing tests pass

---

## Appendix A: Troubleshooting

### Connection Issues
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Test connection
docker exec -it postgres psql -U postgres -c "SELECT 1"

# Check database exists
docker exec -it postgres psql -U postgres -c "\l" | grep outlabs_auth
```

### Migration Issues
```bash
# Check current revision
outlabs-auth current --database-url "postgresql://..."

# View migration history
outlabs-auth history --database-url "postgresql://..."

# Manual table check
docker exec -it postgres psql -U postgres -d outlabs_auth -c "\dt"
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `relation "users" does not exist` | Migrations not run | `outlabs-auth migrate` |
| `duplicate key value violates unique constraint` | Email/slug collision | Check for existing data |
| `connection refused` | PostgreSQL not running | `docker start postgres` |
| `FATAL: database "outlabs_auth" does not exist` | Database not created | Create with `CREATE DATABASE` |

---

## Appendix B: Quick Start (Copy-Paste)

```bash
# 1. Create database
docker exec -it postgres psql -U postgres -c "CREATE DATABASE outlabs_auth;"

# 2. Install dependencies
cd /Users/macbookm3/Documents/projects/outlabsAuth
uv sync

# 3. Run migrations
outlabs-auth migrate --database-url "postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth"

# 4. Start example
cd examples/simple_rbac
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth" \
SECRET_KEY="dev-secret" \
uv run uvicorn main:app --port 8003 --reload

# 5. Start auth-ui
cd auth-ui
bun run dev
```

---

*Last Updated: January 2026*
*Migration Plan Version: 1.0*
