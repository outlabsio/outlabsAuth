# System Specification Documentation

This directory contains **design specifications and architectural decisions** for maintainers and contributors.

## For Library Users
Looking for usage documentation? See **[docs-library/](../docs-library/)** instead.

## Design Documents

### Core Vision
- **REDESIGN_VISION.md** - Project vision and architectural approach
- **LIBRARY_ARCHITECTURE.md** - Technical architecture details
- **IMPLEMENTATION_ROADMAP.md** - Development phases and timeline
- **ENTITY_AUTHORIZATION_ROLE_ONLY.md** - Decision memo for role-only entity authorization

### Design Decisions
- **DESIGN_DECISIONS.md** - Complete record of architectural decisions (DD-001 to DD-037+)
- **CURRENT_IMPLEMENTATION_STATUS.md** - Current delivered slices, accepted implementation nuances, and known remaining gaps
- **COMPARISON_MATRIX.md** - SimpleRBAC vs EnterpriseRBAC feature comparison

### API & Integration
- **API_DESIGN.md** - Library API design and developer experience
- **DEPENDENCY_PATTERNS.md** - FastAPI dependency injection patterns
- **AUTH_UI.md** - External admin UI repository location and repo boundary

### Operational
- **SECURITY.md** - Security hardening requirements
- **DEPLOYMENT_GUIDE.md** - Production deployment specifications
- **PRIVATE_RELEASE.md** - Private package release workflow for `uv`
- **TESTING_GUIDE.md** - Testing strategy and coverage goals

### Extensions
- **AUTH_EXTENSIONS.md** - Optional features (OAuth, MFA, passwordless)
- **ERROR_HANDLING.md** - Exception hierarchy specification
- **MIGRATION_GUIDE.md** - Migration from centralized API

---

**Note**: These are planning/specification documents. Actual implementation may differ - always check the code and `docs-library/` for current behavior.
