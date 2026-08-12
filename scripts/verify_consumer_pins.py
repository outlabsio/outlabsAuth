#!/usr/bin/env python3
"""Verify exact downstream pins for an OutlabsAuth release.

The consumer inventory deliberately lives outside this public repository. See
``docs/CONSUMER_PIN_AUDIT.md`` for the configuration contract.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PACKAGE_NAME = "outlabs-auth"
PYPI_REGISTRY = "https://pypi.org/simple"


@dataclass(frozen=True)
class ConsumerResult:
    id: str
    repo: str
    origin: str | None
    manifest_pin: str | None
    lock_pin: str | None
    lock_version: str | None
    ok: bool
    errors: list[str]


@dataclass(frozen=True)
class AuditResult:
    package: str
    expected_version: str
    expected_consumer_count: int
    ok: bool
    errors: list[str]
    consumers: list[ConsumerResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConfigurationError(ValueError):
    """Raised when the audit matrix is malformed or internally inconsistent."""


def _normalise_package_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _normalise_origin(value: str) -> str:
    origin = value.strip()
    scp_match = re.fullmatch(r"(?:[^@/]+@)?([^:/]+):(.+)", origin)
    if scp_match and "://" not in origin:
        host, path = scp_match.groups()
    elif "://" in origin:
        parsed = urlparse(origin)
        host = parsed.hostname or ""
        path = parsed.path
    else:
        path_value = origin.removeprefix("//")
        host, separator, path = path_value.partition("/")
        if not separator:
            raise ConfigurationError(f"invalid repository origin: {value!r}")

    normalised_path = path.strip("/")
    if normalised_path.endswith(".git"):
        normalised_path = normalised_path[:-4]
    if not host or not normalised_path:
        raise ConfigurationError(f"invalid repository origin: {value!r}")
    return f"{host.lower()}/{normalised_path.lower()}"


def _exact_requirement_version(requirement: str, package: str) -> str | None:
    escaped_name = re.escape(package).replace(r"\-", "[-_.]")
    match = re.fullmatch(
        rf"\s*{escaped_name}(?:\[[^\]]+\])?\s*==\s*([^\s,;]+)\s*(?:;\s*.+)?",
        requirement,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None


def _load_toml(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing {label}: {path}")
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"cannot read {label} {path}: {exc}")
    return None


def _path_within_repo(repo: Path, relative_path: str, label: str) -> Path:
    candidate = (repo / relative_path).resolve()
    try:
        candidate.relative_to(repo)
    except ValueError as exc:
        raise ConfigurationError(f"{label} escapes repository root: {relative_path}") from exc
    return candidate


def _git_origin(repo: Path, errors: list[str]) -> str | None:
    try:
        root = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if Path(root).resolve() != repo:
            errors.append(f"configured path is not the repository root: {repo} (git root: {root})")
            return None
        origin = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return _normalise_origin(origin)
    except (FileNotFoundError, subprocess.CalledProcessError, ConfigurationError) as exc:
        errors.append(f"cannot resolve git origin for {repo}: {exc}")
        return None


def _manifest_pin(data: dict[str, Any], package: str, errors: list[str]) -> str | None:
    dependencies = data.get("project", {}).get("dependencies", [])
    if not isinstance(dependencies, list):
        errors.append("project.dependencies must be a list")
        return None

    matching = [
        value
        for value in dependencies
        if isinstance(value, str)
        and _normalise_package_name(re.split(r"[<>=!~\[;\s]", value.strip(), maxsplit=1)[0]) == package
    ]
    if len(matching) != 1:
        errors.append(f"manifest must contain exactly one direct {package} dependency; found {len(matching)}")
        return None
    pin = _exact_requirement_version(matching[0], package)
    if pin is None:
        errors.append(f"manifest dependency is not an exact == pin: {matching[0]!r}")
    return pin


def _lock_facts(
    data: dict[str, Any],
    package: str,
    expected_registry: str,
    wheel_sha256: str | None,
    sdist_sha256: str | None,
    errors: list[str],
) -> tuple[str | None, str | None]:
    packages = data.get("package", [])
    if not isinstance(packages, list):
        errors.append("lock package table must be a list")
        return None, None

    resolved = [item for item in packages if _normalise_package_name(str(item.get("name", ""))) == package]
    if len(resolved) != 1:
        errors.append(f"lock must resolve exactly one {package} package; found {len(resolved)}")
        return None, None

    package_entry = resolved[0]
    version = str(package_entry.get("version", "")) or None
    source = package_entry.get("source", {})
    registry = source.get("registry") if isinstance(source, dict) else None
    if registry != expected_registry:
        errors.append(f"lock source must be {expected_registry!r}; found {source!r}")

    if wheel_sha256:
        wheel_hashes = {
            str(item.get("hash", "")).removeprefix("sha256:")
            for item in package_entry.get("wheels", [])
            if isinstance(item, dict)
        }
        if wheel_sha256 not in wheel_hashes:
            errors.append("trusted wheel SHA-256 is absent from the lock")
    if sdist_sha256:
        sdist = package_entry.get("sdist", {})
        locked_sdist = str(sdist.get("hash", "")).removeprefix("sha256:") if isinstance(sdist, dict) else ""
        if locked_sdist != sdist_sha256:
            errors.append("trusted sdist SHA-256 does not match the lock")

    root_packages = [
        item
        for item in packages
        if isinstance(item.get("source"), dict)
        and (item["source"].get("editable") == "." or item["source"].get("virtual") == ".")
    ]
    if len(root_packages) != 1:
        errors.append(f"lock must contain exactly one editable/virtual root package; found {len(root_packages)}")
        return None, version

    requirements = root_packages[0].get("metadata", {}).get("requires-dist", [])
    matching = [
        item
        for item in requirements
        if isinstance(item, dict) and _normalise_package_name(str(item.get("name", ""))) == package
    ]
    if len(matching) != 1:
        errors.append(
            f"root lock metadata must contain exactly one direct {package} requirement; found {len(matching)}"
        )
        return None, version
    specifier = str(matching[0].get("specifier", ""))
    lock_pin = specifier.removeprefix("==") if specifier.startswith("==") and specifier.count(",") == 0 else None
    if lock_pin is None:
        errors.append(f"root lock requirement is not an exact == pin: {specifier!r}")
    return lock_pin, version


def audit_matrix(config_path: Path, workspace_root: Path | None = None) -> AuditResult:
    config_path = config_path.resolve()
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"cannot read config {config_path}: {exc}") from exc

    if config.get("schema_version") != 1:
        raise ConfigurationError("schema_version must be 1")
    package = _normalise_package_name(str(config.get("package", "")))
    if package != PACKAGE_NAME:
        raise ConfigurationError(f"package must be {PACKAGE_NAME!r}")
    expected_version = str(config.get("expected_version", "")).strip()
    if not expected_version:
        raise ConfigurationError("expected_version is required")

    consumers = config.get("consumers")
    if not isinstance(consumers, list) or not consumers:
        raise ConfigurationError("at least one [[consumers]] entry is required")
    expected_count = config.get("expected_consumer_count")
    if not isinstance(expected_count, int) or expected_count < 1:
        raise ConfigurationError("expected_consumer_count must be a positive integer")
    if len(consumers) != expected_count:
        raise ConfigurationError(f"expected {expected_count} consumers, config contains {len(consumers)}")

    configured_workspace = config.get("workspace_root", ".")
    root = (workspace_root or (config_path.parent / str(configured_workspace))).resolve()
    expected_registry = str(config.get("expected_registry", PYPI_REGISTRY))
    artifacts = config.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ConfigurationError("artifacts must be a table")
    wheel_sha256 = artifacts.get("wheel_sha256")
    sdist_sha256 = artifacts.get("sdist_sha256")
    for label, value in (("wheel_sha256", wheel_sha256), ("sdist_sha256", sdist_sha256)):
        if value is not None and not re.fullmatch(r"[0-9a-f]{64}", str(value)):
            raise ConfigurationError(f"artifacts.{label} must be a lowercase 64-character SHA-256")

    ids: set[str] = set()
    paths: set[Path] = set()
    origins: set[str] = set()
    global_errors: list[str] = []
    results: list[ConsumerResult] = []

    for item in consumers:
        if not isinstance(item, dict):
            raise ConfigurationError("each consumer entry must be a table")
        consumer_id = str(item.get("id", "")).strip()
        repo_value = str(item.get("repo", "")).strip()
        origin_value = str(item.get("origin", "")).strip()
        if not consumer_id or not repo_value or not origin_value:
            raise ConfigurationError("each consumer requires id, repo, and origin")
        if consumer_id in ids:
            raise ConfigurationError(f"duplicate consumer id: {consumer_id}")
        ids.add(consumer_id)

        repo = (root / repo_value).resolve()
        expected_origin = _normalise_origin(origin_value)
        if repo in paths:
            raise ConfigurationError(f"duplicate consumer repository path: {repo}")
        if expected_origin in origins:
            raise ConfigurationError(f"duplicate consumer origin: {expected_origin}")
        paths.add(repo)
        origins.add(expected_origin)

        errors: list[str] = []
        actual_origin = _git_origin(repo, errors) if repo.is_dir() else None
        if not repo.is_dir():
            errors.append(f"repository directory does not exist: {repo}")
        elif actual_origin != expected_origin:
            errors.append(f"origin mismatch: expected {expected_origin!r}, found {actual_origin!r}")

        manifest_path = _path_within_repo(repo, str(item.get("manifest", "pyproject.toml")), "manifest")
        lock_path = _path_within_repo(repo, str(item.get("lock", "uv.lock")), "lock")
        manifest_data = _load_toml(manifest_path, "manifest", errors)
        lock_data = _load_toml(lock_path, "lock", errors)
        manifest_pin = _manifest_pin(manifest_data, package, errors) if manifest_data else None
        lock_pin, lock_version = (
            _lock_facts(
                lock_data,
                package,
                expected_registry,
                str(wheel_sha256) if wheel_sha256 else None,
                str(sdist_sha256) if sdist_sha256 else None,
                errors,
            )
            if lock_data
            else (None, None)
        )
        if manifest_pin is not None and manifest_pin != expected_version:
            errors.append(f"manifest pins {manifest_pin!r}, expected {expected_version!r}")
        if lock_pin is not None and lock_pin != expected_version:
            errors.append(f"root lock metadata pins {lock_pin!r}, expected {expected_version!r}")
        if lock_version is not None and lock_version != expected_version:
            errors.append(f"lock resolves {lock_version!r}, expected {expected_version!r}")
        if manifest_pin and lock_pin and manifest_pin != lock_pin:
            errors.append(f"manifest/lock pin mismatch: {manifest_pin!r} != {lock_pin!r}")

        results.append(
            ConsumerResult(
                id=consumer_id,
                repo=str(repo),
                origin=actual_origin,
                manifest_pin=manifest_pin,
                lock_pin=lock_pin,
                lock_version=lock_version,
                ok=not errors,
                errors=errors,
            )
        )

    return AuditResult(
        package=package,
        expected_version=expected_version,
        expected_consumer_count=expected_count,
        ok=not global_errors and all(result.ok for result in results),
        errors=global_errors,
        consumers=results,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="Path to the private consumer matrix TOML")
    parser.add_argument("--workspace-root", type=Path, help="Override the matrix workspace root")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = audit_matrix(args.config, args.workspace_root)
    except ConfigurationError as exc:
        if args.json:
            print(json.dumps({"ok": False, "configuration_error": str(exc)}, indent=2, sort_keys=True))
        else:
            print(f"CONFIGURATION ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        status = "PASS" if result.ok else "FAIL"
        print(f"{status}: {result.package}=={result.expected_version} across {len(result.consumers)} consumers")
        for consumer in result.consumers:
            print(f"  {'PASS' if consumer.ok else 'FAIL'} {consumer.id}")
            for error in consumer.errors:
                print(f"    - {error}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
