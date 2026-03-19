from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from outlabs_auth.fastapi import _extract_error_message, register_exception_handlers


@pytest.mark.unit
def test_extract_error_message_handles_nested_dicts_lists_and_empty_values():
    assert _extract_error_message("  hello  ") == "hello"
    assert _extract_error_message({"detail": "boom"}) == "boom"
    assert _extract_error_message({"errors": [{"msg": "nested failure"}]}) == "nested failure"
    assert _extract_error_message([{"message": "first"}]) == "first"
    assert _extract_error_message({"errors": ["bad"]}) is None
    assert _extract_error_message([]) is None


@pytest.mark.unit
def test_register_exception_handlers_rejects_invalid_mode():
    app = FastAPI()

    with pytest.raises(ValueError, match="mode must be 'auth_only' or 'global'"):
        register_exception_handlers(app, mode="invalid")


def _client_for_app(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
def test_fastapi_handlers_cover_validation_integrity_value_and_http_paths():
    app = FastAPI()
    register_exception_handlers(app, debug=True)

    @app.get("/validation")
    async def validation(count: int):
        return {"count": count}

    @app.get("/integrity")
    async def integrity():
        raise IntegrityError("INSERT", {"id": 1}, Exception("duplicate key"))

    @app.get("/value")
    async def value():
        raise ValueError("bad input")

    @app.get("/http-dict")
    async def http_dict():
        raise HTTPException(
            status_code=409,
            detail={"errors": [{"msg": "nested http failure"}], "code": "conflict"},
        )

    @app.get("/http-string")
    async def http_string():
        raise HTTPException(status_code=404, detail="missing resource")

    client = _client_for_app(app)

    validation_response = client.get("/validation", params={"count": "bad"})
    assert validation_response.status_code == 422
    assert validation_response.json()["error"] == "VALIDATION_ERROR"

    integrity_response = client.get("/integrity")
    assert integrity_response.status_code == 409
    assert integrity_response.json()["details"]["error"]

    value_response = client.get("/value")
    assert value_response.status_code == 422
    assert value_response.json() == {
        "error": "INVALID_INPUT",
        "message": "bad input",
        "details": {"error": "bad input"},
    }

    http_dict_response = client.get("/http-dict")
    assert http_dict_response.status_code == 409
    assert http_dict_response.json() == {
        "error": "HTTP_ERROR",
        "message": "nested http failure",
        "details": {"errors": [{"msg": "nested http failure"}], "code": "conflict"},
    }

    http_string_response = client.get("/http-string")
    assert http_string_response.status_code == 404
    assert http_string_response.json() == {
        "error": "HTTP_ERROR",
        "message": "missing resource",
        "details": {"detail": "missing resource"},
    }


@pytest.mark.unit
def test_fastapi_handlers_cover_unexpected_exception_logging_and_fallback():
    app = FastAPI()
    logger = MagicMock()
    register_exception_handlers(
        app,
        debug=True,
        observability=SimpleNamespace(logger=logger),
    )

    @app.get("/unexpected")
    async def unexpected():
        raise RuntimeError("boom")

    client = _client_for_app(app)
    response = client.get("/unexpected")

    assert response.status_code == 500
    assert response.json() == {
        "error": "INTERNAL_SERVER_ERROR",
        "message": "Internal server error",
        "details": {"error": "boom", "error_type": "RuntimeError"},
    }
    logger.error.assert_called_once()

    app_with_failing_logger = FastAPI()
    failing_logger = MagicMock(side_effect=RuntimeError("sink offline"))
    register_exception_handlers(
        app_with_failing_logger,
        debug=False,
        observability=SimpleNamespace(logger=SimpleNamespace(error=failing_logger)),
    )

    @app_with_failing_logger.get("/unexpected")
    async def unexpected_with_failing_logger():
        raise RuntimeError("still boom")

    fallback_client = _client_for_app(app_with_failing_logger)
    fallback_response = fallback_client.get("/unexpected")

    assert fallback_response.status_code == 500
    assert fallback_response.json() == {
        "error": "INTERNAL_SERVER_ERROR",
        "message": "Internal server error",
        "details": {},
    }

