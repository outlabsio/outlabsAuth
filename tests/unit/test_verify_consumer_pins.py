from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from scripts.verify_consumer_pins import ConfigurationError, audit_matrix, main

WHEEL_HASH = hashlib.sha256(b"wheel").hexdigest()
SDIST_HASH = hashlib.sha256(b"sdist").hexdigest()


def _write_repo(
    workspace: Path,
    name: str,
    *,
    origin: str,
    version: str = "0.1.0a33",
    manifest_requirement: str | None = None,
    lock_specifier: str | None = None,
    lock_version: str | None = None,
    manifest: str = "pyproject.toml",
    lock: str = "uv.lock",
    registry: str = "https://pypi.org/simple",
) -> None:
    repo = workspace / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", origin], check=True)
    manifest_path = repo / manifest
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    requirement = manifest_requirement or f"outlabs-auth=={version}"
    manifest_path.write_text(
        f'[project]\nname = "{name}"\nversion = "1.0.0"\ndependencies = ["{requirement}"]\n',
        encoding="utf-8",
    )
    lock_path = repo / lock
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    locked_version = lock_version or version
    specifier = lock_specifier or f"=={version}"
    lock_path.write_text(
        "\n".join(
            [
                "version = 1",
                "revision = 1",
                'requires-python = ">=3.12"',
                "",
                "[[package]]",
                'name = "outlabs-auth"',
                f'version = "{locked_version}"',
                f'source = {{ registry = "{registry}" }}',
                f'sdist = {{ url = "https://example.invalid/pkg.tar.gz", hash = "sha256:{SDIST_HASH}" }}',
                "wheels = [",
                f'    {{ url = "https://example.invalid/pkg.whl", hash = "sha256:{WHEEL_HASH}" }},',
                "]",
                "",
                "[[package]]",
                f'name = "{name}"',
                'version = "1.0.0"',
                'source = { editable = "." }',
                "",
                "[package.metadata]",
                "requires-dist = [",
                f'    {{ name = "outlabs-auth", specifier = "{specifier}" }},',
                "]",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_config(ops: Path, consumers: list[dict[str, str]], expected_count: int | None = None) -> Path:
    lines = [
        "schema_version = 1",
        'package = "outlabs-auth"',
        'expected_version = "0.1.0a33"',
        f"expected_consumer_count = {expected_count if expected_count is not None else len(consumers)}",
        'workspace_root = "../workspace"',
        'expected_registry = "https://pypi.org/simple"',
        "",
        "[artifacts]",
        f'wheel_sha256 = "{WHEEL_HASH}"',
        f'sdist_sha256 = "{SDIST_HASH}"',
    ]
    for consumer in consumers:
        lines.extend(
            [
                "",
                "[[consumers]]",
                f'id = "{consumer["id"]}"',
                f'repo = "{consumer["repo"]}"',
                f'origin = "{consumer["origin"]}"',
                f'manifest = "{consumer.get("manifest", "pyproject.toml")}"',
                f'lock = "{consumer.get("lock", "uv.lock")}"',
            ]
        )
    config = ops / "consumer-matrix.toml"
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config


def test_audit_accepts_exact_pins_hashes_nested_paths_and_origin_forms(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    ops = tmp_path / "ops"
    workspace.mkdir()
    ops.mkdir()
    _write_repo(workspace, "service-alpha", origin="git@github.com:acme/service-alpha.git")
    _write_repo(
        workspace,
        "service-beta",
        origin="https://github.com/acme/service-beta.git",
        manifest="apps/api/pyproject.toml",
        lock="apps/api/uv.lock",
    )
    config = _write_config(
        ops,
        [
            {"id": "alpha", "repo": "service-alpha", "origin": "https://github.com/acme/service-alpha"},
            {
                "id": "beta",
                "repo": "service-beta",
                "origin": "github.com/acme/service-beta",
                "manifest": "apps/api/pyproject.toml",
                "lock": "apps/api/uv.lock",
            },
        ],
    )

    result = audit_matrix(config)

    assert result.ok is True
    assert [consumer.id for consumer in result.consumers] == ["alpha", "beta"]
    assert all(consumer.manifest_pin == "0.1.0a33" for consumer in result.consumers)
    assert all(consumer.lock_version == "0.1.0a33" for consumer in result.consumers)


@pytest.mark.parametrize(
    ("overrides", "expected_error"),
    [
        ({"manifest_requirement": "outlabs-auth>=0.1.0a33,<0.2"}, "manifest dependency is not an exact"),
        ({"lock_specifier": ">=0.1.0a33,<0.2"}, "root lock requirement is not an exact"),
        ({"lock_version": "0.1.0a32"}, "lock resolves '0.1.0a32'"),
        ({"registry": "https://example.invalid/simple"}, "lock source must be"),
    ],
)
def test_audit_rejects_non_immutable_consumer_state(
    tmp_path: Path, overrides: dict[str, str], expected_error: str
) -> None:
    workspace = tmp_path / "workspace"
    ops = tmp_path / "ops"
    workspace.mkdir()
    ops.mkdir()
    _write_repo(workspace, "service-alpha", origin="git@github.com:acme/service-alpha.git", **overrides)
    config = _write_config(
        ops,
        [{"id": "alpha", "repo": "service-alpha", "origin": "github.com/acme/service-alpha"}],
    )

    result = audit_matrix(config)

    assert result.ok is False
    assert any(expected_error in error for error in result.consumers[0].errors)


def test_audit_rejects_wrong_artifact_hashes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    ops = tmp_path / "ops"
    workspace.mkdir()
    ops.mkdir()
    _write_repo(workspace, "service-alpha", origin="git@github.com:acme/service-alpha.git")
    config = _write_config(
        ops,
        [{"id": "alpha", "repo": "service-alpha", "origin": "github.com/acme/service-alpha"}],
    )
    config.write_text(config.read_text().replace(WHEEL_HASH, "0" * 64), encoding="utf-8")

    result = audit_matrix(config)

    assert result.ok is False
    assert "trusted wheel SHA-256 is absent from the lock" in result.consumers[0].errors


def test_audit_rejects_duplicate_repository_identity(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    ops = tmp_path / "ops"
    workspace.mkdir()
    ops.mkdir()
    _write_repo(workspace, "service-alpha", origin="git@github.com:acme/service-alpha.git")
    config = _write_config(
        ops,
        [
            {"id": "alpha", "repo": "service-alpha", "origin": "github.com/acme/service-alpha"},
            {"id": "alias", "repo": "service-alpha", "origin": "github.com/acme/service-alias"},
        ],
    )

    with pytest.raises(ConfigurationError, match="duplicate consumer repository path"):
        audit_matrix(config)


def test_audit_rejects_incomplete_inventory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    ops = tmp_path / "ops"
    workspace.mkdir()
    ops.mkdir()
    _write_repo(workspace, "service-alpha", origin="git@github.com:acme/service-alpha.git")
    config = _write_config(
        ops,
        [{"id": "alpha", "repo": "service-alpha", "origin": "github.com/acme/service-alpha"}],
        expected_count=2,
    )

    with pytest.raises(ConfigurationError, match="expected 2 consumers"):
        audit_matrix(config)


def test_cli_returns_one_and_json_for_validation_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "workspace"
    ops = tmp_path / "ops"
    workspace.mkdir()
    ops.mkdir()
    _write_repo(
        workspace,
        "service-alpha",
        origin="git@github.com:acme/service-alpha.git",
        manifest_requirement="outlabs-auth>=0.1.0a33",
    )
    config = _write_config(
        ops,
        [{"id": "alpha", "repo": "service-alpha", "origin": "github.com/acme/service-alpha"}],
    )

    assert main(["--config", str(config), "--json"]) == 1
    payload = capsys.readouterr().out
    assert '"ok": false' in payload
    assert "manifest dependency is not an exact" in payload
