---
description: Start EnterpriseRBAC example API on port 8000
---

Start the EnterpriseRBAC real estate example API with hot reload:

1. Kill any process on port 8000 (silently, in case another API is running)
2. Run in background from project root:
   ```bash
   cd examples/enterprise_rbac && \
   DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/realestate_enterprise_rbac" \
   SECRET_KEY="enterprise-rbac-secret-key-change-in-production" \
   REDIS_URL="redis://localhost:6380" \
   uv run uvicorn main:app --port 8000 --reload
   ```
3. Confirm it's running by checking the output shows uvicorn started

Note: Library changes in `outlabs_auth/` will auto-reload thanks to the reload_dirs config.
