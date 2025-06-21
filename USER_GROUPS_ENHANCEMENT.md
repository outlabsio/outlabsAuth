# User Groups Enhancement for RBAC System

## 🎯 Overview

The User Groups enhancement adds a powerful layer of organization to your RBAC system. Users can now belong to groups that have preset roles/permissions, while still maintaining their individual role assignments. This provides the flexibility of bulk permission management while preserving granular control.

## 🏗️ Architecture

### Database Schema Changes

#### New `groups` Collection

```javascript
{
  "_id": ObjectId,
  "name": "Engineering Team",
  "description": "All engineering staff members",
  "client_account": Link["ClientAccountModel"],
  "roles": ["developer", "code_reviewer"],
  "is_active": true,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

#### Updated `users` Collection

```javascript
{
  "_id": ObjectId,
  "email": "user@example.com",
  // ... existing fields ...
  "roles": ["platform_admin"],        // Direct role assignments (unchanged)
  "groups": [Link["GroupModel"]],     // NEW: Group memberships
  // ... rest of fields unchanged ...
}
```

### Authorization Flow (Enhanced)

1. **User Authentication** - User logs in and gets JWT token
2. **Permission Check** - System needs to verify permission
3. **Effective Roles Calculation**:
   - Get user's direct roles: `user.roles`
   - Get user's group roles: `for each group in user.groups -> group.roles`
   - Combine: `effective_roles = direct_roles ∪ group_roles`
4. **Permission Resolution**:
   - For each effective role, get permissions
   - Combine all permissions into final set
5. **Authorization Decision** - Allow/deny based on required permission

## 🚀 API Endpoints

### Group Management

#### Create Group

```http
POST /v1/groups
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Marketing Team",
  "description": "Marketing department staff",
  "client_account_id": "507f1f77bcf86cd799439011",
  "roles": ["content_creator", "campaign_manager"]
}
```

#### List Groups

```http
GET /v1/groups?skip=0&limit=10&client_account_id=507f1f77bcf86cd799439011
Authorization: Bearer <token>
```

#### Update Group

```http
PUT /v1/groups/507f1f77bcf86cd799439012
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Senior Marketing Team",
  "roles": ["content_creator", "campaign_manager", "analytics_viewer"]
}
```

#### Delete Group

```http
DELETE /v1/groups/507f1f77bcf86cd799439012
Authorization: Bearer <token>
```

### Group Membership Management

#### Add Users to Group

```http
POST /v1/groups/507f1f77bcf86cd799439012/members
Authorization: Bearer <token>
Content-Type: application/json

{
  "user_ids": ["507f1f77bcf86cd799439013", "507f1f77bcf86cd799439014"]
}
```

#### Remove Users from Group

```http
DELETE /v1/groups/507f1f77bcf86cd799439012/members
Authorization: Bearer <token>
Content-Type: application/json

{
  "user_ids": ["507f1f77bcf86cd799439013"]
}
```

#### Get Group Members

```http
GET /v1/groups/507f1f77bcf86cd799439012/members
Authorization: Bearer <token>
```

### User Group Information

#### Get User's Groups and Effective Permissions

```http
GET /v1/groups/users/507f1f77bcf86cd799439013/groups
Authorization: Bearer <token>
```

Response:

```json
{
  "user_id": "507f1f77bcf86cd799439013",
  "groups": [
    {
      "id": "507f1f77bcf86cd799439012",
      "name": "Marketing Team",
      "description": "Marketing department staff",
      "roles": ["content_creator", "campaign_manager"],
      "is_active": true
    }
  ],
  "effective_roles": ["platform_admin", "content_creator", "campaign_manager"],
  "effective_permissions": ["user:read", "content:create", "content:edit", "campaign:manage"]
}
```

## 🔐 Permissions

The following new permissions are automatically created:

- `group:create` - Create new groups
- `group:read` - View group information
- `group:update` - Update group details and roles
- `group:delete` - Delete groups
- `group:manage_members` - Add/remove users from groups

## 📋 Usage Examples

### Example 1: Department-Based Groups

```python
# Create department groups
marketing_group = {
    "name": "Marketing Department",
    "description": "All marketing team members",
    "client_account_id": "client_123",
    "roles": ["content_creator", "social_media_manager"]
}

engineering_group = {
    "name": "Engineering Department",
    "description": "All engineering team members",
    "client_account_id": "client_123",
    "roles": ["developer", "code_reviewer", "deployment_manager"]
}

# Users automatically get department permissions
# Plus any individual roles for special access
```

### Example 2: Project-Based Groups

```python
# Create temporary project groups
project_alpha_group = {
    "name": "Project Alpha Team",
    "description": "Members working on Project Alpha",
    "client_account_id": "client_123",
    "roles": ["project_alpha_access", "resource_viewer"]
}

# Add team members
# When project ends, deactivate group or delete it
# Individual permissions remain intact
```

### Example 3: Hierarchical Permissions

```python
# User has individual role: "junior_developer"
# User belongs to group: "Frontend Team" with roles: ["ui_developer", "testing_access"]
# User belongs to group: "Project Beta" with roles: ["project_beta_access"]

