# OutlabsAuth Library Documentation

**Version**: 1.5
**Status**: Active Development
**Last Updated**: 2025-01-23

Welcome to the OutlabsAuth library documentation. This is a comprehensive FastAPI authentication and authorization library with hierarchical RBAC, tree permissions, and OAuth integration.

## 📚 Documentation Structure

This documentation is organized into the following sections:

### 🚀 Getting Started
- [[01-Introduction|Introduction]] - What is OutlabsAuth?
- [[02-Quick-Start|Quick Start]] - Get running in 5 minutes
- [[03-Installation|Installation]] - Installation options and requirements
- [[04-Basic-Concepts|Basic Concepts]] - Core concepts and terminology

### 🏗️ Architecture
- [[10-Architecture-Overview|Architecture Overview]] - High-level system design
- [[11-Core-Components|Core Components]] - Main building blocks
- [[12-Data-Models|Data Models]] - Database schema and models
- [[13-Authentication-Flow|Authentication Flow]] - How authentication works
- [[14-Authorization-Flow|Authorization Flow]] - How permissions are checked

### 🎯 Core Features

#### Authentication
- [[20-Authentication-Overview|Authentication Overview]]
- [[21-Email-Password-Auth|Email & Password Authentication]]
- [[22-JWT-Tokens|JWT Access & Refresh Tokens]]
- [[23-API-Keys|API Keys]]
- [[24-Service-Tokens|JWT Service Tokens]]
- [[25-Multi-Source-Auth|Multi-Source Authentication]]

#### OAuth/Social Login
- [[30-OAuth-Overview|OAuth Overview]]
- [[31-OAuth-Setup|OAuth Setup Guide]]
- [[32-OAuth-Providers|Supported Providers]] (Google, Facebook, GitHub, etc.)
- [[33-OAuth-Account-Linking|Account Linking]]
- [[34-OAuth-Security|OAuth Security Best Practices]]

#### Authorization
- [[40-Authorization-Overview|Authorization Overview]]
- [[41-SimpleRBAC|SimpleRBAC]] - Flat role-based access control
- [[42-EnterpriseRBAC|EnterpriseRBAC]] - Hierarchical permissions
- [[43-Permissions-System|Permissions System]]
- [[44-Tree-Permissions|Tree Permissions]]
- [[45-Context-Aware-Roles|Context-Aware Roles]]
- [[46-ABAC-Policies|ABAC Policies]] (Attribute-Based Access Control)

#### Entity Hierarchy (EnterpriseRBAC)
- [[50-Entity-System|Entity System Overview]]
- [[51-Entity-Types|Entity Types]] (STRUCTURAL vs ACCESS_GROUP)
- [[52-Entity-Hierarchy|Entity Hierarchy]]
- [[53-Closure-Table|Closure Table Pattern]]
- [[54-Entity-Memberships|Entity Memberships]]

### 🔧 API Reference

#### Presets
- [[60-SimpleRBAC-API|SimpleRBAC API Reference]]
- [[61-EnterpriseRBAC-API|EnterpriseRBAC API Reference]]

#### Services
- [[70-User-Service|UserService]] - User management
- [[71-Role-Service|RoleService]] - Role management
- [[72-Permission-Service|PermissionService]] - Permission checking
- [[73-API-Key-Service|ApiKeyService]] - API key management
- [[74-Auth-Service|AuthService]] - Authentication logic
- [[75-Entity-Service|EntityService]] - Entity hierarchy (EnterpriseRBAC)

#### Dependencies
- [[80-Auth-Dependencies|AuthDeps]] - FastAPI dependency injection
- [[81-Require-Auth|require_auth()]] - Require authenticated user
- [[82-Require-Permission|require_permission()]] - Require specific permission
- [[83-Require-Role|require_role()]] - Require specific role

#### Router Factories
- [[90-Router-Factories-Overview|Router Factories Overview]]
- [[91-Auth-Router|get_auth_router()]] - Login/register/refresh
- [[92-Users-Router|get_users_router()]] - User profile management
- [[93-API-Keys-Router|get_api_keys_router()]] - API key management
- [[94-OAuth-Router|get_oauth_router()]] - OAuth authentication
- [[95-OAuth-Associate-Router|get_oauth_associate_router()]] - Account linking

### 🎨 Patterns & Best Practices

