---
description: Start OutlabsAuth UI (sibling Nuxt console)
---

Start the sister admin console [OutlabsAuthUI](https://github.com/outlabsio/OutlabsAuthUI)
(Nuxt 4 + Nuxt UI static SPA; needs Bun 1.3.3+ and Node.js 22.18+):

1. From the **outlabsAuth repo root**, run in background:

```bash
cd ../OutlabsAuthUI
bun install
cp -n public/app-config.template.json public/app-config.json || true
bun run dev
```

2. Confirm the Nuxt dev server is listening on `http://localhost:3000` (the console origin
   both examples allow in CORS).

3. Ensure `public/app-config.json` (untracked) matches your API:

- EnterpriseRBAC example: `apiBaseUrl` `http://localhost:8004`, `authApiPrefix` `/v1`,
  `frontendProfileKey` `console` (the template's values)
- SimpleRBAC example: `apiBaseUrl` `http://localhost:8003`, `authApiPrefix` `/v1`, and remove
  `frontendProfileKey` (that example declares no frontend profiles)

Start an example API first (`/start-simple` or `/start-enterprise`, or uvicorn in
`examples/`). The UI discovers Simple vs Enterprise via `GET {authApiPrefix}/auth/config`.

Details: `docs/AUTH_UI.md` in this repo.
