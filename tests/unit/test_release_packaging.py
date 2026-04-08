from __future__ import annotations

import tomllib
from pathlib import Path

from outlabs_auth import __release_stage__, __version__
from outlabs_auth.cli import ALEMBIC_VERSION_TABLE, _resolve_alembic_ini
from outlabs_auth.release_versioning import parse_release_version


def test_pyproject_uses_dynamic_version_file():
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())

    assert data["project"]["dynamic"] == ["version"]
    assert data["tool"]["hatch"]["version"]["path"] == "outlabs_auth/_version.py"


def test_pyproject_exposes_public_package_metadata():
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())

    assert data["project"]["name"] == "outlabs-auth"
    assert data["project"]["authors"][0]["name"] == "OUTLABS LLC"
    assert data["project"]["license"]["file"] == "LICENSE"
    assert data["project"]["urls"]["Repository"] == "https://github.com/outlabsio/outlabsAuth"


def test_sdist_is_limited_to_library_files():
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())

    assert data["tool"]["hatch"]["build"]["targets"]["sdist"]["only-include"] == ["outlabs_auth"]


def test_package_version_file_is_publicly_exposed():
    version_file = Path(__file__).resolve().parents[2] / "outlabs_auth" / "_version.py"
    assert f'__version__ = "{__version__}"' in version_file.read_text()
    assert parse_release_version(__version__).release_stage == __release_stage__


def test_public_root_exports_core_library_surface():
    import outlabs_auth as package

    assert package.__author__ == "OUTLABS LLC"
    assert package.__license__ == "MIT"
    for name in (
        "OutlabsAuth",
        "SimpleRBAC",
        "EnterpriseRBAC",
        "AuthConfig",
        "SimpleConfig",
        "EnterpriseConfig",
        "AuthDeps",
        "create_auth_deps",
        "ResourceContextMiddleware",
        "register_exception_handlers",
    ):
        assert hasattr(package, name)


def test_cli_prefers_bundled_alembic_config():
    resolved = _resolve_alembic_ini()

    assert resolved.name == "alembic.ini"
    assert resolved.parent.name == "outlabs_auth"
    assert "driver://user:pass@localhost/dbname" in resolved.read_text()


def test_cli_uses_namespaced_alembic_version_table():
    assert ALEMBIC_VERSION_TABLE == "outlabs_auth_alembic_version"


def test_cli_can_resolve_local_alembic_config_for_maintainers(tmp_path, monkeypatch):
    local_alembic = tmp_path / "alembic.ini"
    local_alembic.write_text("[alembic]\nscript_location = migrations\n")
    monkeypatch.chdir(tmp_path)

    resolved = _resolve_alembic_ini(require_local=True)

    assert resolved.name == "alembic.ini"
    assert resolved == local_alembic


def test_readme_tracks_current_release_metadata():
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text()
    release = parse_release_version(__version__)

    assert f"**Current Library Version**: {__version__}" in readme
    assert f"**Release Stage**: {release.stage_display}" in readme
    assert "pip install outlabs-auth" in readme
    assert "https://github.com/outlabsio/outlabsAuth" in readme
    assert "MIT" in readme


def test_release_guide_references_release_helper_ci_and_pypi_publish():
    release_guide = (Path(__file__).resolve().parents[2] / "docs" / "PRIVATE_RELEASE.md").read_text()

    assert "uv run python scripts/release_version.py set X.Y.ZaN" in release_guide
    assert "uv run python scripts/release_version.py check" in release_guide
    assert "Release Readiness" in release_guide
    assert "Publish PyPI" in release_guide
    assert "pypa/gh-action-pypi-publish@release/v1" in release_guide


def test_publish_workflow_uses_trusted_publishing():
    workflow = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "publish-pypi.yml").read_text()

    assert 'tags:\n      - "v*"' in workflow
    assert "id-token: write" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
