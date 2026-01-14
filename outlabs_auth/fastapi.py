"""
FastAPI integration helpers for OutlabsAuth.

Provides centralized exception handlers that map domain exceptions to a consistent
HTTP error response shape.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from outlabs_auth.core.exceptions import OutlabsAuthException


def register_exception_handlers(
    app: FastAPI,
    *,
    debug: bool = False,
    observability: Optional[Any] = None,
) -> None:
    """
    Register OutlabsAuth-friendly exception handlers on a FastAPI app.

    - `OutlabsAuthException` -> `exc.status_code` + `exc.to_dict()`
    - `RequestValidationError` -> 422 with consistent shape
    - `IntegrityError` -> 409 with consistent shape
    - fallback `Exception` -> 500 with consistent shape (no internal details unless `debug=True`)
    """

    @app.exception_handler(OutlabsAuthException)
    async def _handle_outlabs_auth_exception(
        request: Request, exc: OutlabsAuthException
    ) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
            },
        )

    @app.exception_handler(IntegrityError)
    async def _handle_integrity_error(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
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
        return JSONResponse(
            status_code=422,
            content={
                "error": "INVALID_INPUT",
                "message": "Invalid input",
                "details": details,
            },
        )

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        details: dict[str, Any] = {}
        if isinstance(exc.detail, dict):
            details = exc.detail
        elif exc.detail is not None:
            details = {"detail": exc.detail}
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP_ERROR",
                "message": "Request failed",
                "details": details,
            },
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
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
