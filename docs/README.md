# outlabsAuth Documentation

Welcome to the outlabsAuth documentation. This authentication and authorization platform provides enterprise-grade identity management for multiple platforms and applications.

## What is outlabsAuth?

outlabsAuth is a centralized authentication and authorization service that handles:
- User authentication (login/logout)
- Permission management
- Organizational structures
- Multi-platform support

It does **NOT** handle business logic - it purely manages who can access what.

## Documentation Structure

### 📋 [Project Overview](./PROJECT_OVERVIEW.md)
Start here to understand what outlabsAuth is, how it works, and why it's designed this way.

### 🏗️ [Architecture Guide](./ARCHITECTURE.md)
Deep dive into the technical architecture, including:
- System components
- Data models
- Security architecture
- Integration patterns

### 🔌 [API Specification](./API_SPECIFICATION.md)
Complete API reference including:
- Authentication endpoints
- User management
- Entity management
- Permission checking

### 🚀 [Integration Guide](./INTEGRATION_GUIDE.md)
Step-by-step guide to integrate your platform:
- Quick start examples
- Best practices
- Common patterns
- Troubleshooting

### 📐 [Architecture Plan](../MAIN_REFACTOR_PLAN.md)
Detailed plan for the unified Entity model architecture (for developers working on outlabsAuth itself).

## Quick Links

- **For Platform Developers**: Start with the [Integration Guide](./INTEGRATION_GUIDE.md)
- **For System Architects**: Review the [Architecture Guide](./ARCHITECTURE.md)
- **For API Reference**: See the [API Specification](./API_SPECIFICATION.md)
- **For Project Context**: Read the [Project Overview](./PROJECT_OVERVIEW.md)

## Key Concepts

### Platforms
Independent applications that use outlabsAuth for authentication (e.g., Diverse Leads, uaya, qdarte).

### Entities
The organizational structure within platforms. Two types:
- **Structural Entities**: Organizations, branches, teams
- **Access Groups**: Functional groups, permission groups, project teams

### Permissions
Granular access controls (e.g., `lead:read`, `user:create`) that determine what actions users can perform.

### Roles
Collections of permissions that can be assigned to users within entity contexts.

## Getting Started

1. **Platform Registration**: Contact administrators to register your platform
2. **Review Documentation**: Understand the architecture and API
3. **Implement Integration**: Follow the integration guide for your platform type
4. **Test Thoroughly**: Ensure authentication and permissions work correctly

## Support

- GitHub Issues: [github.com/outlabs/outlabsAuth/issues](https://github.com/outlabs/outlabsAuth/issues)
- Email: auth-support@outlabs.com
- Documentation Updates: Submit PRs to improve these docs