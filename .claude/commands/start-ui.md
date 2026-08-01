---
description: Start OutlabsAuth UI (sibling Vite/React app)
---

Start the sister admin console [OutlabsAuthUI](https://github.com/outlabsio/OutlabsAuthUI):

1. From the **outlabsAuth repo root**, run in background:

```bash
cd ../OutlabsAuthUI
bun install
cp -n public/app-config.template.json public/app-config.json || true
bun run dev
```

2. Confirm Vite is listening (default `http://localhost:5173`).

3. Ensure `public/app-config.json` matches your API:

- SimpleRBAC example: `apiBaseUrl` `http://localhost:8003`, `authApiPrefix` `/v1`
- EnterpriseRBAC example: `apiBaseUrl` `http://localhost:8004`, `authApiPrefix` `/v1`

Start an example API first (`/start-simple` or `/start-enterprise`, or uvicorn in
`examples/`). The UI discovers Simple vs Enterprise via `GET {authApiPrefix}/auth/config`.

Details: `docs/AUTH_UI.md` in this repo.