# Effective roles: ["junior_developer", "ui_developer", "testing_access", "project_beta_access"]
# Final permissions: combination of all role permissions
```

## 🔄 Migration Guide

### For Existing Users

**No action required!** All existing functionality works exactly the same:

- Existing users keep their direct role assignments
- Authorization continues to work as before
- Groups are purely additive - they only add permissions, never remove them

### For New Implementations

1. **Create Groups**: Define groups that match your organizational structure
2. **Assign Roles to Groups**: Give groups the base permissions most members need
3. **Add Users to Groups**: Bulk assign users to appropriate groups
4. **Individual Overrides**: Add specific roles to individual users as needed

### Migration Script Example

```python
# Optional: Convert existing role patterns to groups
async def migrate_to_groups():
    # Find users with common role patterns
    developers = await UserModel.find(UserModel.roles.in_(["developer"])).to_list()

    # Create a developers group
    dev_group = await group_service.create_group({
        "name": "Developers",
        "description": "All software developers",
        "client_account_id": "your_client_id",
        "roles": ["developer", "code_reviewer"]
    })

    # Add users to group (they keep individual roles too)
    user_ids = [str(user.id) for user in developers]
    await group_service.add_users_to_group(dev_group.id, user_ids)
```

## 🧪 Testing Your Groups

### Test Permission Inheritance

```python
# Create test user with individual role
user = await user_service.create_user({
    "email": "test@example.com",
    "password": "secure_password",
    "roles": ["basic_user"]
})

# Create test group with additional roles
group = await group_service.create_group({
    "name": "Test Group",
    "roles": ["content_viewer", "report_reader"]
})

# Add user to group
await group_service.add_users_to_group(group.id, [str(user.id)])

# Check effective permissions
effective_permissions = await group_service.get_user_effective_permissions(user.id)
# Should include permissions from both "basic_user" AND group roles
```

## 🎛️ Admin UI Integration

The groups feature integrates seamlessly with your admin UI:

### New Screens Needed:

1. **Groups List** - View all groups in client account
2. **Group Details** - Edit group name, description, roles
3. **Group Members** - Manage group membership
4. **User Groups** - View user's group memberships (on user detail page)

### Enhanced Screens:

1. **User Detail** - Show both direct roles AND group memberships
2. **Permission Check** - Show effective permissions from all sources

## 🔧 Configuration Options

### Group Settings (Future Enhancement Ideas)

```python
# Advanced group configuration (not implemented yet, but planned)
class GroupModel:
    # Existing fields...

    # Advanced options for future
    auto_expire: Optional[datetime] = None  # Auto-deactivate groups
    max_members: Optional[int] = None       # Limit group size
    approval_required: bool = False         # Require approval to join
    inheritance_priority: int = 0           # Priority when conflicts arise
```

## 🚨 Important Notes

### Security Considerations

1. **Additive Only**: Groups only ADD permissions, never remove them
2. **Client Scoped**: Groups are scoped to client accounts (multi-tenancy safe)
3. **Audit Trail**: All group changes are logged (future enhancement)
4. **Permission Validation**: Group roles are validated against existing roles

### Performance Considerations

1. **Efficient Queries**: Uses Beanie Links for optimal database queries
2. **Caching Ready**: Permission resolution is designed for caching
3. **Bulk Operations**: Optimized for bulk user management
4. **Index Support**: Proper indexes for common query patterns

### Limitations

1. **No Nested Groups**: Groups cannot contain other groups (by design)
2. **No Role Inheritance**: Groups roles are flat (no role hierarchies)
3. **Client Boundary**: Groups cannot span multiple client accounts

## 🔮 Future Enhancements

### Planned Features

- **Audit Logging**: Track all group membership changes
- **Group Templates**: Pre-defined group configurations
- **Conditional Groups**: Groups with time/location based rules
- **Group Analytics**: Usage statistics and permission analysis

### Integration Possibilities

- **LDAP/AD Sync**: Sync groups from external directories
- **Webhook Notifications**: Real-time group change notifications
- **Bulk Import/Export**: CSV-based group management
- **API Keys**: Service-to-service group management

---

## 📚 Quick Reference

### Key Benefits Recap

✅ **Bulk Management** - Assign permissions to entire teams at once  
✅ **Organizational Structure** - Mirror your company's departments/teams  
✅ **Dynamic Updates** - Change group permissions and all members get updated  
✅ **Granular Control** - Still assign individual permissions when needed  
✅ **Non-Breaking** - All existing functionality remains unchanged  
✅ **Multi-Tenant Safe** - Groups are properly scoped to client accounts

### Common Use Cases

- Department-based permissions (Marketing, Engineering, Sales)
- Project-based access (temporary teams)
- Role-based access with group flexibility (Junior/Senior with team membership)
- Onboarding/offboarding automation (add to groups, remove when leaving)

This enhancement transforms your RBAC system from a basic user-role model to a sophisticated, enterprise-ready authorization system that scales with your organization's needs.
