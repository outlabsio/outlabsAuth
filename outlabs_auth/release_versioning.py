from __future__ import annotations

from dataclasses import dataclass
import re

_VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:(?P<tag>a|b|rc)(?P<number>\d+))?$")

_STAGE_BY_TAG = {
    "a": "alpha",
    "b": "beta",
    "rc": "rc",
}

_STAGE_DISPLAY = {
    "alpha": "Alpha",
    "beta": "Beta",
    "rc": "RC",
    "stable": "Stable",
}

_STAGE_BADGE_COLOR = {
    "alpha": "red",
    "beta": "orange",
    "rc": "blue",
    "stable": "brightgreen",
}


@dataclass(frozen=True)
class ReleaseVersion:
    python_version: str
    major: int
    minor: int
    patch: int
    release_stage: str
    prerelease_number: int | None

    @property
    def base_version(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def ui_version(self) -> str:
        if self.release_stage == "stable":
            return self.base_version
        assert self.prerelease_number is not None
        return f"{self.base_version}-{self.release_stage}.{self.prerelease_number}"

    @property
    def git_tag(self) -> str:
        return f"v{self.python_version}"

    @property
    def dependency_specifier(self) -> str:
        return f">={self.python_version},<{self.major}.{self.minor + 1}"

    @property
    def stage_display(self) -> str:
        return _STAGE_DISPLAY[self.release_stage]

    @property
    def stage_badge_color(self) -> str:
        return _STAGE_BADGE_COLOR[self.release_stage]


def parse_release_version(version: str) -> ReleaseVersion:
    match = _VERSION_RE.fullmatch(version)
    if not match:
        raise ValueError(
            "Unsupported version format. Expected `X.Y.Z`, `X.Y.ZaN`, `X.Y.ZbN`, or `X.Y.ZrcN`."
        )

    tag = match.group("tag")
    release_stage = _STAGE_BY_TAG.get(tag, "stable")
    prerelease_number = match.group("number")

    return ReleaseVersion(
        python_version=version,
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        release_stage=release_stage,
        prerelease_number=int(prerelease_number) if prerelease_number else None,
    )

