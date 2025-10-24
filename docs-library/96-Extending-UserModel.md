# 96. Extending UserModel with Beanie Links

> **Quick Reference**: How to extend UserModel to link to business-specific collections (profiles, organizations, subscriptions) using Beanie's Link feature for efficient querying.

## Overview

OutlabsAuth provides a `UserModel` for authentication, but your application likely needs additional user-related data (profiles, organizations, preferences). **The recommended pattern is to use Beanie Links** to connect UserModel to your business-specific collections.

### Why Use Links (Not Flat Fields)?

❌ **DON'T** add business fields directly to UserModel:
```python
# BAD: Mixing auth and business concerns
class CustomUserModel(UserModel):
    company_name: str
    department: str
    bio: str
    license_number: str  # What if not all users have licenses?
```

✅ **DO** use Links to separate collections:
```python
# GOOD: Separation of concerns
class UserProfile(Document):
    company_name: str
    department: str
    bio: str

class ExtendedUserModel(UserModel):
    profile: Optional[Link[UserProfile]] = None
```

**Benefits**:
- ✅ **Separation of Concerns** - Auth data vs business data
- ✅ **Efficient Querying** - Load profile only when needed
- ✅ **Type Safety** - Links are type-checked
- ✅ **Flexibility** - Multiple links, optional relationships
- ✅ **OutlabsAuth Compatibility** - Pre-built routers still work

---

## Pattern 1: Single Profile Link

The simplest pattern - one profile per user.

### Step 1: Define Your Profile Model

```python
from beanie import Document
from pydantic import Field
from typing import Optional, Dict, Any

class UserProfile(Document):
    """Business-specific user profile data"""
    company_name: str
    department: str
    job_title: str
    bio: Optional[str] = None
    social_links: Dict[str, str] = Field(default_factory=dict)
    preferences: Dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "user_profiles"
```

### Step 2: Extend UserModel with Link

```python
from outlabs_auth.models.user import UserModel
from beanie import Link

class ExtendedUserModel(UserModel):
    """UserModel with link to profile"""
    profile: Optional[Link[UserProfile]] = None

    class Settings:
        name = "users"  # Same collection as UserModel
```

### Step 3: Initialize OutlabsAuth

```python
from outlabs_auth import OutlabsAuth
from beanie import init_beanie

# Use extended model
auth = OutlabsAuth(
    database=mongo_db,
    secret_key="your-secret-key",
    user_model=ExtendedUserModel  # Pass your extended model
)

# Initialize Beanie with all document models
await init_beanie(
    database=mongo_db,
    document_models=[
        ExtendedUserModel,
        UserProfile,
        # ... other models (RoleModel, etc.)
    ]
)

await auth.initialize()
```

### Step 4: Query with Link

**Pattern 1: Prefetch with `fetch_links=True` (Best for single queries)**

```python
@app.get("/users/me/profile")
async def get_my_profile(auth_result = Depends(auth.deps.require_auth())):
    """Get current user with profile (prefetched)"""
    user_id = str(auth_result["user"].id)

    # Prefetch all links during the query
    user = await ExtendedUserModel.get(user_id, fetch_links=True)

    # Links are already fetched, access directly
    if user.profile:
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "profile": user.profile.model_dump()
            }
        }

    return {"error": "No profile found"}
```

**Pattern 2: On-Demand Fetching with `fetch_all_links()` (For existing instances)**

```python
@app.get("/users/me/profile")
async def get_my_profile(auth_result = Depends(auth.deps.require_auth())):
    """Get current user with profile (on-demand fetch)"""
    user = auth_result["user"]  # ExtendedUserModel instance

    # Fetch all linked documents at once (replaces Link objects with actual documents)
    await user.fetch_all_links()

    # After fetch, can access profile properties directly
    if user.profile:
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "profile": user.profile.model_dump()
            }
        }

    return {"error": "No profile found"}
```

**Pattern 3: Manual Single Link Fetching**

```python
# Fetch a single specific link
if user.profile:
    await user.fetch_link(ExtendedUserModel.profile)
    # Now can access profile properties
    print(user.profile.company_name)
```

---

## Pattern 2: Multiple Links