#### Design Patterns
- [[100-Transport-Strategy-Pattern|Transport/Strategy Pattern]] (DD-038)
- [[101-Dynamic-Dependencies|Dynamic Dependency Injection]] (DD-039)
- [[102-Lifecycle-Hooks|Lifecycle Hooks Pattern]] (DD-040)
- [[103-Router-Factory-Pattern|Router Factory Pattern]] (DD-041)
- [[104-JWT-State-Tokens|JWT State Tokens]] (DD-042)

#### Best Practices
- [[110-Security-Best-Practices|Security Best Practices]]
- [[111-Performance-Optimization|Performance Optimization]]
- [[112-Error-Handling|Error Handling]]
- [[113-Testing-Strategies|Testing Strategies]]
- [[114-Deployment-Guide|Deployment Guide]]

### 🔌 Advanced Features

#### Caching & Performance
- [[120-Redis-Integration|Redis Integration]]
- [[121-Cache-Strategies|Cache Strategies]]
- [[122-Redis-Counters|Redis Counters]] (DD-033)
- [[123-Redis-Pub-Sub|Redis Pub/Sub Cache Invalidation]] (DD-037)

#### Lifecycle Hooks
- [[130-Hooks-Overview|Lifecycle Hooks Overview]]
- [[131-User-Hooks|User Lifecycle Hooks]] (13 hooks)
- [[132-Role-Hooks|Role Lifecycle Hooks]] (7 hooks)
- [[133-API-Key-Hooks|API Key Lifecycle Hooks]] (6 hooks)
- [[134-Custom-Hooks|Creating Custom Hooks]]

#### Notifications (v1.1)
- [[140-Notification-System|Notification System Overview]]
- [[141-Email-Notifications|Email Notifications]]
- [[142-SMS-Notifications|SMS Notifications]]
- [[143-Webhook-Notifications|Webhook Notifications]]

### 📖 Guides & Tutorials

#### Tutorials
- [[150-Tutorial-Simple-App|Tutorial: Simple RBAC App]]
- [[151-Tutorial-Enterprise-App|Tutorial: Enterprise Hierarchical App]]
- [[152-Tutorial-OAuth-Integration|Tutorial: Adding OAuth Login]]
- [[153-Tutorial-API-Keys|Tutorial: API Key Authentication]]
- [[154-Tutorial-Custom-Hooks|Tutorial: Custom Lifecycle Hooks]]

#### How-To Guides
- [[160-How-To-Migrate|How to Migrate from Centralized API]]
- [[161-How-To-Custom-Permissions|How to Create Custom Permissions]]
- [[162-How-To-Multi-Tenant|How to Implement Multi-Tenancy]]
- [[163-How-To-Rate-Limiting|How to Add Rate Limiting]]
- [[164-How-To-Audit-Logging|How to Implement Audit Logging]]

#### Migration Guides
- [[170-Migration-From-FastAPI-Users|Migration from FastAPI-Users]]
- [[171-Migration-From-AuthLib|Migration from AuthLib]]
- [[172-Migration-Version-Guide|Version Migration Guide]]

### 🔬 Deep Dives

#### Technical Deep Dives
- [[180-Deep-Dive-Permissions|Deep Dive: Permission Resolution]]
- [[181-Deep-Dive-Tree-Permissions|Deep Dive: Tree Permission Algorithm]]
- [[182-Deep-Dive-Closure-Table|Deep Dive: Closure Table Performance]]
- [[183-Deep-Dive-JWT|Deep Dive: JWT Token Management]]
- [[184-Deep-Dive-OAuth|Deep Dive: OAuth Flow Implementation]]

### 📐 Design Decisions

#### Core Decisions (DD-001 to DD-014)
- [[200-Design-Decisions-Core|Core Design Decisions]]
  - DD-001: Library vs Centralized Service
  - DD-002: Multi-Tenant Support
  - DD-003: Two Presets (SimpleRBAC, EnterpriseRBAC)
  - DD-004: MongoDB + Beanie ODM

#### Authentication Decisions (DD-015 to DD-027)
- [[201-Design-Decisions-Auth|Authentication Design Decisions]]
  - DD-028: API Keys with argon2id
  - DD-029: API Key Prefixes
  - DD-034: JWT Service Tokens

#### FastAPI-Users Patterns (DD-038 to DD-046)
- [[202-Design-Decisions-FastAPI-Users|FastAPI-Users Pattern Integration]]
  - DD-038: Transport/Strategy Pattern
  - DD-039: Dynamic Dependencies (makefun)
  - DD-040: Lifecycle Hooks
  - DD-041: Router Factory Pattern
  - DD-042: JWT State Tokens
  - DD-043: OAuth Router Factory
  - DD-044: OAuth Associate Router
  - DD-045: httpx-oauth Integration
  - DD-046: associate_by_email Security

