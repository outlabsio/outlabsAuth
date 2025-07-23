# Platform Setup Guide

This guide provides step-by-step instructions for setting up a new platform in OutlabsAuth. It covers everything from initial platform creation to onboarding your first users.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Phase 1: Platform Creation](#phase-1-platform-creation)
3. [Phase 2: Define Permissions](#phase-2-define-permissions)
4. [Phase 3: Create Role Templates](#phase-3-create-role-templates)
5. [Phase 4: Build Entity Structure](#phase-4-build-entity-structure)
6. [Phase 5: Configure Access Groups](#phase-5-configure-access-groups)
7. [Phase 6: Platform Administrator Setup](#phase-6-platform-administrator-setup)
8. [Phase 7: Initial User Onboarding](#phase-7-initial-user-onboarding)
9. [Phase 8: Integration Configuration](#phase-8-integration-configuration)
10. [Verification Checklist](#verification-checklist)

## Prerequisites

Before setting up a new platform, ensure you have:
- System administrator access to OutlabsAuth
- Platform details (name, description, type of business)
- Understanding of the platform's organizational structure
- List of required permissions and roles
- Initial platform administrators identified

## Phase 1: Platform Creation

### Understanding Platforms

In OutlabsAuth, a "platform" is simply **any entity without a parent**. This flexible design means:
- You can use any `entity_type` that fits your business (not just "platform")
- The top-level entity automatically becomes your isolated platform
- All child entities inherit the platform_id from this root entity

### Step 1: Create the Platform Entity

Using the OutlabsAuth Admin UI or API:

```python
# API Example - Choose an entity_type that fits your business model
platform_data = {
    "name": "your_platform_name",  # lowercase, no spaces
    "display_name": "Your Platform Name",
    "entity_type": "workspace",  # Can be: "platform", "workspace", "company", "account", etc.
    "entity_class": "STRUCTURAL",
    "parent_entity": None,  # No parent = this becomes a platform
    "metadata": {
        "description": "Lead generation platform for real estate",
        "contact_email": "admin@yourplatform.com",
        "website": "https://yourplatform.com",
        "industry": "real_estate",
        "created_date": datetime.utcnow().isoformat()
    }
}

# Create platform (top-level entity)
response = await outlabs_auth.post("/v1/entities/", platform_data)
platform = response.json()
platform_id = platform["id"]
```

### Step 2: Configure Platform Settings

```python
platform_settings = {
    "platform_id": platform_id,
    "settings": {
        "user_registration": {
            "self_registration_enabled": True,
            "require_email_verification": True,
            "default_entity_placement": "platform",
            "auto_approve_users": False
        },
        "security": {
            "password_policy": {
                "min_length": 12,
                "require_uppercase": True,
                "require_numbers": True,
                "require_special_chars": True
            },
            "session_timeout_minutes": 60,
            "max_login_attempts": 5,
            "mfa_required": False
        },
        "branding": {
            "primary_color": "#2563eb",
            "logo_url": "https://yourplatform.com/logo.png",
            "support_email": "support@yourplatform.com"
        }
    }
}
```

## Phase 2: Define Permissions

### Step 1: Identify Required Permissions

Create a comprehensive list of platform-specific permissions:

```yaml
# Example for a real estate platform
permissions:
  # Lead Management
  - lead:view_own
  - lead:view_team
  - lead:view_all
  - lead:create
  - lead:update
  - lead:delete
  - lead:assign
  - lead:transfer
  
  # Property Management
  - property:view
  - property:create
  - property:update
  - property:delete
  - property:list
  
  # Commission Management
  - commission:view_own
  - commission:view_team
  - commission:calculate
  - commission:approve
  - commission:override
  
  # Reporting
  - report:view_own
  - report:view_team
  - report:view_organization
  - report:export
  - report:create_custom
```

### Step 2: Create Custom Permissions

```python
# Create platform-specific permissions
for permission in custom_permissions:
    perm_data = {
        "name": permission["name"],
        "display_name": permission["display_name"],
        "description": permission["description"],
        "platform_id": platform_id,
        "category": permission["category"],
        "risk_level": permission.get("risk_level", "low")
    }
    
    await outlabs_auth.post("/v1/permissions/", perm_data)
```

## Phase 3: Create Role Templates

### Step 1: Define Standard Roles

```python
platform_roles = [
    {
        "name": "platform_user",
        "display_name": "Platform User",
        "description": "Basic platform user with minimal permissions",
        "permissions": [
            "profile:read_own",
            "profile:update_own",
            "lead:view_own"
        ]
    },
    {
        "name": "agent",
        "display_name": "Agent",
        "description": "Sales agent with lead management capabilities",
        "permissions": [
            "lead:view_own",
            "lead:create",
            "lead:update",
            "property:view",
            "commission:view_own",
            "report:view_own"
        ]
    },
    {
        "name": "team_lead",
        "display_name": "Team Lead",
        "description": "Team leader with team management capabilities",
        "permissions": [
            "lead:view_team",
            "lead:assign",
            "lead:transfer",
            "member:invite",
            "member:remove",
            "commission:view_team",
            "report:view_team"
        ]
    },
    {
        "name": "manager",
        "display_name": "Manager",
        "description": "Office or branch manager",
        "permissions": [
            "lead:view_all",
            "lead:distribute",
            "agent:manage",
            "commission:approve",
            "report:view_organization",
            "entity:create_team"
        ]
    }
]
```

### Step 2: Create Roles

```python
for role_data in platform_roles:
    # Create role scoped to platform
    role = {
        "name": f"{platform_name}_{role_data['name']}",
        "display_name": role_data["display_name"],
        "description": role_data["description"],
        "entity_id": platform_id,
        "permissions": role_data["permissions"],
        "is_system_role": False,
        "metadata": {
            "platform": platform_name,
            "created_for": "platform_setup"
        }
    }
    
    await outlabs_auth.post("/v1/roles/", role)
```

## Phase 4: Build Entity Structure

### Step 1: Plan Your Hierarchy

```
Platform
├── Default Organization (for individual users)
├── Client Organization 1
│   ├── Regional Office 1
│   │   ├── Branch A
│   │   │   └── Team 1
│   │   └── Branch B
│   └── Regional Office 2
└── Client Organization 2
```

### Step 2: Create Default Organization

Every platform should have a default organization for individual users:

```python
default_org = {
    "name": f"{platform_name}_individual_users",
    "display_name": "Individual Users",
    "entity_type": "organization",
    "entity_class": "STRUCTURAL",
    "parent_entity_id": platform_id,
    "metadata": {
        "is_default": True,
        "description": "Default organization for individual platform users",
        "auto_assign_new_users": True
    }
}

response = await outlabs_auth.post("/v1/entities/", default_org)
default_org_id = response.json()["id"]
```

### Step 3: Create Initial Organizations

```python
# Example: Create a client organization
client_org = {
    "name": "acme_realty",
    "display_name": "ACME Realty Inc",
    "entity_type": "organization",
    "entity_class": "STRUCTURAL",
    "parent_entity_id": platform_id,
    "metadata": {
        "client_id": "ACME-001",
        "contract_start": "2024-01-01",
        "license_count": 500,
        "billing_contact": "billing@acmerealty.com"
    }
}

response = await outlabs_auth.post("/v1/entities/", client_org)
```

## Phase 5: Create Your Organizational Structure

### Flexible Entity Types

outlabsAuth now supports flexible entity types, allowing you to use terminology that matches your business model. Here are examples for different industries:

```python
# Real Estate Platform
entities = [
    {
        "name": "west_region",
        "display_name": "West Coast Region",
        "entity_type": "region",  # Custom type: "region"
        "entity_class": "STRUCTURAL",
        "parent_entity_id": platform_id
    },
    {
        "name": "seattle_office",
        "display_name": "Seattle Office",
        "entity_type": "office",  # Custom type: "office"
        "entity_class": "STRUCTURAL",
        "parent_entity_id": west_region_id
    }
]

# Corporate Structure
entities = [
    {
        "name": "sales_division",
        "display_name": "Sales Division",
        "entity_type": "division",  # Custom type: "division"
        "entity_class": "STRUCTURAL",
        "parent_entity_id": platform_id
    },
    {
        "name": "enterprise_sales",
        "display_name": "Enterprise Sales Department",
        "entity_type": "department",  # Custom type: "department"
        "entity_class": "STRUCTURAL",
        "parent_entity_id": sales_division_id
    }
]

# Government Agency
entities = [
    {
        "name": "transport_bureau",
        "display_name": "Bureau of Transportation",
        "entity_type": "bureau",  # Custom type: "bureau"
        "entity_class": "STRUCTURAL",
        "parent_entity_id": platform_id
    },
    {
        "name": "highways_section",
        "display_name": "Highways and Roads Section",
        "entity_type": "section",  # Custom type: "section"
        "entity_class": "STRUCTURAL",
        "parent_entity_id": transport_bureau_id
    }
]
```

**Entity Type Best Practices:**
- Use lowercase with underscores (e.g., "cost_center", "profit_center")
- Be consistent across your platform
- Use the entity-types endpoint to see existing types and maintain consistency
- Choose names that are meaningful to your users

## Phase 6: Configure Access Groups

### Step 1: Create Common Access Groups

```python
# Check existing entity types for consistency
existing_types = await outlabs_auth.get("/v1/entities/entity-types?entity_class=ACCESS_GROUP")
print("Existing access group types:", [t["entity_type"] for t in existing_types["suggestions"]])

access_groups = [
    {
        "name": "platform_admins",
        "display_name": "Platform Administrators",
        "entity_type": "admin_group",
        "entity_class": "ACCESS_GROUP",
        "parent_entity_id": platform_id,
        "metadata": {
            "description": "Platform-wide administrators",
            "approval_required": True,
            "max_members": 10
        }
    },
    {
        "name": "top_performers",
        "display_name": "Top Performers Club",
        "entity_type": "performance_group",
        "entity_class": "ACCESS_GROUP",
        "parent_entity_id": platform_id,
        "metadata": {
            "description": "High-performing agents with special privileges",
            "qualification_criteria": "min_sales_per_month: 10",
            "auto_qualify": True
        }
    },
    {
        "name": "beta_testers",
        "display_name": "Beta Feature Access",
        "entity_type": "feature_access_group",
        "entity_class": "ACCESS_GROUP",
        "parent_entity_id": platform_id,
        "metadata": {
            "description": "Users with access to beta features",
            "feature_flags": ["new_ui", "advanced_analytics"]
        }
    }
]

for group in access_groups:
    await outlabs_auth.post("/v1/entities/", group)
```

### Step 2: Assign Permissions to Access Groups

```python
# Give platform admins full platform permissions
admin_group_role = {
    "name": "platform_admin_role",
    "display_name": "Platform Admin Role",
    "entity_id": platform_admins_group_id,
    "permissions": [
        "entity:manage_platform",
        "user:manage_platform",
        "role:manage_platform",
        "settings:manage_platform"
    ]
}

await outlabs_auth.post("/v1/roles/", admin_group_role)
```

## Phase 6: Platform Administrator Setup

### Step 1: Create Platform Admin Users

```python
# Create the first platform administrator
platform_admin = {
    "email": "admin@yourplatform.com",
    "password": "secure_temp_password",
    "profile": {
        "first_name": "Platform",
        "last_name": "Administrator",
        "phone": "+1234567890"
    },
    "metadata": {
        "role": "platform_administrator",
        "created_by": "system_setup"
    }
}

admin_user = await outlabs_auth.post("/v1/users/", platform_admin)
```

### Step 2: Assign Platform Admin Role

```python
# Add admin to platform with admin role
membership = {
    "user_id": admin_user["id"],
    "entity_id": platform_id,
    "role_ids": [platform_admin_role_id],
    "metadata": {
        "assigned_by": "system",
        "reason": "initial_platform_setup"
    }
}

await outlabs_auth.post("/v1/memberships/", membership)

# Also add to platform admins access group
group_membership = {
    "user_id": admin_user["id"],
    "entity_id": platform_admins_group_id,
    "role_ids": [platform_admin_role_id]
}

await outlabs_auth.post("/v1/memberships/", group_membership)
```

## Phase 7: Initial User Onboarding

### Step 1: Configure Registration Flow

```python
registration_config = {
    "platform_id": platform_id,
    "registration_flow": {
        "steps": [
            {
                "type": "email_verification",
                "required": True
            },
            {
                "type": "profile_completion",
                "required_fields": ["first_name", "last_name", "phone"]
            },
            {
                "type": "organization_selection",
                "allow_individual": True,
                "show_invite_code": True
            },
            {
                "type": "role_assignment",
                "default_role": "platform_user",
                "selectable_roles": ["agent", "team_lead"]
            }
        ]
    }
}
```

### Step 2: Create Invitation System

```python
# Create invitation for batch user onboarding
invitation_template = {
    "platform_id": platform_id,
    "invitation_type": "platform_onboarding",
    "target_entity_id": default_org_id,
    "default_role": "agent",
    "expires_in_days": 30,
    "metadata": {
        "campaign": "initial_launch",
        "benefits": ["free_training", "reduced_fees_3_months"]
    }
}

# Generate invitation codes
invitations = []
for i in range(100):  # Create 100 invitations
    invite = {
        **invitation_template,
        "code": generate_invite_code(),
        "max_uses": 1
    }
    invitations.append(invite)
```

### Step 3: Set Up Welcome Workflow

```python
welcome_workflow = {
    "platform_id": platform_id,
    "workflow_type": "new_user_onboarding",
    "steps": [
        {
            "action": "send_welcome_email",
            "template": "platform_welcome",
            "delay_minutes": 0
        },
        {
            "action": "assign_onboarding_tasks",
            "tasks": [
                "complete_profile",
                "watch_training_video",
                "configure_notifications",
                "join_team"
            ],
            "delay_minutes": 60
        },
        {
            "action": "schedule_onboarding_call",
            "delay_days": 2,
            "condition": "tasks_incomplete"
        }
    ]
}
```

## Phase 8: Integration Configuration

### Step 1: API Access Setup

```python
# Create API credentials for platform
api_config = {
    "platform_id": platform_id,
    "api_access": {
        "client_id": generate_client_id(),
        "client_secret": generate_client_secret(),
        "allowed_origins": [
            "https://yourplatform.com",
            "https://app.yourplatform.com"
        ],
        "allowed_redirect_uris": [
            "https://yourplatform.com/auth/callback",
            "https://app.yourplatform.com/auth/callback"
        ],
        "scopes": [
            "user:read",
            "user:write",
            "entity:read",
            "permission:check"
        ]
    }
}
```

### Step 2: Configure Webhooks

```python
webhook_config = {
    "platform_id": platform_id,
    "webhooks": [
        {
            "url": "https://api.yourplatform.com/webhooks/outlabs",
            "events": [
                "user.created",
                "user.updated",
                "membership.created",
                "membership.deleted",
                "permission.changed"
            ],
            "secret": generate_webhook_secret(),
            "active": True
        }
    ]
}
```

### Step 3: SSO Configuration (if applicable)

```python
sso_config = {
    "platform_id": platform_id,
    "sso_providers": [
        {
            "provider": "google",
            "client_id": "your-google-client-id",
            "client_secret": "your-google-client-secret",
            "allowed_domains": ["yourplatform.com"],
            "auto_provision_users": True,
            "default_role": "platform_user"
        }
    ]
}
```

## Verification Checklist

### Platform Setup Verification

- [ ] Platform entity created successfully
- [ ] Platform appears in admin UI
- [ ] Platform settings configured
- [ ] Platform metadata complete

### Permissions & Roles

- [ ] All required permissions created
- [ ] Role templates defined
- [ ] Roles assigned proper permissions
- [ ] Permission inheritance working

### Entity Structure

- [ ] Default organization created
- [ ] Initial organizations set up
- [ ] Entity hierarchy correct
- [ ] Access groups configured

### Administrator Access

- [ ] Platform admin user created
- [ ] Admin can log into OutlabsAuth Admin UI
- [ ] Admin sees only platform data
- [ ] Admin can manage platform settings

### User Onboarding

- [ ] Registration flow configured
- [ ] Invitation system working
- [ ] Welcome emails sending
- [ ] Default role assignment working

### Integration

- [ ] API credentials generated
- [ ] Webhook endpoints configured
- [ ] Authentication flow tested
- [ ] Permissions checking working

### Testing

- [ ] Create test user via registration
- [ ] Verify permission inheritance
- [ ] Test role assignment
- [ ] Confirm data isolation

## Common Issues and Solutions

### Issue 1: Users Can't Register
```python
# Check registration settings
settings = await get_platform_settings(platform_id)
if not settings["user_registration"]["self_registration_enabled"]:
    # Enable self-registration
    await update_platform_settings(platform_id, {
        "user_registration": {"self_registration_enabled": True}
    })
```

### Issue 2: Permissions Not Working
```python
# Verify permission exists and is active
permission = await get_permission("lead:view_own")
if not permission or permission.platform_id != platform_id:
    # Create platform-specific permission
    await create_permission({
        "name": "lead:view_own",
        "platform_id": platform_id
    })
```

### Issue 3: Admin Can't See Platform
```python
# Check admin's membership
membership = await get_user_platform_membership(admin_id, platform_id)
if not membership or "platform_admin" not in membership.roles:
    # Add proper admin role
    await add_platform_admin(admin_id, platform_id)
```

## Best Practices

### 1. Start Simple
- Begin with basic entity structure
- Add complexity as needed
- Test each phase before proceeding

### 2. Document Everything
- Keep track of all permissions
- Document role purposes
- Maintain entity structure diagram

### 3. Plan for Growth
- Design scalable entity hierarchy
- Use access groups for flexibility
- Plan permission naming carefully

### 4. Security First
- Set strong password policies
- Enable MFA for admins
- Regular permission audits

### 5. User Experience
- Clear onboarding process
- Helpful error messages
- Intuitive role names

## Next Steps

After completing platform setup:

1. **Train Platform Administrators**
   - How to manage users
   - Entity creation process
   - Permission management

2. **Create Documentation**
   - User guides
   - API documentation
   - Integration guides

3. **Monitor and Optimize**
   - Track user adoption
   - Monitor permission usage
   - Gather feedback

4. **Plan Expansions**
   - Additional entity types
   - New permissions
   - Enhanced features

This guide provides a foundation for setting up any platform in OutlabsAuth. Adapt the examples to match your specific platform requirements.