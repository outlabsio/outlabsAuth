# System Specification Documentation

This directory contains **design specifications and architectural decisions** for maintainers and contributors.

## For Library Users
Looking for usage documentation? See **[docs-library/](../docs-library/)** instead.

## Design Documents

### Architecture
- **LIBRARY_ARCHITECTURE.md** - Technical architecture details
- **ENTITY_AUTHORIZATION_ROLE_ONLY.md** - Decision memo for role-only entity authorization

### Design Decisions
- **DESIGN_DECISIONS.md** - Why the architecture is the way it is (DD-001 onward)
- **CURRENT_IMPLEMENTATION_STATUS.md** - Current delivered slices, accepted implementation nuances, and known remaining gaps
- **COMPARISON_MATRIX.md** - SimpleRBAC vs EnterpriseRBAC feature comparison

### API & Integration
- **API_DESIGN.md** - Library API design and developer experience
- **API_KEY_SCOPE_AND_GRANT_POLICY_EPIC.md** - In-progress entity-scoped API key grant model, current backend status, lifecycle rules, and remaining design follow-ups
- **DEPENDENCY_PATTERNS.md** - FastAPI dependency injection patterns
- **HOST_INTEGRATION_QUERIES.md** - Supported auth-owned query boundaries for embedded host applications
- **AUTH_UI.md** - External admin UI repository location and repo boundary

### Operational
- **SECURITY.md** - Security hardening requirements
- **DEPLOYMENT_GUIDE.md** - Production deployment specifications
- **PRIVATE_RELEASE.md** - Private package release workflow for `uv`
- **TESTING_GUIDE.md** - Testing strategy and coverage goals

### Extensions
- **AUTH_EXTENSIONS.md** - Optional features (OAuth, MFA, passwordless)
- **WHATSAPP_ACCOUNT_MESSAGING.md** - WhatsApp/OTP delivery via host-owned providers (intents vs NotificationService)
- **ERROR_HANDLING.md** - Exception hierarchy specification

---

**Note**: These describe the current system and were verified against the source on
2026-07-16. Where a doc and the code disagree, **the code wins** — and that is a bug in
the doc worth fixing rather than working around. The `examples/` are the reference
integration, and `README.md`'s quickstart is executed by a test.
