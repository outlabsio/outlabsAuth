"""Frontend profile registry (DD-059): declared at construction, validated at startup."""

from __future__ import annotations

from typing import Iterable, Iterator, Optional

from outlabs_auth.frontend.errors import (
    FrontendConfigurationError,
    FrontendRouteUnsupportedError,
    UnknownFrontendProfileError,
)
from outlabs_auth.frontend.types import (
    FrontendFlow,
    FrontendProfile,
    validate_profile_key,
    validate_public_origin,
)


class FrontendProfileRegistry:
    """
    Immutable registry of the host's declared frontend profiles.

    Declaration happens at construction; every profile is validated eagerly —
    origins are normalized here, so consumers can trust registered values.
    ``default`` names the declared default profile: it applies only to
    genuinely unambiguous contexts (a single-frontend host; a declared
    no-root population) and is never an exception fallback.
    """

    def __init__(
        self,
        profiles: Iterable[FrontendProfile],
        *,
        default: Optional[str] = None,
        local_dev: bool = False,
    ) -> None:
        normalized: dict[str, FrontendProfile] = {}
        for profile in profiles:
            if not isinstance(profile, FrontendProfile):
                raise FrontendConfigurationError(
                    f"Registry entries must be FrontendProfile instances, got {type(profile).__name__}"
                )
            if profile.key in normalized:
                raise FrontendConfigurationError(f"Duplicate frontend profile key {profile.key!r}")
            normalized_origins: list[str] = []
            for origin in profile.public_origins:
                normalized_origin = validate_public_origin(origin, local_dev=local_dev)
                if normalized_origin in normalized_origins:
                    raise FrontendConfigurationError(
                        f"Frontend profile {profile.key!r} repeats origin {normalized_origin!r}"
                    )
                normalized_origins.append(normalized_origin)
            if tuple(normalized_origins) != tuple(profile.public_origins):
                profile = FrontendProfile(
                    key=profile.key,
                    app_name=profile.app_name,
                    public_origins=tuple(normalized_origins),
                    routes=profile.routes,
                    redirect_policy=profile.redirect_policy,
                    accepted_audiences=profile.accepted_audiences,
                    support_email=profile.support_email,
                )
            normalized[profile.key] = profile

        if not normalized:
            raise FrontendConfigurationError("FrontendProfileRegistry requires at least one profile")

        if default is not None:
            validate_profile_key(default)
            if default not in normalized:
                raise UnknownFrontendProfileError(f"Default frontend profile {default!r} is not registered")

        self._profiles = normalized
        self._default_key = default
        self._local_dev = local_dev

    @property
    def default_key(self) -> Optional[str]:
        return self._default_key

    @property
    def local_dev(self) -> bool:
        return self._local_dev

    @property
    def is_single_profile(self) -> bool:
        return len(self._profiles) == 1

    def __len__(self) -> int:
        return len(self._profiles)

    def __contains__(self, key: object) -> bool:
        return key in self._profiles

    def __iter__(self) -> Iterator[FrontendProfile]:
        return iter(self._profiles.values())

    def keys(self) -> tuple[str, ...]:
        return tuple(self._profiles.keys())

    def get(self, key: str) -> FrontendProfile:
        """Return the registered profile for ``key`` (never an unregistered one)."""
        try:
            return self._profiles[key]
        except KeyError:
            raise UnknownFrontendProfileError(f"Frontend profile {key!r} is not registered") from None

    @property
    def default_profile(self) -> Optional[FrontendProfile]:
        return self._profiles[self._default_key] if self._default_key else None

    @property
    def single_profile(self) -> Optional[FrontendProfile]:
        if self.is_single_profile:
            return next(iter(self._profiles.values()))
        return None

    def require_route(self, key: str, flow: FrontendFlow) -> str:
        """
        Return the route template for ``(profile, flow)``.

        Selecting a profile for a flow whose route is ``None`` is a wiring
        error — this raises rather than letting a guessed link through.
        """
        profile = self.get(key)
        template = profile.routes.route_for(flow)
        if template is None:
            raise FrontendRouteUnsupportedError(
                f"Frontend profile {key!r} does not support flow {flow.value!r} (route is None)"
            )
        return template

    def public_origins_union(self) -> tuple[str, ...]:
        """Union of all registered origins — input for the host's CORS allowlist."""
        seen: list[str] = []
        for profile in self._profiles.values():
            for origin in profile.public_origins:
                if origin not in seen:
                    seen.append(origin)
        return tuple(seen)
