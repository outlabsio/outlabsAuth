# Canonical invitation receipt acceptance

12 October 2026. Unreleased a38 runtime `da830ba27e66448bc2f0fb9dd96fd07583efc14d`.
Auth schema remains `20261012_0031`. No publication or consumer adoption.

`UserService.send_invitation_email_result` returns the existing canonical
`MailDeliveryResult` from the same invitation composition/provider path.
The existing boolean method delegates to it and preserves its return contract.
Absent configuration produces an explicit skipped result. This enables durable
hosts to retain safe provider/message identities without introducing transport.

Actual HTTP acceptance caught two defects. SendGrid converted case-insensitive
headers to a lowercased plain dictionary and lost real `X-Message-Id` receipts;
the adapter now reads the original header collection case-insensitively. The
default invitation composer omitted logical delivery correlation; it now passes
only explicit logical delivery/source identifiers, excluding unrelated private
metadata. Correlation is not provider idempotency. Acceptance is not delivery.

Four regressions cover boolean/receipt compatibility, absent mail, lowercase
receipt headers and safe composer metadata. A host-local provider harness also
exercises actual HTTP acceptance, rejection and receipt loss through this same
adapter; no real provider account or recipient was contacted.

## Final local qualification

- Complete source: **1,651**, no failures/errors/skips, four file-disjoint shards
  (235/235/234/947) on fresh owned PostgreSQL, with required real Redis.
- Independent required Redis: **102**, no skips, unavailable Redis fails.
- Fresh noneditable wheel and sdist: **85 each**, no failures/errors/skips,
  including constructor/lifecycle and genuine public-a37 migration acceptance.
- Both installs match all **243** package files. Exact clean source `da830ba`:
  wheel SHA-256 `3b5b23b915c6381962f4358d9db3f19ffab161e35e75ad42afda1cbf85aeca31`;
  sdist `fcb041b844eb1704488722256d4088faa8649c4826f44cbda0a0e2aa62107404`.
- Changed Python Black, full Ruff and three touched runtime module types pass.
  Canonical handbook port `832253e` passes lint/types/build and rendered text.
  Inherited broad formatting drift is unchanged; no hosted CI gate.

Receipts: `~/Documents/tmp/recovery-provider-20261012/`:
`auth-final-complete-suite-receipt.json`, `auth-required-redis.xml`,
`installed-receipt.json`, `wheel-bytes.json`, `sdist-bytes.json`.
An earlier source run/build and initial harness failures are retained as
superseded development attempts; this final receipt binds the clean runtime.

The SDK does not reconcile provider UNKNOWN outcomes, verify actual provider
evidence/idempotency windows, own encryption keys, deploy recovery authority or
complete row-bound host writer permissions. Those remain host obligations.
Broader staff/group capacity, source/native writer qualification and exact a38
review/release/adoption remain independent exits.