Link to multiple related collections.

```python
from beanie import Document, Link
from typing import Optional

class UserProfile(Document):
    """Personal profile data"""
    bio: str
    avatar_url: str
    class Settings:
        name = "user_profiles"

class Organization(Document):
    """Organization/company data"""
    name: str
    domain: str
    class Settings:
        name = "organizations"

class Subscription(Document):
    """Billing/subscription data"""
    plan: str
    expires_at: datetime
    class Settings:
        name = "subscriptions"

class ExtendedUserModel(UserModel):
    """User with multiple relationships"""
    profile: Optional[Link[UserProfile]] = None
    organization: Optional[Link[Organization]] = None
    subscription: Optional[Link[Subscription]] = None

    async def fetch_all(self):
        """Helper to fetch all links at once"""
        await self.fetch_all_links()
```

**Usage**:

```python
@app.get("/users/me/complete")
async def get_complete_user(auth_result = Depends(auth.deps.require_auth())):
    user = auth_result["user"]

    # Fetch all links in one operation
    await user.fetch_all()

    return {
        "user": user.model_dump(),
        "profile": user.profile.model_dump() if user.profile else None,
        "organization": user.organization.model_dump() if user.organization else None,
        "subscription": user.subscription.model_dump() if user.subscription else None
    }
```

---

## Pattern 3: Multiple User Types (Discriminated Union)

Different user types with different profiles - common in platforms with agents, customers, admins, etc.

### Use Case: Real Estate Platform (Internal Tool)

**User Types**:
- **Agent** - Real estate agents with license, brokerage, specialties
- **Team Member** - Internal staff (support, operations, management)
- **Admin** - System administrators (no profile needed)

```python
from typing import Literal
from beanie import Document, Link

class AgentProfile(Document):
    """Real estate agent profile"""
    license_number: str
    license_state: str
    brokerage_name: str
    years_experience: int
    specialties: List[str]  # ["residential", "commercial", "luxury"]
    bio: str
    certifications: List[str]

    # Performance metrics
    deals_closed: int = 0
    total_sales_volume: int = 0

    class Settings:
        name = "agent_profiles"

class TeamMemberProfile(Document):
    """Internal team member profile"""
    job_title: str
    department: Literal["support", "operations", "marketing", "management", "it"]
    access_level: Literal["standard", "elevated", "full"]
    can_view_all_leads: bool = False
    skills: List[str]
    responsibilities: List[str]

    class Settings:
        name = "team_member_profiles"

class ExtendedUserModel(UserModel):
    """User with type-specific profiles"""
    user_type: Literal["agent", "team_member", "admin"] = "team_member"

    # Profile links (only one will be populated based on user_type)
    agent_profile: Optional[Link[AgentProfile]] = None
    team_member_profile: Optional[Link[TeamMemberProfile]] = None

    class Settings:
        name = "users"

    async def get_profile(self) -> Optional[Document]:
        """
        Smart profile fetcher based on user type.
        Returns the appropriate profile or None.
        """
        if self.user_type == "agent" and self.agent_profile:
            await self.agent_profile.fetch()
            return self.agent_profile
        elif self.user_type == "team_member" and self.team_member_profile:
            await self.team_member_profile.fetch()
            return self.team_member_profile
        return None

    async def create_profile_for_type(self) -> Document:
        """
        Create appropriate profile based on user type.
        Called after user registration.
        """
        if self.user_type == "agent":
            profile = AgentProfile(
                license_number="",
                license_state="",
                brokerage_name="",
                years_experience=0,
                specialties=[],
                bio="",
                certifications=[]
            )
            await profile.save()
            self.agent_profile = profile
        elif self.user_type == "team_member":
            profile = TeamMemberProfile(
                job_title="",
                department="support",
                access_level="standard",
                skills=[],
                responsibilities=[]
            )
            await profile.save()
            self.team_member_profile = profile
        else:
            return None  # Admins don't have profiles

        await self.save()
        return profile
```

**Usage**:

