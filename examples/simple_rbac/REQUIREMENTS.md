# Blog API - Requirements & Use Cases

**Created**: 2025-01-25
**Purpose**: Demonstrate OutlabsAuth's SimpleRBAC preset for flat role-based access control
**Preset**: SimpleRBAC

---

## Table of Contents
1. [Project Vision](#project-vision)
2. [Why a Blog Example?](#why-a-blog-example)
3. [User Roles](#user-roles)
4. [Permission Model](#permission-model)
5. [Domain Model](#domain-model)
6. [What OutlabsAuth Provides](#what-outlabsauth-provides)
7. [What We Implement](#what-we-implement)
8. [SimpleRBAC vs EnterpriseRBAC](#simplerbac-vs-enterpriserbac)
9. [Testing Scenarios](#testing-scenarios)

---

## Project Vision

Demonstrate how OutlabsAuth's **SimpleRBAC** preset works with a **flat role-based access control** system. This example shows:

### Key Features
- ✅ **Flat RBAC**: No entity hierarchy, just users → roles → permissions
- ✅ **Direct role assignment**: Users are directly assigned roles
- ✅ **Simple permission model**: Clear, easy-to-understand permissions
- ✅ **Minimal code**: Most functionality provided by OutlabsAuth routers
- ✅ **Real-world domain**: Blog with posts and comments

### Goals
1. **Show SimpleRBAC in action**: Complete example of flat RBAC
2. **Minimal implementation**: Focus on domain logic, not auth plumbing
3. **Easy to understand**: Universal domain everyone knows (blogging)
4. **Contrast with EnterpriseRBAC**: Clear when to use Simple vs Enterprise

---

## Why a Blog Example?

### Universal Understanding
Everyone understands blogs:
- Posts with authors
- Comments from readers
- Editors managing content
- Admins with full control

### Perfect for SimpleRBAC
Blogs have a flat structure:
- No departments or teams
- No hierarchical organizations
- Simple: readers, writers, editors, admins
- Direct permissions: "Can you create a post? Yes/No"

### Real-World Patterns
This pattern applies to many applications:
- Content management systems
- Knowledge bases
- Community forums
- Simple SaaS products

---

## User Roles

### Reader (Default)
**Description**: Can view published content

**Permissions**: None (public access)

**What they can do**:
- ✅ View published blog posts
- ✅ View comments
- ❌ Create posts or comments
- ❌ Edit anything

**Use case**: Anonymous visitors, free tier users

---

### Writer
**Description**: Can create content

**Permissions**:
- `post:create` - Create new blog posts
- `comment:create` - Add comments to posts

**What they can do**:
- ✅ Everything a Reader can do
- ✅ Create new blog posts (drafts or published)
- ✅ Add comments to any post
- ❌ Edit or delete posts (even their own)
- ❌ Delete comments

**Use case**: Contributing authors, community members

---

### Editor
**Description**: Can manage their own content

**Permissions**:
- `post:create` - Create new posts
- `post:update_own` - Update their own posts
- `post:delete_own` - Delete their own posts
- `comment:create` - Add comments
- `comment:delete_own` - Delete their own comments

**What they can do**:
- ✅ Everything a Writer can do
- ✅ Update their own posts (title, content, status)
- ✅ Delete their own posts
- ✅ Delete their own comments
- ❌ Edit or delete others' content

**Use case**: Regular blog authors, content creators

---

### Admin
**Description**: Full control over all content

**Permissions**:
- `post:create` - Create posts
- `post:update` - Update ANY post
- `post:delete` - Delete ANY post
- `comment:create` - Create comments
- `comment:delete` - Delete ANY comment
- `user:read` - View user information
- `user:manage` - Manage user roles

**What they can do**:
- ✅ Everything
- ✅ Edit any post (even others' posts)
- ✅ Delete any post or comment
- ✅ Manage user roles
- ✅ View all users

**Use case**: Blog administrators, moderators

---

## Permission Model

### Post Permissions

**Basic Permissions**:
```python
"post:create"        # Create new posts (writer+)
"post:update_own"    # Update own posts (editor+)
"post:update"        # Update ANY post (admin)
"post:delete_own"    # Delete own posts (editor+)
"post:delete"        # Delete ANY post (admin)
```

**Permission Checks**:
```python
# Can user edit this post?
def can_edit_post(user_id, post_author_id, permissions):
    # Admin can edit anything
    if "post:update" in permissions:
        return True

    # Editor can edit own posts
    if "post:update_own" in permissions and user_id == post_author_id:
        return True

    return False
```

### Comment Permissions

**Basic Permissions**:
```python
"comment:create"     # Add comments (writer+)
"comment:delete_own" # Delete own comments (editor+)
"comment:delete"     # Delete ANY comment (admin)
```

### User Management Permissions (Admin Only)

```python
"user:read"          # View user information
"user:manage"        # Manage user roles
```

---

## Domain Model

### BlogPost

```python
class BlogPost(Document):
    # Content
    title: str                    # Post title
    content: str                  # Post body (markdown)
    author_id: str                # User ID who created

    # Status
    status: "draft" | "published" | "archived"

    # Metadata
    tags: List[str]               # Post tags
    created_at: datetime
    updated_at: datetime
    view_count: int               # Incremented on view

    # Indexes
    - author_id (for "my posts")
    - status (for listing published)
    - tags (for filtering)
```

**Status Flow**:
```
draft → published → archived
  ↑         ↓
  └─────────┘ (can revert)
```

### Comment

```python
class Comment(Document):
    # Content
    post_id: str                  # Which post
    author_id: str                # Who wrote it
    content: str                  # Comment text

    # Metadata
    created_at: datetime
    updated_at: datetime

    # Indexes
    - post_id (for listing comments on post)
    - author_id (for "my comments")
```

---

## What OutlabsAuth Provides

### Auth Routes (`/auth/*`)
- ✅ `POST /auth/register` - User registration
- ✅ `POST /auth/login` - Login with JWT
- ✅ `POST /auth/logout` - Logout
- ✅ `POST /auth/refresh` - Refresh access token

### User Routes (`/users/*`)
- ✅ `GET /users/me` - Current user info
- ✅ `GET /users` - List users (admin)
- ✅ `GET /users/{id}` - Get user by ID
- ✅ `PUT /users/{id}` - Update user
- ✅ `DELETE /users/{id}` - Delete user (admin)
- ✅ `POST /users/{id}/roles` - Assign role to user
- ✅ `DELETE /users/{id}/roles/{role_id}` - Remove role

### Role Routes (`/roles/*`)
- ✅ `GET /roles` - List all roles
- ✅ `POST /roles` - Create role (admin)
- ✅ `GET /roles/{id}` - Get role details
- ✅ `PUT /roles/{id}` - Update role
- ✅ `DELETE /roles/{id}` - Delete role

### Permission Routes (`/permissions/*`)
- ✅ `GET /permissions/check` - Check if user has permission

### API Key Routes (`/api-keys/*`)
- ✅ `POST /api-keys` - Create API key
- ✅ `GET /api-keys` - List API keys
- ✅ `DELETE /api-keys/{id}` - Revoke API key

**That's 20+ routes we DON'T have to write!**

---

## What We Implement

### Domain-Specific Routes (Blog)

Only **7 routes** for the entire blog functionality:

**Posts**:
- `POST /posts` - Create post
- `GET /posts` - List posts (with pagination)
- `GET /posts/{id}` - View post details
- `PUT /posts/{id}` - Update post
- `DELETE /posts/{id}` - Delete post

**Comments**:
- `POST /posts/{id}/comments` - Add comment
- `GET /posts/{id}/comments` - List comments on post
- `DELETE /comments/{id}` - Delete comment

**Health**:
- `GET /health` - Health check

**Plus**:
- Startup logic to create default roles
- Domain models (BlogPost, Comment)
- Permission check logic

**Total LOC**: ~600 lines (vs 2000+ without OutlabsAuth)

---

## SimpleRBAC vs EnterpriseRBAC

### When to Use SimpleRBAC ✅

**Your structure looks like this**:
```
Users → Roles → Permissions
```

**Examples**:
- Blog platforms
- Simple SaaS apps
- Content management systems
- Community forums
- Personal productivity apps

**Characteristics**:
- Flat organization
- No departments/teams
- Direct role assignment
- Simple permission model
- Small to medium scale

---

### When to Use EnterpriseRBAC ⚠️

**Your structure looks like this**:
```
Company → Departments → Teams → Users → Roles → Permissions
```

**Examples**:
- Real estate platforms (franchises, brokerages, teams)
- Enterprise CRM systems
- Entity-isolated SaaS with org hierarchies
- Corporate applications

**Characteristics**:
- Hierarchical organizations
- Departments, teams, workspaces
- Tree permissions (manager sees all team data)
- Context-aware roles
- Large scale, complex structures

---

### Comparison Matrix

| Feature | SimpleRBAC (Blog) | EnterpriseRBAC (Real Estate) |
|---------|-------------------|------------------------------|
| **Hierarchy** | ❌ Flat | ✅ 5-level tree |
| **Entities** | ❌ No | ✅ Franchises, teams, etc. |
| **Memberships** | ❌ Direct roles | ✅ Entity memberships |
| **Tree Permissions** | ❌ No | ✅ Manager sees all team data |
| **Complexity** | Low | High |
| **Setup Time** | Minutes | Hours |
| **Best For** | Blogs, simple apps | Enterprises, platforms |

---

## Testing Scenarios

### Test 1: Reader Cannot Create Posts
1. Register new user
2. Login (no role assigned)
3. Try to create post via `POST /posts`
4. **Expected**: 403 Forbidden (missing `post:create` permission)

**Demonstrates**: Permission enforcement works

---

### Test 2: Writer Can Create Posts
1. Register new user
2. Assign "writer" role
3. Login
4. Create post via `POST /posts`
5. **Expected**: 201 Created

**Demonstrates**: Writers have `post:create` permission

---

### Test 3: Editor Can Update Own Posts
1. Register user, assign "editor" role
2. Create post (as author)
3. Update post via `PUT /posts/{id}`
4. **Expected**: 200 OK

**Demonstrates**: Editors can edit their own posts

---

### Test 4: Editor Cannot Update Others' Posts
1. User A creates post (editor)
2. User B tries to update User A's post (also editor)
3. **Expected**: 403 Forbidden

**Demonstrates**: `post:update_own` respects ownership

---

### Test 5: Admin Can Update Any Post
1. User A creates post (writer)
2. Admin tries to update User A's post
3. **Expected**: 200 OK

**Demonstrates**: Admin has `post:update` (no ownership check)

---

### Test 6: Admin Can Delete Any Comment
1. User A adds comment
2. Admin deletes User A's comment
3. **Expected**: 204 No Content

**Demonstrates**: Admin moderation capabilities

---

### Test 7: Public Can View Published Posts
1. No authentication
2. `GET /posts` (default: status=published)
3. **Expected**: 200 OK with list of published posts

**Demonstrates**: Public read access works

---

### Test 8: Drafts Are Private
1. Writer creates draft post
2. Anonymous user tries `GET /posts` (status=draft)
3. **Expected**: Only author's drafts visible (or empty list for anonymous)

**Demonstrates**: Draft visibility control

---

## Success Criteria

### Functional Requirements
- ✅ Users can register and login
- ✅ Roles are automatically created on startup
- ✅ Permission enforcement works correctly
- ✅ Writers can create posts
- ✅ Editors can manage own posts
- ✅ Admins can manage all content
- ✅ Public can view published posts
- ✅ Comments work correctly

### Non-Functional Requirements
- ✅ Docker Compose setup works
- ✅ Live reload works for library changes
- ✅ Live reload works for app changes
- ✅ API documentation available at `/docs`
- ✅ Health check endpoint responds
- ✅ All tests pass

### Code Quality
- ✅ Minimal implementation (focus on domain logic)
- ✅ Clear separation of concerns
- ✅ Well-documented code
- ✅ Production-ready patterns

---

## Future Enhancements

### Phase 2: Additional Features
- **Post categories**: Organize posts by topic
- **Post likes**: Track popular posts
- **Comment threading**: Nested replies
- **Rich text editor**: Markdown rendering

### Phase 3: Social Features
- **User profiles**: Author pages
- **Follow system**: Follow favorite authors
- **Notifications**: New posts from followed authors
- **RSS feeds**: Subscribe to blog updates

### Phase 4: Analytics
- **View tracking**: Most viewed posts
- **Engagement metrics**: Comments per post
- **Author analytics**: Post performance
- **Trending content**: Popular this week

---

**Last Updated**: 2025-01-25
**Status**: Requirements Complete - Implementation Ready
**Next Step**: Test Docker Compose and verify all functionality
