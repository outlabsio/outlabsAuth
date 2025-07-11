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

### 🏢 [Platform Scenarios](./PLATFORM_SCENARIOS.md)
Real-world deployment scenarios showing how different business models use outlabsAuth:
- Complex hierarchical organizations (Diverse)
- Simple flat platforms (uaya)
- Multi-sided marketplaces (qdarte)
- Hybrid optional hierarchies (Referral Brokerage)

### 🚀 Platform Integration Documentation

#### [Platform Setup Guide](./PLATFORM_SETUP_GUIDE.md)
Complete guide for setting up a new platform from scratch, including:
- Initial platform creation
- Permission and role configuration
- Entity structure setup
- Administrator onboarding

#### [API Integration Patterns](./API_INTEGRATION_PATTERNS.md)
Common patterns and best practices for integrating with outlabsAuth:
- Authentication flows
- Permission checking patterns
- Entity management
- Performance optimization

#### [Platform Integration: Diverse](./PLATFORM_INTEGRATION_DIVERSE.md)
Detailed real-world example showing how Diverse (a complex real estate platform) integrates with outlabsAuth:
- Business requirements mapping
- User journey scenarios
- Implementation examples
- Best practices

#### [Admin Access Levels](./ADMIN_ACCESS_LEVELS.md)
How different administrative levels access the outlabsAuth Admin UI:
- System, Platform, Organization, and Team admin levels
- Permission-based UI adaptation
- Scoped data access
- Implementation guide

#### [Entity Type Flexibility Changes](./ENTITY_TYPE_FLEXIBILITY_CHANGES.md) 🆕
Documentation of the architectural changes that allow flexible entity naming:
- Motivation and benefits  
- Technical changes made
- Entity type autocomplete feature
- Migration notes
- Best practices

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
The organizational structure within platforms. Two classes with flexible types:
- **Structural Entities**: Forms the organizational hierarchy
  - Flexible types: organization, division, department, region, office, team, or any custom type
  - Can contain other structural entities or access groups
- **Access Groups**: Cross-cutting permission groups
  - Flexible types: admin_group, viewer_group, project_team, committee, or any custom type
  - Can only contain other access groups

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