```python
@app.post("/auth/register/{user_type}")
async def register_user(
    user_type: Literal["agent", "team_member", "admin"],
    registration: RegistrationRequest
):
    """Register new user with appropriate profile"""

    # Create user via OutlabsAuth
    user = await auth.user_service.create_user(
        email=registration.email,
        password=registration.password,
        user_type=user_type  # Set user type
    )

    # Create appropriate profile
    profile = await user.create_profile_for_type()

    return {
        "user_id": str(user.id),
        "user_type": user.user_type,
        "profile_created": profile is not None
    }

@app.get("/users/me/profile")
async def get_my_profile(auth_result = Depends(auth.deps.require_auth())):
    """Get current user's profile (type-aware)"""
    user = auth_result["user"]
    profile = await user.get_profile()

    if not profile:
        # Create profile if doesn't exist
        profile = await user.create_profile_for_type()

    return {
        "user_type": user.user_type,
        "profile": profile.model_dump() if profile else None
    }

@app.put("/users/me/profile/agent")
async def update_agent_profile(
    profile_data: AgentProfileUpdate,
    auth_result = Depends(auth.deps.require_auth())
):
    """Update agent profile (agents only)"""
    user = auth_result["user"]

    # Validate user type
    if user.user_type != "agent":
        raise HTTPException(403, "Only agents can update agent profiles")

    # Ensure profile exists
    if not user.agent_profile:
        await user.create_profile_for_type()

    # Fetch and update
    await user.agent_profile.fetch()
    for field, value in profile_data.model_dump(exclude_unset=True).items():
        setattr(user.agent_profile, field, value)

    await user.agent_profile.save()
    return user.agent_profile
```

---

## Best Practices

### 1. Use Optional Links

Always use `Optional[Link[...]]` for nullable relationships:

```python
class ExtendedUserModel(UserModel):
    profile: Optional[Link[UserProfile]] = None  # ✅ Can be None
    # profile: Link[UserProfile]  # ❌ Required, breaks on missing profile
```

### 2. Add Helper Methods

Create convenience methods for common operations:

```python
class ExtendedUserModel(UserModel):
    profile: Optional[Link[UserProfile]] = None

    async def get_profile_or_create(self) -> UserProfile:
        """Get profile or create if missing"""
        if self.profile:
            await self.profile.fetch()
            return self.profile

        # Create default profile
        profile = UserProfile(
            company_name="",
            department="",
            job_title=""
        )
        await profile.save()
        self.profile = profile
        await self.save()
        return profile

    async def has_profile(self) -> bool:
        """Check if user has profile"""
        return self.profile is not None
```

### 3. Choose the Right Fetch Pattern

**Option A: Prefetch during query (best for single queries)**

```python
# ✅ BEST: Prefetch all links in the query
user = await ExtendedUserModel.get(user_id, fetch_links=True)
# Links are already resolved, no additional fetch needed
```

**Option B: On-demand batch fetch (for existing instances)**

```python
# ✅ GOOD: Fetch all links at once for existing instance
await user.fetch_all_links()
# All Link objects are replaced with actual documents
```

**Option C: Individual link fetch (only when needed)**

```python
# ⚠️ OK: Fetch specific link when only one is needed
await user.fetch_link(ExtendedUserModel.profile)
# Only the profile link is fetched
```

**Avoid: Multiple individual fetches**

```python
# ❌ BAD: Multiple separate fetch calls
await user.fetch_link(ExtendedUserModel.profile)
await user.fetch_link(ExtendedUserModel.organization)
await user.fetch_link(ExtendedUserModel.subscription)
# Use fetch_all_links() instead!
```

### 4. Cache Fetched Data

Once fetched, links are cached for the object's lifetime:

```python
@app.get("/users/me/dashboard")
async def dashboard(auth_result = Depends(auth.deps.require_auth())):
    user = auth_result["user"]

    # Fetch once
    await user.fetch_all_links()

    # Access multiple times without re-fetching
    profile_data = user.profile.model_dump()
    org_data = user.organization.model_dump()
    # ... no additional queries
```

### 5. Handle Missing Links Gracefully

Always check if link exists before fetching:

```python
@app.get("/users/me/profile")
async def get_profile(auth_result = Depends(auth.deps.require_auth())):
    user = auth_result["user"]

    if not user.profile:
        # Handle missing profile
        return {"error": "No profile found", "user_id": str(user.id)}

    await user.profile.fetch()
    return user.profile
```

