# Consumer Pin Audit

`scripts/verify_consumer_pins.py` is a source-owned release tool for operators
who maintain multiple applications that consume OutlabsAuth. It fails closed
unless every configured application has:

- the expected Git origin, with no duplicate repository paths or origins;
- exactly one direct `outlabs-auth==X.Y.Z` dependency in `pyproject.toml`;
- the same exact direct specifier in the editable or virtual root package in
  `uv.lock`;
- exactly one resolved `outlabs-auth` package at that version from PyPI; and
- when configured, the trusted wheel and sdist SHA-256 values in the lock.

The inventory belongs in the operator's private deployment repository. Do not
put private consumer names, repository paths, or deployment topology in this
public repository.

## Configuration

```toml
schema_version = 1
package = "outlabs-auth"
expected_version = "0.1.0a33"
expected_consumer_count = 2
workspace_root = ".."
expected_registry = "https://pypi.org/simple"

[artifacts]
wheel_sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
sdist_sha256 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

[[consumers]]
id = "service-alpha"
repo = "service-alpha"
origin = "github.com/example/service-alpha"
manifest = "pyproject.toml"
lock = "uv.lock"

[[consumers]]
id = "service-beta-api"
repo = "service-beta"
origin = "git@github.com:example/service-beta.git"
manifest = "apps/api/pyproject.toml"
lock = "apps/api/uv.lock"
```

Paths are resolved from `workspace_root`, which is itself relative to the
configuration file. Operators can override it for another machine:

```bash
uv run python scripts/verify_consumer_pins.py \
  --config ../deployment-ops/config/outlabs-auth-consumers.toml \
  --workspace-root /srv/source
```

Use `--json` for CI or archived rollout evidence. Exit status is `0` when all
consumers pass, `1` for consumer validation failures, and `2` for an invalid or
incomplete matrix.

Run the audit after the release is public and each lock has been regenerated
from the public index. This is a downstream rollout gate; it does not replace
the library's package build, migration rehearsal, or API integration tests.
