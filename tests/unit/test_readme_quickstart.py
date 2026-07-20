"""Execute the README quickstart, so it cannot rot into a lie.

It had rotted. The previous version failed twice before serving a request:
`secret_key="change-me"` is 9 characters and HS256 requires >= 32, so it raised
during construction; and it mounted routers at import while `auth.deps` only
exists after the async `initialize()`, so it raised again. Both examples/ apps
avoided both mistakes — the README contradicted the working code, and was the
first thing anyone read.

A string-matching test would not have caught either failure. This extracts the
first python block from the Quickstart section and runs it.

No database is touched: `create_async_engine` is lazy, so nothing here connects.
"""

import re
from pathlib import Path

import pytest

README = Path(__file__).resolve().parents[2] / "README.md"


def _quickstart_source() -> str:
    text = README.read_text()

    start = text.index("## Quickstart")
    end = text.index("##", start + len("## Quickstart"))
    section = text[start:end]

    blocks = re.findall(r"```python\n(.*?)```", section, re.DOTALL)
    assert blocks, "README Quickstart no longer contains a python block"
    return blocks[0]


@pytest.mark.unit
def test_readme_quickstart_executes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "r" * 48)

    namespace: dict = {}
    exec(compile(_quickstart_source(), str(README), "exec"), namespace)  # noqa: S102

    app = namespace.get("app")
    assert app is not None, "quickstart should define `app`"
    assert app.routes, "quickstart should mount the auth router"


@pytest.mark.unit
def test_readme_quickstart_uses_a_real_secret_key() -> None:
    """The exact failure that made the old quickstart unrunnable."""
    source = _quickstart_source()

    assert "secret_key=os.environ" in source, (
        "the quickstart must read secret_key from the environment; a literal "
        "placeholder under 32 chars raises at construction under HS256"
    )
    assert 'secret_key="change-me"' not in source


@pytest.mark.unit
def test_readme_quickstart_primes_before_mounting() -> None:
    """Mounting at import without priming raises; keep the ordering explicit."""
    source = _quickstart_source()

    assert "prime_fastapi_routing()" in source
    assert source.index("prime_fastapi_routing()") < source.index("include_router")
