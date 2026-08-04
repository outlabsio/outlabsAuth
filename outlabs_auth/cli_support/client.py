"""Typed-enough HTTP transport shared by remote administration commands."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

import httpx

from outlabs_auth._version import __version__
from outlabs_auth.cli_support.contexts import ContextStore, normalize_api_prefix, normalize_base_url
from outlabs_auth.cli_support.credentials import CredentialStore, StoredSession
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
    def __init__(
        self,
        target: RemoteTarget,
        *,
        transport: Optional[httpx.BaseTransport] = None,
        credential_store: Optional[CredentialStore] = None,
    ):
        self.target = target
        self.transport = transport
        self._credential_store = credential_store

    def _url(self, path: str) -> str:
        normalized_path = f"/{path.lstrip('/')}"
        return f"{self.target.base_url}{self.target.api_prefix}{normalized_path}"

    def _target_details(self) -> dict[str, Any]:
        return {
            "profile": self.target.name,
            "target": f"{self.target.base_url}{self.target.api_prefix}",
        }

    def credential_store(self) -> CredentialStore:
        if self._credential_store is None:
            self._credential_store = CredentialStore().load()
        return self._credential_store

    def stored_session(self, *, required: bool = False) -> Optional[StoredSession]:
        return self.credential_store().get(
            self.target.name,
            base_url=self.target.base_url,
            api_prefix=self.target.api_prefix,
            required=required,
        )

    def authentication_status(self) -> dict[str, Any]:
        """Return safe local credential metadata without making a request."""

        environment_configured = bool(os.environ.get(self.target.credential_env))
        stored = self.stored_session(required=False) if self.target.credential_type == "bearer" else None
        if environment_configured:
            source: Optional[str] = "environment"
        elif stored is not None:
            source = "stored_session"
        else:
            source = None
        return {
            "authenticated": source is not None,
            "source": source,
            "credential_type": self.target.credential_type,
            "credential_env": self.target.credential_env,
            "environment_configured": environment_configured,
            "stored_session": stored.public_dict() if stored else None,
        }

    def _authentication_credential(self) -> tuple[str, str]:
        environment_value = os.environ.get(self.target.credential_env)
        if environment_value:
            return environment_value, "environment"

        if self.target.credential_type == "bearer":
            session = self.stored_session(required=False)
            if session is not None:
                if session.expires_within(30):
                    session, _ = self.refresh_stored_session(session=session)
                return session.access_token, "stored_session"

        raise CliError(
            code="AUTH_CREDENTIAL_MISSING",
            message=f"Authentication credential environment variable {self.target.credential_env} is not set.",
            exit_code=EXIT_AUTH,
            details=self._target_details()
            | {
                "credential_type": self.target.credential_type,
                "credential_env": self.target.credential_env,
            },
            hint=(
                f"Export {self.target.credential_env} with the configured credential."
                if self.target.credential_type == "api_key"
                else f"Export {self.target.credential_env} or run: outlabs-auth auth login --email USER@example.com"
            ),
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: Optional[dict[str, Any]] = None,
        require_auth: bool = True,
        _retry_stored_auth: bool = True,
    ) -> tuple[Any, dict[str, Any]]:
        headers = {
            "Accept": "application/json",
            "User-Agent": f"outlabs-auth-cli/{__version__}",
        }
        auth_source: Optional[str] = None
        if require_auth:
            credential, auth_source = self._authentication_credential()
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
            **({"auth_source": auth_source} if auth_source else {}),
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

        if response.status_code == 401 and auth_source == "stored_session" and _retry_stored_auth:
            self.refresh_stored_session(force=True)
            return self.request(
                method,
                path,
                json_body=json_body,
                params=params,
                require_auth=require_auth,
                _retry_stored_auth=False,
            )

        code, message, details = _decode_remote_error(response)
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

    def login(self, *, email: str, password: str) -> tuple[StoredSession, dict[str, Any]]:
        payload, meta = self.request(
            "POST",
            "/auth/login",
            json_body={"email": email, "password": password, "app": self.target.app},
            require_auth=False,
        )
        session = self.store_session_payload(payload, email=email, endpoint="login")
        return session, meta

    def store_session_payload(
        self,
        payload: Any,
        *,
        email: Optional[str],
        endpoint: str,
    ) -> StoredSession:
        """Validate and persist a token exchange without exposing token values."""

        if not isinstance(payload, dict):
            raise _protocol_error(f"The {endpoint} endpoint returned an invalid response.", self._target_details())
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_in = payload.get("expires_in")
        if (
            not isinstance(access_token, str)
            or not access_token
            or not isinstance(refresh_token, str)
            or not refresh_token
        ):
            raise _protocol_error(f"The {endpoint} endpoint omitted required tokens.", self._target_details())
        if isinstance(expires_in, bool) or not isinstance(expires_in, (int, str)):
            raise _protocol_error(
                f"The {endpoint} endpoint returned an invalid token lifetime.", self._target_details()
            )
        try:
            lifetime = int(expires_in)
        except (TypeError, ValueError) as exc:
            raise _protocol_error(
                f"The {endpoint} endpoint returned an invalid token lifetime.", self._target_details()
            ) from exc
        if lifetime <= 0:
            raise _protocol_error(
                f"The {endpoint} endpoint returned an expired token lifetime.", self._target_details()
            )
        now = time.time()
        session = StoredSession(
            profile=self.target.name,
            base_url=self.target.base_url,
            api_prefix=self.target.api_prefix,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=now + lifetime,
            created_at=now,
            email=email,
            app=self.target.app,
        )
        self.credential_store().put(session)
        return session

    def refresh_stored_session(
        self,
        *,
        session: Optional[StoredSession] = None,
        force: bool = False,
    ) -> tuple[StoredSession, dict[str, Any]]:
        current = session or self.stored_session(required=True)
        assert current is not None
        if not force and not current.expires_within(30):
            return current, {"refreshed": False}
        payload, meta = self.request(
            "POST",
            "/auth/refresh",
            json_body={"refresh_token": current.refresh_token},
            require_auth=False,
        )
        if not isinstance(payload, dict):
            raise _protocol_error("The refresh endpoint returned an invalid response.", self._target_details() | meta)
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_in = payload.get("expires_in")
        if isinstance(expires_in, bool) or not isinstance(expires_in, (int, str)):
            raise _protocol_error(
                "The refresh endpoint returned an invalid token lifetime.", self._target_details() | meta
            )
        try:
            lifetime = int(expires_in)
        except (TypeError, ValueError) as exc:
            raise _protocol_error(
                "The refresh endpoint returned an invalid token lifetime.", self._target_details() | meta
            ) from exc
        if (
            not isinstance(access_token, str)
            or not access_token
            or not isinstance(refresh_token, str)
            or not refresh_token
            or lifetime <= 0
        ):
            raise _protocol_error("The refresh endpoint omitted required token data.", self._target_details() | meta)
        refreshed = StoredSession(
            profile=current.profile,
            base_url=current.base_url,
            api_prefix=current.api_prefix,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=time.time() + lifetime,
            created_at=current.created_at,
            email=current.email,
            app=current.app,
        )
        self.credential_store().put(refreshed)
        return refreshed, meta | {"refreshed": True}

    def logout(self, *, refresh_token: Optional[str], immediate: bool) -> tuple[Any, dict[str, Any]]:
        return self.request(
            "POST",
            "/auth/logout",
            json_body={"refresh_token": refresh_token, "immediate": immediate},
            require_auth=True,
        )

    def capabilities(self) -> tuple[Any, dict[str, Any]]:
        return self.request("GET", "/auth/config", require_auth=False)

    def whoami(self) -> tuple[Any, dict[str, Any]]:
        return self.request("GET", "/users/me", require_auth=True)

    def paginate(
        self,
        path: str,
        *,
        page: int = 1,
        limit: int = 20,
        max_limit: int = 100,
        all_pages: bool = False,
        params: Optional[dict[str, Any]] = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Consume the library's standard PaginatedResponse envelope."""

        request_params = dict(params or {})
        request_params.update(
            {
                "page": 1 if all_pages else page,
                "limit": max_limit if all_pages else limit,
            }
        )
        first, meta = self.request("GET", path, params=request_params)
        if not isinstance(first, dict) or not isinstance(first.get("items"), list):
            raise _protocol_error(
                f"The {path} endpoint returned an invalid pagination envelope.",
                self._target_details() | meta,
            )
        if not all_pages:
            return first, meta

        items = list(first["items"])
        try:
            pages = int(first.get("pages") or 0)
            total = int(first.get("total") or len(items))
        except (TypeError, ValueError) as exc:
            raise _protocol_error(
                f"The {path} endpoint returned invalid pagination metadata.",
                self._target_details() | meta,
            ) from exc
        for next_page in range(2, pages + 1):
            request_params["page"] = next_page
            payload, page_meta = self.request("GET", path, params=request_params)
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise _protocol_error(
                    f"Page {next_page} from {path} returned an invalid pagination envelope.",
                    self._target_details() | page_meta,
                )
            items.extend(payload["items"])
        return {
            "items": items,
            "total": total,
            "all": True,
            "pages_fetched": pages,
        }, meta

    def resolve_resource(
        self,
        reference: str,
        *,
        resource_name: str,
        detail_path: str,
        list_path: str,
        exact_fields: tuple[str, ...],
        search_param: Optional[str] = "search",
        max_limit: int = 100,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Resolve UUID, exact canonical name, or one unambiguous search result."""

        resource_label = resource_name.replace("_", " ")
        resource_code = resource_name.replace("-", "_").replace(" ", "_").upper()
        try:
            resource_id = str(UUID(reference))
        except ValueError:
            resource_id = None
        if resource_id:
            payload, meta = self.request("GET", detail_path.format(id=resource_id))
            if not isinstance(payload, dict):
                raise _protocol_error(
                    f"The {resource_label} endpoint returned an invalid response.",
                    self._target_details() | meta,
                )
            meta["resolution"] = {"input": reference, "kind": "id", "id": resource_id}
            return payload, meta

        filters = {search_param: reference} if search_param else None
        page, meta = self.paginate(
            list_path,
            all_pages=True,
            max_limit=max_limit,
            params=filters,
        )
        candidates = [item for item in page["items"] if isinstance(item, dict)]
        matches: list[dict[str, Any]] = []
        matched_field: Optional[str] = None
        for field in exact_fields:
            field_matches = [item for item in candidates if str(item.get(field, "")).casefold() == reference.casefold()]
            if field_matches:
                matches = field_matches
                matched_field = field
                break
        if not matches:
            matches = candidates
        if not matches:
            raise CliError(
                code=f"{resource_code}_NOT_FOUND",
                message=f"No {resource_label} matched '{reference}'.",
                exit_code=EXIT_OPERATION_FAILED,
            )
        if len(matches) > 1:
            raise CliError(
                code=f"{resource_code}_REFERENCE_AMBIGUOUS",
                message=f"{resource_label.title()} reference '{reference}' matched more than one result.",
                exit_code=EXIT_CONFLICT,
                details={
                    "matches": [
                        {
                            "id": item.get("id"),
                            **{field: item.get(field) for field in exact_fields if item.get(field) is not None},
                        }
                        for item in matches[:10]
                    ]
                },
                hint=f"Use the exact canonical name or {resource_label} UUID.",
            )
        result = matches[0]
        meta["resolution"] = {
            "input": reference,
            "kind": matched_field or "search",
            "id": result.get("id"),
        }
        return result, meta

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
            "search": search,
            "status": status,
            "root_entity_id": root_entity_id,
        }
        return self.paginate(
            "/users/",
            page=page,
            limit=limit,
            max_limit=100,
            all_pages=all_pages,
            params=params,
        )

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


_SENSITIVE_ERROR_KEYS = {
    "access_token",
    "authorization",
    "credential",
    "input",
    "new_password",
    "password",
    "refresh_token",
    "secret",
    "token",
}


def _sanitize_remote_error(value: Any) -> Any:
    """Remove values that an upstream FastAPI validator may echo."""

    if isinstance(value, dict):
        return {
            str(key): _sanitize_remote_error(item)
            for key, item in value.items()
            if str(key).lower() not in _SENSITIVE_ERROR_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_remote_error(item) for item in value]
    return value


def _decode_remote_error(response: httpx.Response) -> tuple[str, str, dict[str, Any]]:
    try:
        raw_payload: Any = response.json()
    except ValueError:
        raw_payload = {}
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    detail = payload.get("detail")
    detail_payload = detail if isinstance(detail, dict) else {}
    code = str(payload.get("error") or detail_payload.get("code") or f"HTTP_{response.status_code}")
    if payload.get("message"):
        message = str(payload["message"])
    elif detail_payload.get("message"):
        message = str(detail_payload["message"])
    elif isinstance(detail, str) and detail:
        message = detail
    elif isinstance(detail, list):
        message = "The remote request failed validation."
    else:
        message = "The remote operation failed."
    raw_details = payload.get("details")
    details: dict[str, Any] = dict(raw_details) if isinstance(raw_details, dict) else {}
    if detail_payload:
        nested = {key: value for key, value in detail_payload.items() if key not in {"code", "message"}}
        if nested:
            details["detail"] = nested
    elif isinstance(detail, list):
        details["errors"] = detail
    sanitized = _sanitize_remote_error(details)
    return code, message, sanitized if isinstance(sanitized, dict) else {}


def _protocol_error(message: str, details: dict[str, Any]) -> CliError:
    return CliError(
        code="REMOTE_PROTOCOL_ERROR",
        message=message,
        exit_code=EXIT_OPERATION_FAILED,
        details=details,
    )
