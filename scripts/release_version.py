from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from outlabs_auth.release_versioning import parse_release_version


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "outlabs_auth" / "_version.py"
PACKAGE_JSON = ROOT / "auth-ui" / "package.json"
README = ROOT / "README.md"
PRIVATE_RELEASE_DOC = ROOT / "docs" / "PRIVATE_RELEASE.md"


def _read_current_version() -> str:
    version_file = VERSION_FILE.read_text()
    match = re.search(r'^__version__ = "(?P<version>[^"]+)"$', version_file, re.MULTILINE)
    if not match:
        raise ValueError(f"Could not read __version__ from {VERSION_FILE}")
    return match.group("version")


def _replace_once(text: str, pattern: str, replacement: str, *, description: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"Failed to update {description}")
    return updated


def _expected_readme_fragments(version: str) -> dict[str, str]:
    release = parse_release_version(version)
    return {
        "stage_badge": (
            f"[![Stage: {release.stage_display}]"
            f"(https://img.shields.io/badge/stage-{release.release_stage}-{release.stage_badge_color}.svg)]"
            "(#development-status)"
        ),
        "dependency_example": f'dependencies = ["outlabs-auth{release.dependency_specifier}"]',
        "git_tag_example": f'tag = "{release.git_tag}"',
        "library_version": f"**Current Library Version**: {release.python_version}",
        "ui_version": f"**Current Admin UI Version**: {release.ui_version}",
        "release_stage": f"**Release Stage**: {release.stage_display}",
    }


def _write_version_file(version: str) -> None:
    release = parse_release_version(version)
    VERSION_FILE.write_text(
        "\n".join(
            [
                '"""Package version metadata."""',
                "",
                '__all__ = ["__release_stage__", "__version__"]',
                "",
                f'__release_stage__ = "{release.release_stage}"',
                f'__version__ = "{release.python_version}"',
                "",
            ]
        )
    )


def _write_package_json(version: str) -> None:
    release = parse_release_version(version)
    package_data = json.loads(PACKAGE_JSON.read_text())
    package_data["version"] = release.ui_version
    package_data["packageManager"] = "bun@1.3.3"
    package_data.setdefault("outlabsAuth", {})
    package_data["outlabsAuth"]["libraryVersion"] = release.python_version
    package_data["outlabsAuth"]["releaseStage"] = release.release_stage
    PACKAGE_JSON.write_text(f"{json.dumps(package_data, indent=2)}\n")


def _write_readme(version: str) -> None:
    release = parse_release_version(version)
    readme = README.read_text()
    readme = _replace_once(
        readme,
        r"\[!\[Stage: [^\]]+\]\(https://img\.shields\.io/badge/stage-[^)]+\)\]\(#development-status\)",
        _expected_readme_fragments(version)["stage_badge"],
        description="README stage badge",
    )
    readme = _replace_once(
        readme,
        r'dependencies = \["outlabs-auth>=[^"]+"\]',
        _expected_readme_fragments(version)["dependency_example"],
        description="README dependency example",
    )
    readme = _replace_once(
        readme,
        r'tag = "v[^"]+"',
        _expected_readme_fragments(version)["git_tag_example"],
        description="README git tag example",
    )
    readme = _replace_once(
        readme,
        r"^\*\*Current Library Version\*\*: .+$",
        _expected_readme_fragments(version)["library_version"],
        description="README library version",
    )
    readme = _replace_once(
        readme,
        r"^\*\*Current Admin UI Version\*\*: .+$",
        _expected_readme_fragments(version)["ui_version"],
        description="README admin UI version",
    )
    readme = _replace_once(
        readme,
        r"^\*\*Release Stage\*\*: .+$",
        _expected_readme_fragments(version)["release_stage"],
        description="README release stage",
    )
    readme = _replace_once(
        readme,
        r"^> \*\*.*? release\*\* - ",
        f"> **{release.stage_display} release** - ",
        description="README release banner",
    )
    README.write_text(readme)


def _check_private_release_doc() -> list[str]:
    issues: list[str] = []
    doc_text = PRIVATE_RELEASE_DOC.read_text()
    for fragment in (
        "uv run python scripts/release_version.py set X.Y.ZaN",
        "uv run python scripts/release_version.py check",
        "Release Readiness",
    ):
        if fragment not in doc_text:
            issues.append(f"`docs/PRIVATE_RELEASE.md` is missing `{fragment}`")
    return issues


def check_release_metadata(version: str) -> list[str]:
    release = parse_release_version(version)
    issues: list[str] = []

    version_file_text = VERSION_FILE.read_text()
    if f'__release_stage__ = "{release.release_stage}"' not in version_file_text:
        issues.append("`outlabs_auth/_version.py` release stage is out of sync")
    if f'__version__ = "{release.python_version}"' not in version_file_text:
        issues.append("`outlabs_auth/_version.py` version is out of sync")

    package_data = json.loads(PACKAGE_JSON.read_text())
    if package_data.get("version") != release.ui_version:
        issues.append("`auth-ui/package.json` UI version is out of sync")
    if package_data.get("packageManager") != "bun@1.3.3":
        issues.append("`auth-ui/package.json` packageManager is missing or unexpected")
    outlabs_auth_meta = package_data.get("outlabsAuth", {})
    if outlabs_auth_meta.get("libraryVersion") != release.python_version:
        issues.append("`auth-ui/package.json` linked library version is out of sync")
    if outlabs_auth_meta.get("releaseStage") != release.release_stage:
        issues.append("`auth-ui/package.json` release stage is out of sync")

    readme = README.read_text()
    for description, fragment in _expected_readme_fragments(version).items():
        if fragment not in readme:
            issues.append(f"`README.md` is missing the expected {description.replace('_', ' ')}")

    issues.extend(_check_private_release_doc())
    return issues


def _set_version(version: str) -> None:
    _write_version_file(version)
    _write_package_json(version)
    _write_readme(version)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keep OutlabsAuth release metadata in sync.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_parser = subparsers.add_parser("set", help="Set the current release version across tracked metadata files.")
    set_parser.add_argument("version", help="PEP 440 version, e.g. 0.1.0a2 or 0.1.0")

    subparsers.add_parser("check", help="Verify that release metadata files are in sync.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "set":
        _set_version(args.version)
        issues = check_release_metadata(args.version)
        if issues:
            for issue in issues:
                print(f"- {issue}", file=sys.stderr)
            return 1
        release = parse_release_version(args.version)
        print(f"Set library version to {release.python_version}")
        print(f"Set admin UI version to {release.ui_version}")
        print(f"Set release stage to {release.stage_display}")
        return 0

    current_version = _read_current_version()
    issues = check_release_metadata(current_version)
    if issues:
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1

    print(f"Release metadata is in sync for {current_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

