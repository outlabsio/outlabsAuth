---
description: Start auth-ui frontend on port 3000
---

Start the auth-ui Nuxt frontend with Bun:

1. Run in background from project root:
   ```bash
   cd auth-ui && bun run dev
   ```
2. Confirm it's running by checking the output shows Nuxt started on port 3000

Note: Requires an API running on port 8000 (use /start-simple or /start-enterprise first).
The frontend auto-detects SimpleRBAC vs EnterpriseRBAC mode via the /v1/auth/config endpoint.