### 🧪 Testing

- [[210-Testing-Overview|Testing Overview]]
- [[211-Unit-Testing|Unit Testing Guide]]
- [[212-Integration-Testing|Integration Testing Guide]]
- [[213-Test-Fixtures|Test Fixtures & Mocks]]
- [[214-Test-Coverage|Test Coverage Reports]]

### 🚀 Deployment

- [[220-Deployment-Overview|Deployment Overview]]
- [[221-Docker-Deployment|Docker Deployment]]
- [[222-Kubernetes-Deployment|Kubernetes Deployment]]
- [[223-Production-Checklist|Production Checklist]]
- [[224-Monitoring|Monitoring & Observability]]

### 🔧 Development

- [[230-Development-Setup|Development Setup]]
- [[231-Contributing-Guide|Contributing Guide]]
- [[232-Code-Style|Code Style Guide]]
- [[233-Release-Process|Release Process]]

### 📚 Reference

#### API Reference
- [[240-API-Reference-Index|API Reference Index]]
- [[241-Models-Reference|Models Reference]]
- [[242-Schemas-Reference|Schemas Reference]]
- [[243-Exceptions-Reference|Exceptions Reference]]

#### Comparisons
- [[250-Comparison-FastAPI-Users|vs FastAPI-Users]]
- [[251-Comparison-AuthLib|vs AuthLib]]
- [[252-Feature-Matrix|Feature Comparison Matrix]]

### 📝 Appendices

- [[260-Glossary|Glossary of Terms]]
- [[261-FAQ|Frequently Asked Questions]]
- [[262-Troubleshooting|Troubleshooting Guide]]
- [[263-Changelog|Changelog]]
- [[264-Roadmap|Development Roadmap]]
- [[265-License|License & Credits]]

---

## 🗺️ Navigation Tips

### For New Users
Start here:
1. [[01-Introduction|Introduction]]
2. [[02-Quick-Start|Quick Start]]
3. [[04-Basic-Concepts|Basic Concepts]]
4. Choose your preset: [[41-SimpleRBAC|SimpleRBAC]] or [[42-EnterpriseRBAC|EnterpriseRBAC]]

### For Developers Migrating
Check out:
- [[170-Migration-From-FastAPI-Users|Migration from FastAPI-Users]]
- [[250-Comparison-FastAPI-Users|vs FastAPI-Users Comparison]]
- [[160-How-To-Migrate|Migration Guide]]

### For OAuth Integration
Follow this path:
1. [[30-OAuth-Overview|OAuth Overview]]
2. [[31-OAuth-Setup|OAuth Setup Guide]]
3. [[94-OAuth-Router|OAuth Router]]
4. [[152-Tutorial-OAuth-Integration|OAuth Tutorial]]

### For Enterprise Features
Explore:
- [[42-EnterpriseRBAC|EnterpriseRBAC]]
- [[50-Entity-System|Entity System]]
- [[44-Tree-Permissions|Tree Permissions]]
- [[151-Tutorial-Enterprise-App|Enterprise Tutorial]]

---

## 📖 Documentation Conventions

### Code Examples
All code examples are tested and production-ready unless marked as pseudocode.

### Version Tags
- 🟢 **Core v1.0**: Available now
- 🟡 **v1.1**: In development
- 🔵 **v1.2+**: Planned features

### Navigation
- Use `[[Page-Name]]` for internal links
- Use headers for quick navigation within pages
- Use tags for cross-referencing: #authentication #authorization #oauth

---

## 🤝 Contributing to Documentation

Found an error? Want to improve the docs?

1. Documentation lives in `docs-library/`
2. Follow the naming convention: `##-Descriptive-Name.md`
3. Use Obsidian-style `[[links]]` for cross-references
4. Include code examples where possible
5. Add to this TOC when creating new pages

---

**Related Documents**:
- Original design docs: `docs/` (for library redesign context)
- Implementation status: [[IMPLEMENTATION_STATUS]]
- Design decisions log: `docs/DESIGN_DECISIONS.md`

**External Resources**:
- GitHub Repository: https://github.com/outlabsio/outlabsAuth
- FastAPI Documentation: https://fastapi.tiangolo.com/
- httpx-oauth Docs: https://frankie567.github.io/httpx-oauth/
