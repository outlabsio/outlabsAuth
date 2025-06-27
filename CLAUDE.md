# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

outlabsAuth is an enterprise-grade Role-Based Access Control (RBAC) authentication platform built with FastAPI, MongoDB, and Beanie ODM. It features a unique three-tier hierarchical permission system with automatic inheritance and multi-tenant support.

## Essential Commands

### Development
```bash
# Setup and dependencies
uv sync                              # Install all dependencies
uv sync --extra stress               # Include stress testing dependencies

# Run the application
uv run uvicorn api.main:app --reload # Start FastAPI dev server on port 8030

# Testing - ALWAYS run tests before committing
uv run pytest                        # Run all tests (should have 98%+ pass rate)
uv run pytest tests/test_auth_routes.py::test_login # Run specific test
uv run pytest -k "test_user"         # Run tests matching pattern
uv run pytest -v                     # Verbose output

# Code quality checks - MUST pass before changes are complete
uv run black .                       # Format code
uv run isort .                       # Sort imports
uv run flake8 .                      # Linting
uv run mypy .                        # Type checking

# Database seeding
uv run python scripts/seed_test_environment.py # Seed test data
```

### Docker
```bash
docker compose up -d --build         # Build and start all services
docker compose logs -f api           # View API logs
docker compose down -v               # Stop and remove volumes
```

## Architecture & Key Concepts

### Hierarchical Permission System
The permission system has automatic inheritance where "manage" permissions include "read":

1. **System Level** (`*:manage_all`): Global platform administration
   - Example: `user:manage_all` automatically includes `user:read_all`
   
2. **Platform Level** (`*:manage_platform`): Cross-client operations
   - Example: `client:manage_platform` for managing multiple clients
   
3. **Client Level** (`*:manage_client`): Organization-specific management
   - Example: `user:manage_client` for managing users within a client
   
4. **Self-Access Level**: Individual user operations (automatic)

### Multi-Tenant Architecture
- **Complete isolation**: All operations are automatically filtered by client_id
- **Platform staff**: Can manage multiple clients with platform-level permissions
- **Client context**: Every request includes client_id validation
- **Data boundaries**: Never mix data between different client organizations

### Service Layer Pattern
```
routes/ → services/ → models/
```
- **Routes**: Handle HTTP requests, validation, and responses
- **Services**: Business logic, permission checks, database operations
- **Models**: Beanie ODM documents with type safety

### Authentication Flow
1. Login creates JWT access token (15 min) and refresh token (30 days)
2. Refresh tokens support multi-device sessions
3. Logout revokes specific refresh tokens
4. Rate limiting prevents brute force attacks

## Critical Implementation Notes

### Permission Checks
Always use the hierarchical permission checker:
```python
from api.dependencies import check_hierarchical_permissions

# In routes
@router.post("/", dependencies=[Depends(check_hierarchical_permissions("user:manage"))])
```

### Database Operations
- Use Beanie's async methods: `await User.find_all()`, `await user.save()`
- Always filter by client_id for multi-tenant queries
- Use transactions for multi-document operations

### Testing Requirements
- Maintain 98%+ test success rate
- Use fixtures from conftest.py for consistent test data
- Test both success and error cases
- Verify permission boundaries in all tests

### Error Handling
- Use FastAPI's HTTPException with appropriate status codes
- Include descriptive error messages
- Log security-related errors (failed logins, permission denials)

## File Structure

```
api/
├── models/          # Beanie ODM models (always inherit from BaseDocument)
├── routes/          # FastAPI endpoints (use dependency injection)
├── services/        # Business logic (handle permissions here)
├── schemas/         # Pydantic models for request/response
├── middleware/      # Rate limiting, CORS, etc.
└── dependencies.py  # Auth helpers, permission checkers

tests/
├── conftest.py      # Shared fixtures (test users, roles, etc.)
├── test_*_routes.py # API endpoint tests
└── test_*_service.py # Service layer tests
```

## Common Development Tasks

### Adding a New Endpoint
1. Define Pydantic schemas in `schemas/`
2. Implement service logic in `services/`
3. Create route in `routes/` with proper permission dependencies
4. Add comprehensive tests covering success/error cases
5. Update route documentation in `docs/routes/`

### Modifying Permissions
1. Update permission definitions in the service layer
2. Ensure hierarchical inheritance is maintained
3. Test all affected permission levels
4. Verify multi-tenant isolation remains intact

### Database Schema Changes
1. Update Beanie model in `models/`
2. Consider migration strategy for existing data
3. Update related services and routes
4. Add tests for new fields/behaviors

## Environment Variables

Key variables for local development:
- `DATABASE_URL`: MongoDB connection string
- `MONGO_DATABASE`: Database name (default: outlabs_auth)
- `SECRET_KEY`: JWT signing key
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Default 15
- `REFRESH_TOKEN_EXPIRE_DAYS`: Default 30