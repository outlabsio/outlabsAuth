# OutlabsAuth Documentation Index

**Quick Access Index** - Jump directly to what you need

---

## 🔍 By Topic

### Authentication
- [[21-Email-Password-Auth|Email & Password]] - Traditional authentication
- [[22-JWT-Tokens|JWT Tokens]] - Access and refresh tokens
- [[23-API-Keys|API Keys]] - Programmatic access
- [[30-OAuth-Overview|OAuth/Social Login]] - Google, Facebook, GitHub
- [[25-Multi-Source-Auth|Multi-Source Auth]] - JWT + API Key + Service Token

### Authorization
- [[41-SimpleRBAC|SimpleRBAC]] - Flat role-based access control
- [[42-EnterpriseRBAC|EnterpriseRBAC]] - Hierarchical RBAC
- [[43-Permissions-System|Permissions]] - How permissions work
- [[44-Tree-Permissions|Tree Permissions]] - Hierarchical access
- [[45-Context-Aware-Roles|Context-Aware Roles]] - Dynamic permissions

### Entity System
- [[50-Entity-System|Entity System]] - Organizational hierarchy
- [[51-Entity-Types|Entity Types]] - STRUCTURAL vs ACCESS_GROUP
- [[52-Entity-Hierarchy|Entity Hierarchy]] - Building org structures
- [[53-Closure-Table|Closure Table]] - Performance optimization

### API Routes
- [[91-Auth-Router|Authentication Routes]] - /auth endpoints
- [[92-Users-Router|User Routes]] - /users endpoints
- [[93-API-Keys-Router|API Key Routes]] - /api-keys endpoints
- [[94-OAuth-Router|OAuth Routes]] - /auth/{provider} endpoints

---

## 🎯 By Use Case

### "I want to add basic auth to my FastAPI app"
→ [[02-Quick-Start|Quick Start]] → [[41-SimpleRBAC|SimpleRBAC]]

### "I need hierarchical permissions (company → teams)"
→ [[42-EnterpriseRBAC|EnterpriseRBAC]] → [[50-Entity-System|Entity System]]

### "I want to add Google/Facebook login"
→ [[30-OAuth-Overview|OAuth Overview]] → [[31-OAuth-Setup|OAuth Setup]]

### "I need API keys for my API service"
→ [[23-API-Keys|API Keys]] → [[93-API-Keys-Router|API Keys Router]]

### "How do I customize auth behavior?"
→ [[102-Lifecycle-Hooks|Lifecycle Hooks]] → [[134-Custom-Hooks|Custom Hooks]]

### "I'm migrating from FastAPI-Users"
→ [[170-Migration-From-FastAPI-Users|Migration Guide]] → [[250-Comparison-FastAPI-Users|Comparison]]

---

## 📚 By Learning Path

### Beginner Path
1. [[01-Introduction|Introduction]]
2. [[02-Quick-Start|Quick Start]]
3. [[04-Basic-Concepts|Basic Concepts]]
4. [[41-SimpleRBAC|SimpleRBAC]]
5. [[150-Tutorial-Simple-App|Tutorial: Simple App]]

### Intermediate Path
1. [[42-EnterpriseRBAC|EnterpriseRBAC]]
2. [[50-Entity-System|Entity System]]
3. [[44-Tree-Permissions|Tree Permissions]]
4. [[30-OAuth-Overview|OAuth]]
5. [[151-Tutorial-Enterprise-App|Tutorial: Enterprise App]]

### Advanced Path
1. [[100-Transport-Strategy-Pattern|Design Patterns]]
2. [[120-Redis-Integration|Redis Integration]]
3. [[180-Deep-Dive-Permissions|Deep Dive: Permissions]]
4. [[111-Performance-Optimization|Performance]]
5. [[223-Production-Checklist|Production Deployment]]

---

## 🔧 By Component

### Services
- [[70-User-Service|UserService]] - User management
- [[71-Role-Service|RoleService]] - Role management
- [[72-Permission-Service|PermissionService]] - Permission checking
- [[73-API-Key-Service|ApiKeyService]] - API key management
- [[74-Auth-Service|AuthService]] - Authentication logic

