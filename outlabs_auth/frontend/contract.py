"""Cross-repository route-contract checks (DD-059).

A ``FrontendProfile``'s typed route templates are claims about ANOTHER
repository's route tree — the class of assumption behind every dead-link
defect in the multi-frontend audit. These helpers turn each claim into an
executable assertion a consumer runs in its own test suite against the
frontend checkouts it integrates with:

    available = routes_from_nuxt_pages(Path("../frontend/app/pages"))
    assert_profile_routes(portal_profile, available)

The adapters are deliberately best-effort filename/constants parsers: they
exist to catch "the declared route does not exist at all", not to emulate a
frontend router.
"""

from __future__ import annotations

import re
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Collection, Optional

from outlabs_auth.frontend.types import FrontendProfile

_PARAM_RE = re.compile(r"\[([^\]/]+)\]")
_ROUTE_LITERAL_RE = re.compile(r"""["'](/[A-Za-z0-9_\-/{}]*)["']""")


def template_path(template: str) -> str:
    """The path portion of a route template (query string stripped)."""
    return template.split("?", 1)[0] or "/"


def declared_route_paths(profile: FrontendProfile) -> dict[str, str]:
    """Declared (non-``None``) route fields mapped to their path portion."""
    declared: dict[str, str] = {}
    for field in dataclass_fields(profile.routes):
        template = getattr(profile.routes, field.name)
        if template is not None:
            declared[field.name] = template_path(template)
    return declared


def missing_frontend_routes(
    profile: FrontendProfile,
    available: Collection[str],
    *,
    ignore: Collection[str] = (),
) -> dict[str, str]:
    """Declared routes whose path is absent from ``available``."""
    normalized = {template_path(path) for path in available}
    return {
        name: path
        for name, path in declared_route_paths(profile).items()
        if name not in ignore and path not in normalized
    }


def assert_profile_routes(
    profile: FrontendProfile,
    available: Collection[str],
    *,
    ignore: Collection[str] = (),
) -> None:
    """Raise ``AssertionError`` listing declared routes the frontend lacks."""
    missing = missing_frontend_routes(profile, available, ignore=ignore)
    if missing:
        listing = ", ".join(f"{name}={path!r}" for name, path in sorted(missing.items()))
        raise AssertionError(
            f"Frontend profile {profile.key!r} declares routes its frontend does not "
            f"implement: {listing}. Fix the frontend, or declare the flow None."
        )


def routes_from_nuxt_pages(pages_dir: Path | str) -> set[str]:
    """Route paths from a Nuxt ``pages/`` tree (``[param]`` -> ``{param}``)."""
    root = Path(pages_dir)
    return {
        _nuxt_path(page.relative_to(root))
        for page in root.rglob("*.vue")
    }


def routes_from_path_names(names: Collection[str]) -> set[str]:
    """Route paths from Nuxt-style page path names (e.g. git ls-tree output)."""
    return {_nuxt_path(Path(name)) for name in names if str(name).endswith(".vue")}


def _nuxt_path(relative: Path) -> str:
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "index":
        parts = parts[:-1]
    joined = "/" + "/".join(parts) if parts else "/"
    return _PARAM_RE.sub(lambda match: "{" + match.group(1) + "}", joined)


def routes_from_tanstack_route_dir(routes_dir: Path | str) -> set[str]:
    """Route paths from a TanStack flat-file routes directory (dots -> slashes)."""
    root = Path(routes_dir)
    paths: set[str] = set()
    for route_file in root.glob("*.tsx"):
        stem = route_file.name[: -len(".tsx")]
        if stem.startswith("__"):
            continue
        segments = [segment for segment in stem.split(".") if segment and segment != "index"]
        segments = [
            "{" + segment[1:] + "}" if segment.startswith("$") else segment
            for segment in segments
        ]
        paths.add("/" + "/".join(segments) if segments else "/")
    return paths


def routes_from_route_constants(constants_file: Path | str) -> set[str]:
    """Absolute-path string literals from a routes/constants source file."""
    text = Path(constants_file).read_text(encoding="utf-8")
    return {match.group(1) for match in _ROUTE_LITERAL_RE.finditer(text)}


def normalize_available(paths: Collection[str]) -> set[str]:
    """Convenience: strip query strings from an available-route collection."""
    return {template_path(path) for path in paths}


__all__ = [
    "assert_profile_routes",
    "declared_route_paths",
    "missing_frontend_routes",
    "normalize_available",
    "routes_from_nuxt_pages",
    "routes_from_path_names",
    "routes_from_route_constants",
    "routes_from_tanstack_route_dir",
    "template_path",
]
