# OutlabsAuth Library - Technical Architecture

**Version**: 1.2
**Date**: 2025-01-14
**Status**: Design Phase

---

## Table of Contents

1. [Overview](#overview)
2. [Package Structure](#package-structure)
3. [Preset Architecture](#preset-architecture)
4. [Data Models](#data-models)
5. [Service Layer](#service-layer)
6. [Authentication Extensions (v1.1-v1.4, Optional)](#authentication-extensions-v11-v14-optional)
7. [Dependency Injection](#dependency-injection)
8. [Configuration System](#configuration-system)
9. [Testing Strategy](#testing-strategy)

---

## Overview

OutlabsAuth is structured as a modular Python library with two preset configurations:

```
Simple RBAC (Core)
    ↓
Enterprise RBAC (+ Entity System + Optional Advanced Features)
```

**Simple vs Enterprise Decision**: Do you have departments/teams/hierarchy?
- **NO** → SimpleRBAC (flat structure, single role per user)
- **YES** → EnterpriseRBAC (entity hierarchy + optional features via flags)

Each preset is a fully functional auth system that can be used independently.

---

## Package Structure

```
outlabs_auth/
├── __init__.py                 # Public API exports
├── core/
│   ├── __init__.py
│   ├── base.py                 # Base OutlabsAuth class
│   ├── config.py               # Configuration management
│   └── exceptions.py           # Custom exceptions
├── models/
│   ├── __init__.py
│   ├── base.py                 # BaseDocument
│   ├── user.py                 # UserModel
│   ├── role.py                 # RoleModel
│   ├── permission.py           # PermissionModel
│   ├── entity.py               # EntityModel
│   ├── membership.py           # EntityMembershipModel
│   └── token.py                # RefreshTokenModel
├── services/
│   ├── __init__.py
│   ├── auth.py                 # AuthService
│   ├── user.py                 # UserService
│   ├── role.py                 # RoleService
│   ├── permission.py           # PermissionService
│   ├── entity.py               # EntityService (enterprise only)
│   └── membership.py           # MembershipService (enterprise only)
├── presets/
│   ├── __init__.py
│   ├── simple.py               # SimpleRBAC preset
│   └── enterprise.py           # EnterpriseRBAC preset
├── dependencies/
│   ├── __init__.py
│   ├── auth.py                 # FastAPI auth dependencies
│   ├── permissions.py          # Permission checking dependencies
│   └── entities.py             # Entity context dependencies (enterprise only)
├── middleware/
│   ├── __init__.py
│   ├── auth.py                 # JWT middleware
│   └── tenant.py               # Multi-tenant middleware (optional)
├── utils/
│   ├── __init__.py
│   ├── password.py             # Password hashing
│   ├── jwt.py                  # JWT utilities
│   └── validation.py           # Input validation
└── schemas/
    ├── __init__.py
    ├── auth.py                 # Auth request/response schemas
    ├── user.py                 # User schemas
    ├── role.py                 # Role schemas
    ├── permission.py           # Permission schemas
    └── entity.py               # Entity schemas (enterprise only)

examples/                       # Example applications
├── simple_app/
├── enterprise_app/             # EnterpriseRBAC with various configurations
└── migration_example/

tests/                          # Comprehensive test suite
├── unit/
├── integration/
└── examples/
```

---

## Preset Architecture

### Base Class: `OutlabsAuth`

All presets inherit from a base class that provides core functionality:

```python
class OutlabsAuth:
    """Base class for all OutlabsAuth presets"""

    def __init__(
        self,
        database: Any,
        config: Optional[AuthConfig] = None,
        user_model: Type[UserModel] = UserModel,
        role_model: Type[RoleModel] = RoleModel,
        permission_model: Type[PermissionModel] = PermissionModel,
    ):
        self.database = database
        self.config = config or AuthConfig()

        # Models
        self.user_model = user_model
        self.role_model = role_model
        self.permission_model = permission_model

        # Services (initialized in subclasses)
        self.auth_service: Optional[AuthService] = None
        self.user_service: Optional[UserService] = None
        self.role_service: Optional[RoleService] = None
        self.permission_service: Optional[PermissionService] = None

    # Core dependency methods (implemented in subclasses)
    async def get_current_user(self, token: str) -> UserModel:
        raise NotImplementedError

    def require_permission(self, permission: str):
        raise NotImplementedError

    # Utility methods
    async def initialize(self):
        """Initialize database collections/tables"""
        raise NotImplementedError
```

### Preset 1: SimpleRBAC

**Purpose**: Basic role-based access control without entity hierarchy.

**Features**:
- User management
- Role assignment (single role per user)
- Flat permission system
- JWT authentication

**Models Used**:
- UserModel
- RoleModel
- PermissionModel
- RefreshTokenModel

**Services**:
- AuthService
- UserService
- RoleService
- PermissionService (basic)

**Example**:
```python
from outlabs_auth import SimpleRBAC

auth = SimpleRBAC(database=mongo_client)

# Initialize database
await auth.initialize()

# Use in routes
@app.get("/users/me")
async def get_me(user = Depends(auth.get_current_user)):
    return user

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    user = Depends(auth.require_permission("user:delete"))
):
    return await auth.user_service.delete_user(user_id)
```

**Implementation**:
```python
class SimpleRBAC(OutlabsAuth):
    """Simple role-based access control"""

    def __init__(self, database: Any, config: Optional[SimpleConfig] = None):
        super().__init__(database, config)

        # Initialize services
        self.auth_service = AuthService(database, self.user_model)
        self.user_service = UserService(database, self.user_model)
        self.role_service = RoleService(database, self.role_model)
        self.permission_service = BasicPermissionService(
            database, self.permission_model
        )

    async def get_current_user(self, token: str = Depends(oauth2_scheme)):
        """Get current authenticated user"""
        return await self.auth_service.get_current_user(token)

    def require_permission(self, permission: str):
        """Dependency that requires a specific permission"""
        async def _check_permission(
            user: UserModel = Depends(self.get_current_user)
        ):
            has_perm = await self.permission_service.check_permission(
                user.id, permission
            )
            if not has_perm:
                raise HTTPException(403, f"Permission denied: {permission}")
            return user

        return Depends(_check_permission)
```

### Preset 2: EnterpriseRBAC

**Purpose**: Full-featured auth system with entity hierarchy and optional advanced features.

**Core Features** (Always Included):
- Everything from SimpleRBAC
- Entity hierarchy (organizational structure)
- Multiple roles per user (via entity memberships)
- Tree permissions (`resource:action_tree`)
- Entity context in permission checks

**Optional Features** (Opt-in via flags):
- Context-aware roles (permissions vary by entity type) - `enable_context_aware_roles=True`
- ABAC conditions (attribute-based access control) - `enable_abac=True`
- Permission caching (Redis) - `enable_caching=True` (requires `redis_url`)
- Multi-tenant support - `multi_tenant=True`
- Advanced audit logging - `enable_audit_log=True`

**Models Used**:
- All SimpleRBAC models
- EntityModel
- EntityMembershipModel

**Services**:
- All SimpleRBAC services
- EntityService
- MembershipService
- EnterprisePermissionService (with ABAC and caching support)

**Example - Basic Configuration** (entity hierarchy only):
```python
from outlabs_auth import EnterpriseRBAC

# Minimal configuration - just entity hierarchy
auth = EnterpriseRBAC(database=mongo_client)

# Create entity hierarchy
org = await auth.entity_service.create_entity(
    name="my_org",
    entity_class="structural",
    entity_type="organization"
)

dept = await auth.entity_service.create_entity(
    name="engineering",
    entity_class="structural",
    entity_type="department",
    parent_id=org.id
)

# Assign user to entity with multiple roles
await auth.membership_service.add_member(
    entity_id=dept.id,
    user_id=user.id,
    role_ids=[manager_role.id, developer_role.id]
)
```

**Example - Full Configuration** (all optional features enabled):
```python
from outlabs_auth import EnterpriseRBAC

# Full configuration with all optional features
auth = EnterpriseRBAC(
    database=mongo_client,
    redis_url="redis://localhost:6379",
    enable_context_aware_roles=True,  # Opt-in
    enable_abac=True,                 # Opt-in
    enable_caching=True,              # Opt-in (requires Redis)
    multi_tenant=True,                # Opt-in
    enable_audit_log=True             # Opt-in
)

# Context-aware role
regional_manager = await auth.role_service.create_role(
    name="regional_manager",
    permissions=["entity:read", "user:read"],  # Default
    entity_type_permissions={
        "region": [
            "entity:manage_tree",
            "user:manage_tree",
            "budget:approve"
        ],
        "office": ["entity:read", "user:read"],
        "team": ["entity:read"]
    }
)

# ABAC permission with conditions
invoice_approval = await auth.permission_service.create_permission(
    name="invoice:approve",
    conditions=[
        {
            "attribute": "resource.value",
            "operator": "LESS_THAN_OR_EQUAL",
            "value": 50000
        }
    ]
)

# Check with ABAC
result = await auth.permission_service.check_permission_with_context(
    user_id=user.id,
    permission="invoice:approve",
    entity_id=entity.id,
    resource_attributes={"value": 35000}
)
```

---

## Data Models

### Core Models (All Presets)

#### UserModel
```python
class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"
    TERMINATED = "terminated"

class UserModel(BaseDocument):
    # Authentication
    email: EmailStr
    hashed_password: str

    # Profile
    profile: UserProfile

    # Status
    status: UserStatus = UserStatus.ACTIVE
    is_system_user: bool = False
    email_verified: bool = False

    # Security
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
```

#### RoleModel
```python
class RoleModel(BaseDocument):
    # Identity
    name: str
    display_name: str
    description: Optional[str] = None

    # Permissions (default for all contexts)
    permissions: List[str] = Field(default_factory=list)

    # Context-aware permissions (EnterpriseRBAC only - optional feature)
    entity_type_permissions: Optional[Dict[str, List[str]]] = None

    # Configuration
    is_system_role: bool = False
```

#### PermissionModel
```python
class PermissionModel(BaseDocument):
    # Identity
    name: str  # e.g., "user:create"
    display_name: str
    description: str

    # Structure (auto-parsed from name)
    resource: str  # "user"
    action: str    # "create"

    # ABAC conditions (EnterpriseRBAC only - optional feature)
    conditions: List[Condition] = Field(default_factory=list)

    # Status
    is_active: bool = True
```

### Enterprise Models (EnterpriseRBAC only)

#### EntityModel
```python
class EntityClass(str, Enum):
    STRUCTURAL = "structural"      # Organizational hierarchy
    ACCESS_GROUP = "access_group"  # Cross-cutting groups

class EntityModel(BaseDocument):
    # Identity
    name: str
    display_name: str
    slug: str
    description: Optional[str] = None

    # Classification
    entity_class: EntityClass
    entity_type: str  # Flexible: "department", "team", etc.

    # Hierarchy
    parent_entity: Optional[Link["EntityModel"]] = None

    # Optional: Multi-tenant support
    tenant_id: Optional[str] = None

    # Status
    status: str = "active"
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Direct permissions (optional)
    direct_permissions: List[str] = Field(default_factory=list)

    # Configuration
    allowed_child_classes: List[EntityClass] = []
    allowed_child_types: List[str] = []
    max_members: Optional[int] = None
```

#### EntityMembershipModel
```python
class EntityMembershipModel(BaseDocument):
    """User's membership in an entity with roles"""

    user: Link[UserModel]
    entity: Link[EntityModel]

    # Multiple roles per membership
    roles: List[Link[RoleModel]] = Field(default_factory=list)

    # Time-based membership
    joined_at: datetime
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Status
    is_active: bool = True
```

### Model Changes from Current System

#### Removed Fields
- ❌ `platform_id` (no longer needed)
- ❌ Platform-specific isolation logic

#### Added Fields
- ✅ `tenant_id` (optional, for multi-tenant mode)

#### Preserved Fields
- ✅ All entity hierarchy logic
- ✅ Tree permission support
- ✅ Context-aware role support
- ✅ Time-based validity

---

## Service Layer

### AuthService
```python
class AuthService:
    """Handles authentication logic"""

    async def login(self, email: str, password: str) -> TokenPair:
        """Authenticate user and return tokens"""
        pass

    async def logout(self, refresh_token: str) -> None:
        """Revoke refresh token"""
        pass

    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """Get new access token using refresh token"""
        pass

    async def get_current_user(self, token: str) -> UserModel:
        """Validate JWT and return user"""
        pass
```

### PermissionService

#### BasicPermissionService (Simple preset)
```python
class BasicPermissionService:
    """Simple permission checking without hierarchy"""

    async def check_permission(
        self,
        user_id: str,
        permission: str
    ) -> bool:
        """Check if user has permission"""
        # Get user's role
        # Check if role has permission
        pass

    async def get_user_permissions(self, user_id: str) -> List[str]:
        """Get all permissions for user"""
        pass
```

#### EnterprisePermissionService (EnterpriseRBAC)
```python
class EnterprisePermissionService(BasicPermissionService):
    """Permission checking with entity hierarchy and tree permissions"""

    async def check_permission(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check permission with entity context.
        Returns (has_permission, source)

        Handles:
        - Direct permissions in entity
        - Tree permissions from parent entities
        - Platform-wide permissions (_all suffix)
        """
        pass

    async def check_tree_permission(
        self,
        user_id: str,
        permission: str,
        target_entity_id: str
    ) -> bool:
        """
        Check if user has tree permission in any parent entity.
        Example: entity:update_tree in parent allows updating children.
        """
        pass

    async def check_permission_with_context(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None,
        resource_attributes: Optional[Dict[str, Any]] = None
    ) -> PolicyResult:
        """
        Full RBAC + ReBAC + ABAC evaluation (when ABAC enabled).

        Steps:
        1. Check RBAC (does user have permission in role?)
        2. Check ReBAC (is entity relationship valid?)
        3. Check ABAC (do conditions pass?) - only if enable_abac=True

        Note: Caching automatically applied when enable_caching=True
        """
        pass
```

### EntityService (EnterpriseRBAC only)
```python
class EntityService:
    """Entity hierarchy management"""

    async def create_entity(
        self,
        name: str,
        entity_class: str,
        entity_type: str,
        parent_id: Optional[str] = None,
        **kwargs
    ) -> EntityModel:
        """Create new entity"""
        # Validate entity type
        # Check circular hierarchy
        # Validate parent relationship
        pass

    async def get_entity_path(self, entity_id: str) -> List[EntityModel]:
        """Get path from root to entity"""
        pass

    async def get_descendants(
        self,
        entity_id: str,
        entity_type: Optional[str] = None
    ) -> List[EntityModel]:
        """Get all descendants of entity"""
        pass
```

---

## Authentication Extensions (v1.1-v1.4, Optional)

**Status**: Post-v1.0 features
**Timeline**: Weeks 8-16 (9 weeks total)
**Compatibility**: Work with both SimpleRBAC and EnterpriseRBAC

### Overview

Authentication extensions add modern auth capabilities beyond password-based authentication. All extensions are **optional** and can be adopted independently based on application needs.

**Extension Phases**:
- **v1.1 (Week 8-9)**: Notification system (prerequisite)
- **v1.2 (Week 10-12)**: OAuth/social login
- **v1.3 (Week 13-14)**: Passwordless authentication
- **v1.4 (Week 15-16)**: Advanced features (MFA, WebAuthn)

### Extension 1: Notification Handler Abstraction (v1.1)

**Purpose**: Pluggable system for sending auth-related notifications without vendor lock-in.

#### NotificationHandler Interface
```python
class NotificationEvent(BaseModel):
    """Event emitted when notification needs to be sent"""
    type: str  # "welcome", "magic_link", "otp", "password_reset", etc.
    recipient: str  # Email or phone number
    data: Dict[str, Any]  # Event-specific payload
    metadata: Optional[Dict[str, Any]] = None

class NotificationHandler(ABC):
    """Abstract base class for notification handlers"""

    @abstractmethod
    async def send(self, event: NotificationEvent) -> bool:
        """
        Send notification event.
        Returns True if sent successfully, False otherwise.
        """
        pass
```

#### Pre-built Handlers
```python
# Default handler (logs but doesn't send)
class NoOpHandler(NotificationHandler):
    async def send(self, event: NotificationEvent) -> bool:
        logger.info(f"Notification event: {event.type} to {event.recipient}")
        return True

# Webhook handler (send to HTTP endpoint)
class WebhookHandler(NotificationHandler):
    def __init__(self, webhook_url: str, headers: Optional[Dict] = None):
        self.webhook_url = webhook_url
        self.headers = headers or {}

    async def send(self, event: NotificationEvent) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_url,
                json=event.dict(),
                headers=self.headers
            )
            return response.status_code == 200

# Queue handler (push to message queue)
class QueueHandler(NotificationHandler):
    def __init__(self, queue_client: Any, queue_name: str):
        self.queue_client = queue_client
        self.queue_name = queue_name

    async def send(self, event: NotificationEvent) -> bool:
        await self.queue_client.send_message(
            self.queue_name,
            event.json()
        )
        return True

# Callback handler (direct function call)
class CallbackHandler(NotificationHandler):
    def __init__(self, callback: Callable[[NotificationEvent], Awaitable[bool]]):
        self.callback = callback

    async def send(self, event: NotificationEvent) -> bool:
        return await self.callback(event)

# Composite handler (combine multiple handlers)
class CompositeHandler(NotificationHandler):
    def __init__(self, handlers: List[NotificationHandler], parallel: bool = True):
        self.handlers = handlers
        self.parallel = parallel

    async def send(self, event: NotificationEvent) -> bool:
        if self.parallel:
            results = await asyncio.gather(
                *[h.send(event) for h in self.handlers],
                return_exceptions=True
            )
            return all(r is True for r in results if not isinstance(r, Exception))
        else:
            for handler in self.handlers:
                if not await handler.send(event):
                    return False
            return True
```

#### Usage Example
```python
# Configure notification handler
notification_handler = WebhookHandler(
    webhook_url="https://api.internal/notifications",
    headers={"X-API-Key": os.getenv("NOTIFICATION_API_KEY")}
)

auth = SimpleRBAC(
    database=mongo_client,
    notification_handler=notification_handler
)

# Notification is sent automatically
await auth.user_service.send_welcome_email(user)
```

### Extension 2: OAuth/Social Login (v1.2)

**Purpose**: Enable "Login with Google/Facebook/Apple" functionality.
**Requires**: Notification system (v1.1) for welcome emails

#### OAuth Provider Interface
```python
class OAuthToken(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None

class OAuthUserInfo(BaseModel):
    provider_user_id: str
    email: Optional[EmailStr] = None
    email_verified: bool = False
    name: Optional[str] = None
    picture: Optional[str] = None
    profile_data: Optional[Dict[str, Any]] = None

class OAuthProvider(ABC):
    """Abstract base class for OAuth providers"""

    @abstractmethod
    def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        scopes: Optional[List[str]] = None
    ) -> str:
        """Generate OAuth authorization URL"""
        pass

    @abstractmethod
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str
    ) -> OAuthToken:
        """Exchange authorization code for tokens"""
        pass

    @abstractmethod
    async def get_user_info(self, token: OAuthToken) -> OAuthUserInfo:
        """Get user information from provider"""
        pass
```

#### New Models
```python
class AuthMethod(str, Enum):
    PASSWORD = "password"
    GOOGLE = "google"
    FACEBOOK = "facebook"
    APPLE = "apple"
    GITHUB = "github"
    MICROSOFT = "microsoft"
    MAGIC_LINK = "magic_link"
    SMS_OTP = "sms_otp"
    EMAIL_OTP = "email_otp"
    TOTP = "totp"

class SocialAccountModel(BaseDocument):
    """Social account linked to user"""
    user: Link[UserModel]
    provider: str  # "google", "facebook", "apple", etc.
    provider_user_id: str
    email: Optional[EmailStr] = None
    email_verified: bool = False
    profile_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

class UserModel(BaseDocument):
    # ... existing fields ...
    hashed_password: Optional[str] = None  # Optional now
    auth_methods: List[AuthMethod] = Field(default_factory=lambda: [AuthMethod.PASSWORD])
    phone_number: Optional[str] = None  # For SMS OTP
```

#### OAuth Service
```python
class OAuthService:
    """OAuth authentication service"""

    async def get_authorization_url(
        self,
        provider: str,
        redirect_uri: str
    ) -> str:
        """Generate OAuth authorization URL with state validation"""
        pass

    async def authenticate_with_provider(
        self,
        provider: str,
        code: str,
        redirect_uri: str,
        auto_link_by_email: bool = True
    ) -> Tuple[UserModel, TokenPair, bool]:
        """
        Authenticate user with OAuth provider.
        Returns (user, tokens, is_new_user)

        Rules:
        - If social email is verified: auto-link to existing user
        - If social email is unverified: create separate account
        - If no existing user: create new user
        """
        pass

    async def link_provider_to_user(
        self,
        user_id: str,
        provider: str,
        code: str,
        redirect_uri: str
    ) -> SocialAccountModel:
        """Link social account to existing user"""
        pass

    async def unlink_provider(
        self,
        user_id: str,
        provider: str
    ) -> None:
        """Unlink social account (must have alternative auth method)"""
        pass
```

#### Usage Example
```python
oauth_providers = {
    "google": GoogleProvider(
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    ),
    "facebook": FacebookProvider(
        client_id=os.getenv("FACEBOOK_CLIENT_ID"),
        client_secret=os.getenv("FACEBOOK_CLIENT_SECRET")
    )
}

auth = SimpleRBAC(
    database=mongo_client,
    notification_handler=notification_handler,
    oauth_providers=oauth_providers
)

# Get authorization URL
auth_url = await auth.oauth_service.get_authorization_url(
    provider="google",
    redirect_uri="https://myapp.com/auth/callback"
)

# Handle callback
user, tokens, is_new = await auth.oauth_service.authenticate_with_provider(
    provider="google",
    code=request.query_params["code"],
    redirect_uri="https://myapp.com/auth/callback"
)
```

### Extension 3: Passwordless Authentication (v1.3)

**Purpose**: Magic links and OTP-based authentication.
**Requires**: Notification system (v1.1) for sending links/codes

#### Challenge Management
```python
class ChallengeType(str, Enum):
    MAGIC_LINK = "magic_link"
    EMAIL_OTP = "email_otp"
    SMS_OTP = "sms_otp"
    WHATSAPP_OTP = "whatsapp_otp"
    TELEGRAM_OTP = "telegram_otp"

class AuthenticationChallengeModel(BaseDocument):
    """Temporary authentication challenge"""
    challenge_type: ChallengeType
    recipient: str  # Email or phone
    code: str  # Magic link token or OTP
    user_id: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    expires_at: datetime
    created_at: datetime
```

#### Passwordless Service
```python
class PasswordlessService:
    """Passwordless authentication service"""

    # Magic Links
    async def send_magic_link(
        self,
        email: EmailStr,
        create_user_if_not_exists: bool = False
    ) -> None:
        """
        Generate magic link and send via notification handler.
        Magic link expires in 15 minutes.
        """
        pass

    async def verify_magic_link(
        self,
        code: str
    ) -> TokenPair:
        """Verify magic link and return JWT tokens"""
        pass

    # OTP
    async def send_otp(
        self,
        recipient: str,
        channel: str = "email",  # "email", "sms", "whatsapp", "telegram"
        create_user_if_not_exists: bool = False
    ) -> None:
        """
        Generate 6-digit OTP and send via notification handler.
        OTP expires in 5 minutes.
        """
        pass

    async def verify_otp(
        self,
        recipient: str,
        code: str
    ) -> TokenPair:
        """Verify OTP code and return JWT tokens"""
        pass
```

#### Usage Example
```python
auth = SimpleRBAC(
    database=mongo_client,
    notification_handler=notification_handler
)

# Magic link
await auth.passwordless_service.send_magic_link("user@example.com")
tokens = await auth.passwordless_service.verify_magic_link(code)

# SMS OTP
await auth.passwordless_service.send_otp("+1234567890", channel="sms")
tokens = await auth.passwordless_service.verify_otp("+1234567890", "123456")
```

### Extension 4: Advanced Features (v1.4)

**Purpose**: MFA, TOTP, extended OTP channels, and WebAuthn research.

#### TOTP/MFA
```python
class MFAMethodModel(BaseDocument):
    """Multi-factor authentication method"""
    user: Link[UserModel]
    method_type: str  # "totp", "sms", "email"
    totp_secret: Optional[str] = None  # For authenticator apps
    is_primary: bool = False
    created_at: datetime
    last_used_at: Optional[datetime] = None

class MFAService:
    """Multi-factor authentication service"""

    async def enable_totp(self, user_id: str) -> Tuple[str, str]:
        """
        Enable TOTP for user.
        Returns (secret, qr_code_uri)
        """
        pass

    async def verify_totp(self, user_id: str, code: str) -> bool:
        """Verify TOTP code from authenticator app"""
        pass

    async def generate_backup_codes(self, user_id: str) -> List[str]:
        """Generate recovery codes for lost authenticator"""
        pass

    async def require_mfa(self, user_id: str) -> None:
        """Enforce MFA for user"""
        pass
```

### Package Structure Changes (Extensions)

```python
outlabs_auth/
├── extensions/                  # NEW: Extension modules
│   ├── __init__.py
│   ├── notifications/
│   │   ├── __init__.py
│   │   ├── base.py             # NotificationHandler ABC
│   │   ├── webhook.py          # WebhookHandler
│   │   ├── queue.py            # QueueHandler
│   │   └── callback.py         # CallbackHandler
│   ├── oauth/
│   │   ├── __init__.py
│   │   ├── base.py             # OAuthProvider ABC
│   │   ├── google.py           # GoogleProvider
│   │   ├── facebook.py         # FacebookProvider
│   │   └── apple.py            # AppleProvider
│   ├── passwordless/
│   │   ├── __init__.py
│   │   ├── service.py          # PasswordlessService
│   │   └── challenge.py        # Challenge management
│   └── mfa/
│       ├── __init__.py
│       ├── service.py          # MFAService
│       └── totp.py             # TOTP implementation
├── models/
│   ├── social_account.py       # NEW
│   ├── auth_challenge.py       # NEW
│   └── mfa_method.py           # NEW
└── services/
    ├── oauth.py                # NEW
    ├── passwordless.py         # NEW
    └── mfa.py                  # NEW
```

### Configuration Changes

```python
class SimpleConfig(AuthConfig):
    """Configuration with optional extensions"""

    # Notification system (v1.1)
    notification_handler: Optional[NotificationHandler] = None

    # OAuth providers (v1.2)
    oauth_providers: Optional[Dict[str, OAuthProvider]] = None

    # Passwordless (v1.3)
    enable_magic_links: bool = False
    enable_otp: bool = False
    magic_link_expire_minutes: int = 15
    otp_expire_minutes: int = 5

    # MFA (v1.4)
    enable_mfa: bool = False
    mfa_required_for_users: List[str] = Field(default_factory=list)
```

### Extension Integration Example

```python
from outlabs_auth import SimpleRBAC
from outlabs_auth.extensions.notifications import WebhookHandler
from outlabs_auth.extensions.oauth import GoogleProvider, FacebookProvider

# Full configuration with all extensions
notification_handler = WebhookHandler(
    webhook_url="https://api.internal/notifications",
    headers={"X-API-Key": os.getenv("API_KEY")}
)

oauth_providers = {
    "google": GoogleProvider(
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
    ),
    "facebook": FacebookProvider(
        client_id=os.getenv("FACEBOOK_CLIENT_ID"),
        client_secret=os.getenv("FACEBOOK_CLIENT_SECRET")
    )
}

auth = SimpleRBAC(
    database=mongo_client,
    notification_handler=notification_handler,
    oauth_providers=oauth_providers,
    enable_magic_links=True,
    enable_otp=True,
    enable_mfa=True
)

# All auth methods now available:
# 1. Password (built-in)
tokens = await auth.auth_service.login("user@example.com", "password")

# 2. OAuth (v1.2)
tokens = await auth.oauth_service.authenticate_with_provider("google", code, redirect_uri)

# 3. Magic link (v1.3)
await auth.passwordless_service.send_magic_link("user@example.com")
tokens = await auth.passwordless_service.verify_magic_link(code)

# 4. OTP (v1.3)
await auth.passwordless_service.send_otp("+1234567890", channel="sms")
tokens = await auth.passwordless_service.verify_otp("+1234567890", "123456")

# 5. TOTP/MFA (v1.4)
secret, qr_code = await auth.mfa_service.enable_totp(user.id)
is_valid = await auth.mfa_service.verify_totp(user.id, totp_code)
```

### Key Design Principles

1. **Optional**: All extensions are opt-in
2. **Independent**: Extensions can be adopted separately
3. **Compatible**: Work with both SimpleRBAC and EnterpriseRBAC
4. **No Vendor Lock-in**: Use pluggable abstractions (notification handlers, OAuth providers)
5. **Security First**: Rate limiting, expiration, state validation built-in
6. **Documented**: Comprehensive guides in AUTH_EXTENSIONS.md and SECURITY.md

### Testing Extensions

```python
# Test notification handler
async def test_webhook_handler():
    handler = WebhookHandler("https://webhook.site/...")
    event = NotificationEvent(
        type="welcome",
        recipient="test@example.com",
        data={"name": "Test User"}
    )
    assert await handler.send(event) is True

# Test OAuth flow
async def test_google_oauth(auth_with_oauth):
    # Mock OAuth provider
    auth_url = await auth_with_oauth.oauth_service.get_authorization_url(
        "google", "http://localhost/callback"
    )
    assert "accounts.google.com" in auth_url

# Test magic link
async def test_magic_link(auth_with_notifications):
    await auth_with_notifications.passwordless_service.send_magic_link("test@example.com")
    # Verify notification was sent
    # Verify challenge created in database
```

---

## Dependency Injection

FastAPI dependencies for common patterns:

### Authentication Dependencies
```python
# outlabs_auth/dependencies/auth.py

def get_current_user(auth: OutlabsAuth):
    """Dependency factory for getting current user"""
    async def _get_current_user(
        token: str = Depends(oauth2_scheme)
    ) -> UserModel:
        return await auth.get_current_user(token)
    return _get_current_user

def require_active_user(auth: OutlabsAuth):
    """Require active user status"""
    async def _check_active(
        user: UserModel = Depends(get_current_user(auth))
    ) -> UserModel:
        if user.status != UserStatus.ACTIVE:
            raise HTTPException(403, "User account is not active")
        return user
    return _check_active
```

### Permission Dependencies
```python
# outlabs_auth/dependencies/permissions.py

def require_permission(auth: OutlabsAuth, permission: str):
    """Dependency factory for permission checks"""
    async def _check_permission(
        user: UserModel = Depends(get_current_user(auth))
    ) -> UserModel:
        has_perm = await auth.permission_service.check_permission(
            user.id, permission
        )
        if not has_perm:
            raise HTTPException(403, f"Permission denied: {permission}")
        return user
    return _check_permission

def require_any_permission(auth: OutlabsAuth, permissions: List[str]):
    """Require at least one of the permissions"""
    async def _check_any(
        user: UserModel = Depends(get_current_user(auth))
    ) -> UserModel:
        for perm in permissions:
            has_perm = await auth.permission_service.check_permission(
                user.id, perm
            )
            if has_perm:
                return user
        raise HTTPException(
            403,
            f"Permission denied: requires one of {permissions}"
        )
    return _check_any
```

### Entity Context Dependencies (EnterpriseRBAC only)
```python
# outlabs_auth/dependencies/entities.py

def require_entity_permission(
    auth: EnterpriseRBAC,
    permission: str,
    entity_param: str = "entity_id"
):
    """
    Check permission within entity context from path parameter.

    Example:
    @app.get("/entities/{entity_id}/members")
    async def get_members(
        entity_id: str,
        user = Depends(require_entity_permission(auth, "member:read", "entity_id"))
    ):
        pass
    """
    async def _check_entity_permission(
        user: UserModel = Depends(get_current_user(auth)),
        # Entity ID extracted from path
        **kwargs
    ) -> UserModel:
        entity_id = kwargs.get(entity_param)
        if not entity_id:
            raise HTTPException(400, f"Missing {entity_param}")

        has_perm = await auth.permission_service.check_permission(
            user.id, permission, entity_id
        )
        if not has_perm:
            raise HTTPException(
                403,
                f"Permission denied: {permission} in entity {entity_id}"
            )
        return user

    return _check_entity_permission
```

---

## Configuration System

### Base Configuration
```python
class AuthConfig(BaseModel):
    """Base configuration for all presets"""

    # JWT settings
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Password settings
    password_min_length: int = 8
    require_special_char: bool = True
    require_uppercase: bool = True
    require_digit: bool = True

    # Security
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 30
```

### Preset-Specific Configs
```python
class SimpleConfig(AuthConfig):
    """Configuration for SimpleRBAC"""

    # Simple mode has no additional config
    pass

class EnterpriseConfig(AuthConfig):
    """Configuration for EnterpriseRBAC"""

    # Entity settings (always enabled)
    max_entity_depth: int = 5
    allowed_entity_types: Optional[List[str]] = None
    allow_access_groups: bool = True

    # Optional features (opt-in)
    enable_context_aware_roles: bool = False
    enable_abac: bool = False
    enable_caching: bool = False
    enable_audit_log: bool = False
    multi_tenant: bool = False

    # Caching settings (only used when enable_caching=True)
    redis_url: Optional[str] = None
    cache_ttl_seconds: int = 300
```

---

## Testing Strategy

### Unit Tests
```python
# Test each service independently
tests/unit/services/test_auth_service.py
tests/unit/services/test_permission_service.py
tests/unit/services/test_entity_service.py

# Test models
tests/unit/models/test_user_model.py
tests/unit/models/test_entity_model.py

# Test utilities
tests/unit/utils/test_jwt.py
tests/unit/utils/test_password.py
```

### Integration Tests
```python
# Test preset configurations
tests/integration/test_simple_rbac.py
tests/integration/test_enterprise_rbac.py

# Test complex scenarios
tests/integration/test_tree_permissions.py
tests/integration/test_context_aware_roles.py
tests/integration/test_abac_conditions.py
tests/integration/test_multi_tenant.py
```

### Example Tests
```python
# Test example applications work
tests/examples/test_simple_app.py
tests/examples/test_enterprise_app.py
```

### Test Fixtures
```python
@pytest.fixture
async def mongo_db():
    """Test database connection"""
    client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_outlabs_auth"]
    yield db
    await client.drop_database("test_outlabs_auth")

@pytest.fixture
async def simple_auth(mongo_db):
    """SimpleRBAC instance for testing"""
    auth = SimpleRBAC(database=mongo_db)
    await auth.initialize()
    return auth

@pytest.fixture
async def test_user(simple_auth):
    """Create test user"""
    return await simple_auth.user_service.create_user(
        email="test@example.com",
        password="Test123!@#"
    )
```

---

## Migration Path from Current System

### Phase 1: Parallel Development
- Keep current API running
- Develop library alongside
- Test library in isolated projects

### Phase 2: Selective Migration
- New projects use library
- Existing projects stay on API
- No forced migration

### Phase 3: Gradual Deprecation
- Document API deprecation timeline
- Provide migration tools
- Support both for transition period

### Phase 4: API Sunset
- After all projects migrated
- Archive API code
- Maintain library only

---

## Performance Considerations

### Caching Strategy (EnterpriseRBAC with caching enabled)
```python
# Redis cache keys
user_permissions:{user_id}:{entity_id}  # TTL: 5 minutes
entity_path:{entity_id}                 # TTL: 10 minutes
role_permissions:{role_id}              # TTL: 15 minutes

# Cache invalidation on:
- Role permissions changed
- User membership changed
- Entity hierarchy changed
```

### Database Indexes
```python
# User collection
{"email": 1}  # Unique
{"status": 1}

# Role collection
{"name": 1}

# Permission collection
{"name": 1}
{"resource": 1, "action": 1}

# Entity collection (EnterpriseRBAC only)
{"slug": 1}  # Unique
{"parent_entity": 1}
{"entity_type": 1}

# EntityMembership collection (EnterpriseRBAC only)
{"user": 1, "entity": 1}  # Unique
{"entity": 1}
{"user": 1}
```

### Query Optimization
- Eager loading of relationships (use `fetch_links=True`)
- Batch permission checks when possible
- Limit entity path traversal depth
- Cache expensive queries

---

## Next Steps

1. ✅ Architecture defined
2. 🔄 Create implementation roadmap (next)
3. ⏭️ Design public API
4. ⏭️ Begin Phase 1 implementation

---

**Last Updated**: 2025-01-14 (Added authentication extensions architecture)
**Next Review**: After Phase 1 prototype
