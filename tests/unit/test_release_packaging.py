from __future__ import annotations

import json
import tomllib
from pathlib import Path

from outlabs_auth import __release_stage__, __version__
from outlabs_auth.cli import _resolve_alembic_ini
from outlabs_auth.release_versioning import parse_release_version


def test_pyproject_uses_dynamic_version_file():
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())

    assert data["project"]["dynamic"] == ["version"]
    assert data["tool"]["hatch"]["version"]["path"] == "outlabs_auth/_version.py"


def test_package_version_file_is_publicly_exposed():
    version_file = Path(__file__).resolve().parents[2] / "outlabs_auth" / "_version.py"
    assert f'__version__ = "{__version__}"' in version_file.read_text()
    assert parse_release_version(__version__).release_stage == __release_stage__


def test_cli_prefers_bundled_alembic_config():
    resolved = _resolve_alembic_ini()

    assert resolved.name == "alembic.ini"
    assert resolved.parent.name == "outlabs_auth"


def test_cli_can_resolve_local_alembic_config_for_maintainers(tmp_path, monkeypatch):
    local_alembic = tmp_path / "alembic.ini"
    local_alembic.write_text("[alembic]\nscript_location = migrations\n")
    monkeypatch.chdir(tmp_path)

    resolved = _resolve_alembic_ini(require_local=True)

    assert resolved.name == "alembic.ini"
    assert resolved == local_alembic


def test_auth_ui_package_tracks_its_own_version_and_library_version():
    package_json = Path(__file__).resolve().parents[2] / "auth-ui" / "package.json"
    data = json.loads(package_json.read_text())
    release = parse_release_version(__version__)

    assert data["version"] == release.ui_version
    assert data["packageManager"] == "bun@1.3.3"
    assert data["outlabsAuth"]["libraryVersion"] == __version__
    assert data["outlabsAuth"]["releaseStage"] == __release_stage__


def test_auth_ui_readme_tracks_current_ui_version():
    auth_ui_readme = (Path(__file__).resolve().parents[2] / "auth-ui" / "README.md").read_text()
    release = parse_release_version(__version__)

    assert f"Current tracked UI version: `{release.ui_version}`" in auth_ui_readme


def test_readme_tracks_current_release_metadata():
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text()
    release = parse_release_version(__version__)

    assert f"**Current Library Version**: {__version__}" in readme
    assert f"**Current Admin UI Version**: {release.ui_version}" in readme
    assert f"**Release Stage**: {release.stage_display}" in readme
    assert f'dependencies = ["outlabs-auth{release.dependency_specifier}"]' in readme
    assert f'tag = "{release.git_tag}"' in readme


def test_private_release_doc_references_release_helper_and_ci():
    private_release_doc = (Path(__file__).resolve().parents[2] / "docs" / "PRIVATE_RELEASE.md").read_text()

    assert "uv run python scripts/release_version.py set X.Y.ZaN" in private_release_doc
    assert "uv run python scripts/release_version.py check" in private_release_doc
    assert "Release Readiness" in private_release_doc
