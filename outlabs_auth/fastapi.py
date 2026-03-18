"""
FastAPI integration helpers for OutlabsAuth.

Provides centralized exception handlers that map domain exceptions to a consistent
HTTP error response shape.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from outlabs_auth.core.exceptions import OutlabsAuthException

ExceptionHandlerMode = Literal["auth_only", "global"]


def _extract_error_message(value: Any) -> Optional[str]:
    if isinstance(value, str):
        message = value.strip()
        return message or None

    if isinstance(value, dict):
        for key in ("message", "detail", "error"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                message = candidate.strip()
                if message:
                    return message

        return _extract_error_message(value.get("errors"))

    if isinstance(value, list) and value:
        first_error = value[0]
        if isinstance(first_error, dict):
            for key in ("message", "msg"):
                candidate = first_error.get(key)
                if isinstance(candidate, str):
                    message = candidate.strip()
                    if message:
                        return message

    return None


def register_outlabs_exception_handler(app: FastAPI) -> None:
    """Register only the OutlabsAuthException handler on a FastAPI app."""

    @app.exception_handler(OutlabsAuthException)
    async def _handle_outlabs_auth_exception(request: Request, exc: OutlabsAuthException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


def register_exception_handlers(
    app: FastAPI,
    *,
    debug: bool = False,
    observability: Optional[Any] = None,
    mode: ExceptionHandlerMode = "global",
) -> None:
    """
    Register OutlabsAuth-friendly exception handlers on a FastAPI app.

    Modes:
    - `auth_only`: register only the library-specific `OutlabsAuthException` handler
    - `global`: also install generic validation/HTTP/unexpected handlers
    """
    if mode not in {"auth_only", "global"}:
        raise ValueError("mode must be 'auth_only' or 'global'")

    register_outlabs_exception_handler(app)

    if mode == "auth_only":
        return

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
            },
        )

    @app.exception_handler(IntegrityError)
    async def _handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        details: dict[str, Any] = {}
        if debug:
            details["error"] = str(exc)
        return JSONResponse(
            status_code=409,
            content={
                "error": "INTEGRITY_ERROR",
                "message": "Integrity constraint violated",
                "details": details,
            },
        )

    @app.exception_handler(ValueError)
    async def _handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        details: dict[str, Any] = {}
        if debug:
            details["error"] = str(exc)
        message = str(exc).strip() or "Invalid input"
        return JSONResponse(
            status_code=422,
            content={
                "error": "INVALID_INPUT",
                "message": message,
                "details": details,
            },
        )

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        details: dict[str, Any] = {}
        if isinstance(exc.detail, dict):
            details = exc.detail
        elif exc.detail is not None:
            details = {"detail": exc.detail}
        message = _extract_error_message(exc.detail) or "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP_ERROR",
                "message": message,
                "details": details,
            },
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        if observability:
            try:
                observability.logger.error(
                    "unhandled_exception",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    path=str(request.url.path),
                    method=request.method,
                )
            except Exception:
                pass

        details: dict[str, Any] = {}
        if debug:
            details = {"error": str(exc), "error_type": type(exc).__name__}

        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Internal server error",
                "details": details,
            },
        )
