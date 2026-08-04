"""Typed-enough HTTP transport shared by remote administration commands."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

import httpx

from outlabs_auth._version import __version__
from outlabs_auth.cli_support.contexts import ContextStore, normalize_api_prefix, normalize_base_url
from outlabs_auth.cli_support.runtime import (
    CliError,
    CliRuntime,
    EXIT_AUTH,
    EXIT_CONFLICT,
    EXIT_OPERATION_FAILED,
    EXIT_UNAVAILABLE,
    EXIT_USAGE,
)


@dataclass(frozen=True)
class RemoteTarget:
    name: str
    base_url: str
    api_prefix: str
    app: Optional[str]
    credential_type: str
    credential_env: str
    timeout: float

    def context_dict(self) -> dict[str, Any]:
        return {
            "profile": self.name,
            "base_url": self.base_url,
            "api_prefix": self.api_prefix,
            "credential_type": self.credential_type,
            "credential_env": self.credential_env,
            **({"app": self.app} if self.app else {}),
        }


def resolve_remote_target(runtime: CliRuntime, store: Optional[ContextStore] = None) -> RemoteTarget:
    if runtime.base_url:
        return RemoteTarget(
            name=runtime.profile or "command-line",
            base_url=normalize_base_url(runtime.base_url, allow_insecure=False),
            api_prefix=normalize_api_prefix(runtime.api_prefix or "/v1"),
            app=None,
            credential_type=runtime.credential_type or "bearer",
            credential_env=runtime.credential_env
            or ("OUTLABS_AUTH_API_KEY" if runtime.credential_type == "api_key" else "OUTLABS_AUTH_TOKEN"),
            timeout=runtime.timeout,
        )

    loaded = (store or ContextStore()).load()
    profile = loaded.get(runtime.profile)
    credential_type = runtime.credential_type or profile.credential_type
    if runtime.credential_env:
        credential_env = runtime.credential_env
    elif runtime.credential_type and runtime.credential_type != profile.credential_type:
        credential_env = "OUTLABS_AUTH_API_KEY" if credential_type == "api_key" else "OUTLABS_AUTH_TOKEN"
    else:
        credential_env = profile.credential_env
    return RemoteTarget(
        name=profile.name,
        base_url=profile.base_url,
        api_prefix=normalize_api_prefix(runtime.api_prefix or profile.api_prefix),
        app=profile.app,
        credential_type=credential_type,
        credential_env=credential_env,
        timeout=runtime.timeout,
    )


class RemoteClient:
    def __init__(self, target: RemoteTarget, *, transport: Optional[httpx.BaseTransport] = None):
        self.target = target
        self.transport = transport

    def _url(self, path: str) -> str:
        normalized_path = f"/{path.lstrip('/')}"
        return f"{self.target.base_url}{self.target.api_prefix}{normalized_path}"

    def _target_details(self) -> dict[str, Any]:
        return {
            "profile": self.target.name,
            "target": f"{self.target.base_url}{self.target.api_prefix}",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        require_auth: bool = True,
    ) -> tuple[Any, dict[str, Any]]:
        headers = {
            "Accept": "application/json",
            "User-Agent": f"outlabs-auth-cli/{__version__}",
        }
        if require_auth:
            credential = os.environ.get(self.target.credential_env)
            if not credential:
                raise CliError(
                    code="AUTH_CREDENTIAL_MISSING",
                    message=(
                        f"Authentication credential environment variable " f"{self.target.credential_env} is not set."
                    ),
                    exit_code=EXIT_AUTH,
                    details=self._target_details()
                    | {
                        "credential_type": self.target.credential_type,
                        "credential_env": self.target.credential_env,
                    },
                    hint=f"Export {self.target.credential_env} with the configured credential.",
                )
            if self.target.credential_type == "api_key":
                headers["X-API-Key"] = credential
            else:
                headers["Authorization"] = f"Bearer {credential}"

        try:
            with httpx.Client(
                timeout=self.target.timeout,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = client.request(
                    method,
                    self._url(path),
                    headers=headers,
                    json=json_body,
                    params={name: value for name, value in (params or {}).items() if value is not None},
                )
        except httpx.TimeoutException as exc:
            raise CliError(
                code="REMOTE_TIMEOUT",
                message=f"The remote request exceeded {self.target.timeout:g} seconds.",
                exit_code=EXIT_UNAVAILABLE,
                details=self._target_details() | {"timeout_seconds": self.target.timeout},
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise CliError(
                code="REMOTE_UNAVAILABLE",
                message="The OutlabsAuth API could not be reached.",
                exit_code=EXIT_UNAVAILABLE,
                details=self._target_details() | {"exception_type": type(exc).__name__},
                hint="Check the active context, network path, and API availability.",
                retryable=True,
            ) from exc

        request_id = response.headers.get("x-request-id") or response.headers.get("traceparent")
        meta: dict[str, Any] = {
            "http_status": response.status_code,
            **({"request_id": request_id} if request_id else {}),
        }
        retry_after = response.headers.get("retry-after")
        if retry_after:
            meta["retry_after"] = retry_after

        if response.is_success:
            if response.status_code == 204 or not response.content:
                return None, meta
            try:
                return response.json(), meta
            except ValueError as exc:
                raise CliError(
                    code="REMOTE_PROTOCOL_ERROR",
                    message="The API returned a non-JSON success response.",
                    exit_code=EXIT_OPERATION_FAILED,
                    details=self._target_details() | meta,
                ) from exc

        try:
            raw_payload: Any = response.json()
        except ValueError:
            raw_payload = {}
        payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}

        code = str(payload.get("error") or f"HTTP_{response.status_code}")
        message = str(payload.get("message") or "The remote operation failed.")
        raw_details = payload.get("details")
        details: dict[str, Any] = dict(raw_details) if isinstance(raw_details, dict) else {}
        details.update(self._target_details())
        details.update(meta)

        if response.status_code in {401, 403}:
            exit_code = EXIT_AUTH
        elif response.status_code == 409:
            exit_code = EXIT_CONFLICT
        elif response.status_code == 422:
            exit_code = EXIT_USAGE
        elif response.status_code == 429 or response.status_code >= 500:
            exit_code = EXIT_UNAVAILABLE
        else:
            exit_code = EXIT_OPERATION_FAILED

        raise CliError(
            code=code,
            message=message,
            exit_code=exit_code,
            details=details,
            retryable=response.status_code == 429 or response.status_code >= 500,
        )

    def capabilities(self) -> tuple[Any, dict[str, Any]]:
        return self.request("GET", "/auth/config", require_auth=False)

    def whoami(self) -> tuple[Any, dict[str, Any]]:
        return self.request("GET", "/users/me", require_auth=True)

    def list_users(
        self,
        *,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        root_entity_id: Optional[str] = None,
        all_pages: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        params = {
            # ``--all`` means the complete collection even if the caller also
            # supplied a page value.
            "page": 1 if all_pages else page,
            "limit": 100 if all_pages else limit,
            "search": search,
            "status": status,
            "root_entity_id": root_entity_id,
        }
        first, meta = self.request("GET", "/users/", params=params)
        if not isinstance(first, dict) or not isinstance(first.get("items"), list):
            raise CliError(
                code="REMOTE_PROTOCOL_ERROR",
                message="The users endpoint returned an invalid pagination envelope.",
                exit_code=EXIT_OPERATION_FAILED,
                details=meta,
            )
        if not all_pages:
            return first, meta

        items = list(first["items"])
        pages = int(first.get("pages") or 0)
        for next_page in range(2, pages + 1):
            params["page"] = next_page
            payload, page_meta = self.request("GET", "/users/", params=params)
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise CliError(
                    code="REMOTE_PROTOCOL_ERROR",
                    message=f"Users page {next_page} returned an invalid pagination envelope.",
                    exit_code=EXIT_OPERATION_FAILED,
                    details=page_meta,
                )
            items.extend(payload["items"])
        return {
            "items": items,
            "total": int(first.get("total") or len(items)),
            "all": True,
            "pages_fetched": pages,
        }, meta

    def resolve_user(self, reference: str) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            user_id = str(UUID(reference))
        except ValueError:
            user_id = None

        if user_id:
            payload, meta = self.request("GET", f"/users/{user_id}")
            if not isinstance(payload, dict):
                raise CliError(
                    code="REMOTE_PROTOCOL_ERROR",
                    message="The user endpoint returned an invalid response.",
                    exit_code=EXIT_OPERATION_FAILED,
                    details=meta,
                )
            meta["resolution"] = {"input": reference, "kind": "id", "id": user_id}
            return payload, meta

        page, meta = self.list_users(page=1, limit=100, search=reference)
        candidates = [item for item in page.get("items", []) if isinstance(item, dict)]
        exact_email = [item for item in candidates if str(item.get("email", "")).lower() == reference.lower()]
        matches = exact_email or candidates
        if not matches:
            raise CliError(
                code="USER_NOT_FOUND",
                message=f"No user matched '{reference}'.",
                exit_code=EXIT_OPERATION_FAILED,
            )
        if len(matches) > 1:
            raise CliError(
                code="USER_REFERENCE_AMBIGUOUS",
                message=f"User reference '{reference}' matched more than one account.",
                exit_code=EXIT_CONFLICT,
                details={"matches": [{"id": item.get("id"), "email": item.get("email")} for item in matches[:10]]},
                hint="Use the exact email address or UUID.",
            )
        user = matches[0]
        meta["resolution"] = {
            "input": reference,
            "kind": "email" if exact_email else "search",
            "id": user.get("id"),
        }
        return user, meta