---

## Common Patterns

### Pattern: Profile Auto-Creation (Using Hooks)

**Recommended**: Use the `on_after_register` hook to automatically create profiles:

```python
from outlabs_auth.services.user_service import UserService

class MyUserService(UserService):
    """Custom user service with profile auto-creation"""

    async def on_after_register(self, user, request=None):
        """Create profile automatically after user registration"""
        # Create appropriate profile based on user type
        if hasattr(user, 'create_profile_for_type'):
            await user.create_profile_for_type()

# Pass custom service to OutlabsAuth
auth = EnterpriseRBAC(
    database=db,
    secret_key="secret",
    user_model=ExtendedUserModel,
    user_service_class=MyUserService  # Use custom service
)
```

**Alternative**: Create profile manually in registration endpoint:

```python
@app.post("/auth/register")
async def register(registration: RegistrationRequest):
    # Create user
    user = await auth.user_service.create_user(
        email=registration.email,
        password=registration.password
    )

    # Auto-create empty profile
    profile = UserProfile(
        company_name="",
        department="",
        job_title=""
    )
    await profile.save()

    user.profile = profile
    await user.save()

    return {"user_id": str(user.id)}
```

### Pattern: Eager Loading for Lists

Fetch profiles for multiple users efficiently:

```python
@app.get("/users")
async def list_users():
    users = await ExtendedUserModel.find().to_list()

    # Fetch all profiles in parallel
    await asyncio.gather(*[
        user.profile.fetch() if user.profile else None
        for user in users
    ])

    return [
        {
            "user": user.model_dump(),
            "profile": user.profile.model_dump() if user.profile else None
        }
        for user in users
    ]
```

### Pattern: Conditional Links

Different links based on configuration:

```python
class ExtendedUserModel(UserModel):
    # Basic profile (always available)
    profile: Optional[Link[UserProfile]] = None

    # Optional advanced features
    organization: Optional[Link[Organization]] = None  # For team plans
    billing: Optional[Link[BillingInfo]] = None        # For paid plans
```

---

## Working Example

See the complete implementation in:
- **`examples/enterprise_rbac/profiles.py`** - Profile models + ExtendedUserModel
- **`examples/enterprise_rbac/main.py`** - Profile routes
- **`examples/enterprise_rbac/seed_data.py`** - Profile creation

---

## Troubleshooting

### Issue: "Link not fetched"

**Problem**: Accessing link properties before fetching:

```python
# ❌ Error: Link not fetched
profile_name = user.profile.company_name
```

**Solution**: Fetch first:

```python
# ✅ Correct
await user.profile.fetch()
profile_name = user.profile.company_name
```

### Issue: Type Hints Not Working

**Problem**: IDE doesn't recognize extended model fields.

**Solution**: Ensure you pass `user_model` parameter:

```python
# ✅ Correct
auth = OutlabsAuth(
    database=db,
    secret_key="secret",
    user_model=ExtendedUserModel  # Important!
)
```

### Issue: Pre-built Routers Don't Return Custom Fields

**Problem**: `/auth/me` endpoint doesn't include profile link.

**Solution**: This is expected! Pre-built routers use base `UserModel` schema. Create custom routes for extended data:

```python
# Use pre-built router for auth
app.include_router(auth.routers.auth_router, prefix="/auth", tags=["auth"])

# Add custom route for profile
@app.get("/users/me/complete")
async def get_complete_user(auth_result = Depends(auth.deps.require_auth())):
    user = auth_result["user"]
    await user.fetch_all_links()
    return user.model_dump()
```

---

## Summary

**Recommended Pattern**: Beanie Links for extending UserModel

✅ **DO**:
- Use `Optional[Link[...]]` for relationships
- Create separate collections for business data
- Add helper methods for common operations
- Use `fetch_all_links()` for multiple relationships

❌ **DON'T**:
- Add flat business fields to UserModel
- Forget to check if link exists before fetching
- Create required (non-Optional) links

**Key Benefit**: Clean separation between authentication (OutlabsAuth) and business logic (your code).
