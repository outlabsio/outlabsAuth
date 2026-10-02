# UI Parity Tracking Moved

Frontend capability tracking lives in the sister repository
[OutlabsAuthUI](https://github.com/outlabsio/OutlabsAuthUI) (a Nuxt 4 + Nuxt UI static
SPA), not in this Python package. Its
[`CAPABILITIES.md`](https://github.com/outlabsio/OutlabsAuthUI/blob/main/CAPABILITIES.md)
records, per backend capability, whether the console has it built, partial or missing;
rows marked "backend" name the library or example change they wait on.

Use that repository for:

- UI build, test and release-gate status
- frontend/backend contract reconciliation
- remaining UI capability gaps

This backend repository retains backend-side contract tests and documentation for
the API surface the UI consumes (`docs/AUTH_UI.md`, OpenAPI on the examples).