### Dependencies
- [[80-Auth-Dependencies|AuthDeps]] - Dependency injection
- [[81-Require-Auth|require_auth()]] - Auth dependency
- [[82-Require-Permission|require_permission()]] - Permission dependency
- [[83-Require-Role|require_role()]] - Role dependency

### Patterns
- [[100-Transport-Strategy-Pattern|Transport/Strategy]]
- [[101-Dynamic-Dependencies|Dynamic Dependencies]]
- [[102-Lifecycle-Hooks|Lifecycle Hooks]]
- [[103-Router-Factory-Pattern|Router Factories]]

---

## 🚀 Quick References

### Code Examples
- [[02-Quick-Start#Option-1-SimpleRBAC|SimpleRBAC Setup]]
- [[02-Quick-Start#Option-2-EnterpriseRBAC|EnterpriseRBAC Setup]]
- [[02-Quick-Start#Add-OAuth-Login|OAuth Integration]]
- [[02-Quick-Start#Add-API-Keys|API Keys]]

### Common Tasks
- [[161-How-To-Custom-Permissions|Create Custom Permissions]]
- [[162-How-To-Multi-Tenant|Implement Multi-Tenancy]]
- [[163-How-To-Rate-Limiting|Add Rate Limiting]]
- [[164-How-To-Audit-Logging|Implement Audit Logging]]

### Troubleshooting
- [[262-Troubleshooting|Common Issues]]
- [[261-FAQ|FAQ]]
- [[223-Production-Checklist|Production Checklist]]

---

## 📖 Complete Table of Contents

See [[README|Full Documentation Structure]] for the complete table of contents with all sections.

---

## 🏷️ Tag Index

### #getting-started
[[01-Introduction]] • [[02-Quick-Start]] • [[03-Installation]] • [[04-Basic-Concepts]]

### #authentication
[[21-Email-Password-Auth]] • [[22-JWT-Tokens]] • [[23-API-Keys]] • [[24-Service-Tokens]] • [[25-Multi-Source-Auth]]

### #oauth
[[30-OAuth-Overview]] • [[31-OAuth-Setup]] • [[32-OAuth-Providers]] • [[33-OAuth-Account-Linking]] • [[34-OAuth-Security]]

### #authorization
[[40-Authorization-Overview]] • [[41-SimpleRBAC]] • [[42-EnterpriseRBAC]] • [[43-Permissions-System]] • [[44-Tree-Permissions]]

### #entity-system
[[50-Entity-System]] • [[51-Entity-Types]] • [[52-Entity-Hierarchy]] • [[53-Closure-Table]] • [[54-Entity-Memberships]]

### #api-reference
[[60-SimpleRBAC-API]] • [[61-EnterpriseRBAC-API]] • [[70-User-Service]] • [[80-Auth-Dependencies]] • [[90-Router-Factories-Overview]]

### #patterns
[[100-Transport-Strategy-Pattern]] • [[101-Dynamic-Dependencies]] • [[102-Lifecycle-Hooks]] • [[103-Router-Factory-Pattern]]

### #performance
[[111-Performance-Optimization]] • [[120-Redis-Integration]] • [[122-Redis-Counters]] • [[123-Redis-Pub-Sub]] • [[53-Closure-Table]]

### #tutorials
[[150-Tutorial-Simple-App]] • [[151-Tutorial-Enterprise-App]] • [[152-Tutorial-OAuth-Integration]] • [[153-Tutorial-API-Keys]]

### #migration
[[170-Migration-From-FastAPI-Users]] • [[171-Migration-From-AuthLib]] • [[172-Migration-Version-Guide]]

---

## 🔗 External Links

- **GitHub**: https://github.com/outlabsio/outlabsAuth
- **PyPI**: https://pypi.org/project/outlabs-auth/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **httpx-oauth**: https://frankie567.github.io/httpx-oauth/
- **MongoDB**: https://www.mongodb.com/docs/

---

Last Updated: 2025-01-23
