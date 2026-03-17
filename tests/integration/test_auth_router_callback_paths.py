import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.core.exceptions import (
    InvalidCredentialsError,
    RefreshTokenInvalidError,
    TokenInvalidError,
    UserAlreadyExistsError,
)
from outlabs_auth.models.sql.enums import EntityClass
from outlabs_auth.routers import get_auth_router
from outlabs_auth.schemas.auth import (
    AcceptInviteRequest,
    ForgotPasswordRequest,
    InviteUserRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
)


class DummyObs:
    def __init__(self, user_id: str | None = None) -> None:
        self.user_id = user_id
        self.events: list[tuple[str, dict]] = []
        self.errors: list[tuple[str, str, dict]] = []

    def log_event(self, event: str, **fields) -> None:
        self.events.append((event, fields))

    def log_500_error(self, exception: Exception, **extra) -> None:
        self.errors.append((type(exception).__name__, str(exception), extra))


class DummyObservability:
    def __init__(self) -> None:
        self.info_records: list[tuple[str, dict]] = []
        self.error_records: list[tuple[str, dict]] = []
        self.logger = SimpleNamespace(info=self._info, error=self._error)

    def _info(self, event: str, **fields) -> None:
        self.info_records.append((event, fields))

    def _error(self, event: str, **fields) -> None:
        self.error_records.append((event, fields))

    async def shutdown(self) -> None:
        return None


class FakeRedis:
    def __init__(self) -> None:
        self.is_available = True
        self.calls: list[tuple[str, str, int | None]] = []
        self.counters: dict[str, int] = {}

    async def set(self, key: str, value: str, ttl: int | None = None):
        self.calls.append((key, value, ttl))
        return True

    async def increment_with_ttl(self, key: str, amount: int = 1, ttl: int | None = None):
        self.counters[key] = self.counters.get(key, 0) + amount
        return self.counters[key]

    async def disconnect(self) -> None:
        return None


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if route.path == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found for {method} {path}")


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


async def _create_user(
    auth: EnterpriseRBAC,
    session,
    *,
    email_prefix: str,
    password: str = "TestPass123!",
):
    return await auth.user_service.create_user(
        session=session,
        email=f"{email_prefix}-{_suffix()}@example.com",
        password=password,
        first_name="Test",
        last_name="User",
    )


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    auth.observability = DummyObservability()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def auth_router(auth_instance: EnterpriseRBAC):
    return get_auth_router(auth_instance, prefix="/v1/auth")


@pytest_asyncio.fixture
async def verified_auth_router(auth_instance: EnterpriseRBAC):
    return get_auth_router(auth_instance, prefix="/v1/auth", requires_verification=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_router_callback_happy_paths(
    auth_instance: EnterpriseRBAC,
    auth_router,
    verified_auth_router,
):
    get_config = _endpoint(auth_router, "/v1/auth/config", "GET")
    register = _endpoint(auth_router, "/v1/auth/register", "POST")
    login = _endpoint(auth_router, "/v1/auth/login", "POST")
    verified_login = _endpoint(verified_auth_router, "/v1/auth/login", "POST")
    refresh = _endpoint(auth_router, "/v1/auth/refresh", "POST")
    logout = _endpoint(auth_router, "/v1/auth/logout", "POST")
    forgot_password = _endpoint(auth_router, "/v1/auth/forgot-password", "POST")
    reset_password = _endpoint(auth_router, "/v1/auth/reset-password", "POST")
    invite_user = _endpoint(auth_router, "/v1/auth/invite", "POST")
    accept_invite = _endpoint(auth_router, "/v1/auth/accept-invite", "POST")

    captured: dict[str, str] = {}

    async def capture_invite(user, token, request=None):
        captured["invite_token"] = token

    async def capture_reset(user, token, request=None):
        captured["reset_token"] = token

    auth_instance.user_service.on_after_invite = capture_invite
    auth_instance.user_service.on_after_forgot_password = capture_reset

    fake_redis = FakeRedis()
    auth_instance.redis_client = fake_redis

    async with auth_instance.get_session() as session:
        permission = await auth_instance.permission_service.create_permission(
            session,
            name=f"config:{_suffix()}",
            display_name="Config Permission",
        )
        config_response = await get_config(session=session)
        assert config_response.preset == "EnterpriseRBAC"
        assert permission.name in config_response.available_permissions

        registered = await register(
            data=RegisterRequest(
                email=f"registered-{_suffix()}@example.com",
                password="Register123!",
                first_name="Registered",
                last_name="User",
            ),
            session=session,
            obs=DummyObs(),
        )
        assert registered.email.startswith("registered-")

        login_response = await login(
            data=LoginRequest(email=registered.email, password="Register123!"),
            session=session,
            obs=DummyObs(),
        )
        assert login_response.access_token
        assert login_response.refresh_token

        with pytest.raises(HTTPException) as exc:
            await verified_login(
                data=LoginRequest(email=registered.email, password="Register123!"),
                session=session,
                obs=DummyObs(),
            )
        assert exc.value.status_code == 403
        assert exc.value.detail == "Email verification required"

        registered_db = await auth_instance.user_service.get_user_by_email(session, registered.email)
        registered_db.email_verified = True
        await session.flush()

        verified_login_response = await verified_login(
            data=LoginRequest(email=registered.email, password="Register123!"),
            session=session,
            obs=DummyObs(),
        )
        assert verified_login_response.refresh_token

        refreshed = await refresh(
            data=RefreshRequest(refresh_token=login_response.refresh_token),
            session=session,
            obs=DummyObs(),
        )
        assert refreshed.access_token
        assert refreshed.refresh_token == login_response.refresh_token

        logout_result = await logout(
            data=LogoutRequest(immediate=True),
            session=session,
            auth_result={"user_id": registered_db.id, "jti": "logout-jti"},
        )
        assert logout_result is None
        assert fake_redis.calls == [("blacklist:jwt:logout-jti", "revoked", 900)]

        forgot_result = await forgot_password(
            data=ForgotPasswordRequest(email=registered.email),
            session=session,
        )
        assert forgot_result is None
        assert captured["reset_token"]

        reset_result = await reset_password(
            data=ResetPasswordRequest(token=captured["reset_token"], new_password="Reset123!"),
            session=session,
            obs=DummyObs(),
        )
        assert reset_result is None

        relogin = await login(
            data=LoginRequest(email=registered.email, password="Reset123!"),
            session=session,
            obs=DummyObs(),
        )
        assert relogin.access_token

        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"root-{_suffix()}",
            display_name="Root",
            slug=f"root-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"team-{_suffix()}",
            display_name="Team",
            slug=f"team-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"role_{_suffix()}",
            display_name="Invite Role",
            root_entity_id=root.id,
            is_global=False,
        )
        actor = await _create_user(auth_instance, session, email_prefix="inviter")

        invited = await invite_user(
            data=InviteUserRequest(
                email=f"invited-{_suffix()}@example.com",
                first_name="Invited",
                last_name="User",
                entity_id=str(team.id),
                role_ids=[str(role.id)],
            ),
            session=session,
            obs=DummyObs(str(actor.id)),
        )
        assert invited.status == "invited"
        assert captured["invite_token"]

        accepted = await accept_invite(
            data=AcceptInviteRequest(
                token=captured["invite_token"],
                new_password="Invite123!",
            ),
            session=session,
            obs=DummyObs(),
        )
        assert accepted.access_token
        assert accepted.refresh_token


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_router_callback_register_login_refresh_error_branches(
    auth_instance: EnterpriseRBAC,
    auth_router,
    monkeypatch,
):
    register = _endpoint(auth_router, "/v1/auth/register", "POST")
    login = _endpoint(auth_router, "/v1/auth/login", "POST")
    refresh = _endpoint(auth_router, "/v1/auth/refresh", "POST")

    async with auth_instance.get_session() as session:
        user = await _create_user(auth_instance, session, email_prefix="login-user")

        with pytest.raises(UserAlreadyExistsError):
            await register(
                data=RegisterRequest(
                    email=user.email,
                    password="Register123!",
                    first_name="Dup",
                    last_name="User",
                ),
                session=session,
                obs=DummyObs(),
            )

        async def raise_http_register(*args, **kwargs):
            raise HTTPException(status_code=418, detail="teapot")

        monkeypatch.setattr(auth_instance.user_service, "create_user", raise_http_register)
        with pytest.raises(HTTPException) as exc:
            await register(
                data=RegisterRequest(
                    email=f"http-{_suffix()}@example.com",
                    password="Register123!",
                ),
                session=session,
                obs=DummyObs(),
            )
        assert exc.value.status_code == 418

        async def raise_runtime_register(*args, **kwargs):
            raise RuntimeError("register exploded")

        monkeypatch.setattr(auth_instance.user_service, "create_user", raise_runtime_register)
        obs = DummyObs()
        with pytest.raises(RuntimeError):
            await register(
                data=RegisterRequest(
                    email=f"runtime-{_suffix()}@example.com",
                    password="Register123!",
                ),
                session=session,
                obs=obs,
            )
        assert obs.errors[0][0] == "RuntimeError"

        with pytest.raises(InvalidCredentialsError):
            await login(
                data=LoginRequest(email=user.email, password="WrongPass123!"),
                session=session,
                obs=DummyObs(),
            )

        async def raise_http_login(*args, **kwargs):
            raise HTTPException(status_code=429, detail="slow down")

        monkeypatch.setattr(auth_instance.auth_service, "login", raise_http_login)
        with pytest.raises(HTTPException) as exc:
            await login(
                data=LoginRequest(email=user.email, password="TestPass123!"),
                session=session,
                obs=DummyObs(),
            )
        assert exc.value.status_code == 429

        async def raise_runtime_login(*args, **kwargs):
            raise RuntimeError("login exploded")

        monkeypatch.setattr(auth_instance.auth_service, "login", raise_runtime_login)
        obs = DummyObs()
        with pytest.raises(RuntimeError):
            await login(
                data=LoginRequest(email=user.email, password="TestPass123!"),
                session=session,
                obs=obs,
            )
        assert obs.errors[0][0] == "RuntimeError"

        with pytest.raises(RefreshTokenInvalidError):
            await refresh(
                data=RefreshRequest(refresh_token="bad-token"),
                session=session,
                obs=DummyObs(),
            )

        async def raise_http_refresh(*args, **kwargs):
            raise HTTPException(status_code=400, detail="bad refresh")

        monkeypatch.setattr(auth_instance.auth_service, "refresh_access_token", raise_http_refresh)
        with pytest.raises(HTTPException) as exc:
            await refresh(
                data=RefreshRequest(refresh_token="ignored"),
                session=session,
                obs=DummyObs(),
            )
        assert exc.value.status_code == 400

        async def raise_runtime_refresh(*args, **kwargs):
            raise RuntimeError("refresh exploded")

        monkeypatch.setattr(auth_instance.auth_service, "refresh_access_token", raise_runtime_refresh)
        obs = DummyObs()
        with pytest.raises(RuntimeError):
            await refresh(
                data=RefreshRequest(refresh_token="ignored"),
                session=session,
                obs=obs,
            )
        assert obs.errors[0][0] == "RuntimeError"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_router_callback_forgot_and_reset_error_branches(
    auth_instance: EnterpriseRBAC,
    auth_router,
    monkeypatch,
):
    forgot_password = _endpoint(auth_router, "/v1/auth/forgot-password", "POST")
    reset_password = _endpoint(auth_router, "/v1/auth/reset-password", "POST")

    async with auth_instance.get_session() as session:
        user = await _create_user(auth_instance, session, email_prefix="forgot-user")

        no_user = await forgot_password(
            data=ForgotPasswordRequest(email=f"missing-{_suffix()}@example.com"),
            session=session,
        )
        assert no_user is None

        async def failing_hook(user_obj, token, request=None):
            raise RuntimeError("mail transport offline")

        auth_instance.user_service.on_after_forgot_password = failing_hook
        failed_hook_result = await forgot_password(
            data=ForgotPasswordRequest(email=user.email),
            session=session,
        )
        assert failed_hook_result is None
        assert auth_instance.observability.error_records[-1][0] == "forgot_password_error"

        async def fake_rate_limit(email: str, redis_client=None):
            return True, 90

        monkeypatch.setattr("outlabs_auth.routers.auth.check_forgot_password_rate_limit", fake_rate_limit)
        with pytest.raises(HTTPException) as exc:
            await forgot_password(
                data=ForgotPasswordRequest(email=user.email),
                session=session,
            )
        assert exc.value.status_code == 429

        with pytest.raises(TokenInvalidError):
            await reset_password(
                data=ResetPasswordRequest(token="bad-token", new_password="Reset123!"),
                session=session,
                obs=DummyObs(),
            )

        async def raise_http_reset(*args, **kwargs):
            raise HTTPException(status_code=422, detail="bad reset")

        monkeypatch.setattr(auth_instance.auth_service, "reset_password", raise_http_reset)
        with pytest.raises(HTTPException) as exc:
            await reset_password(
                data=ResetPasswordRequest(token="ignored", new_password="Reset123!"),
                session=session,
                obs=DummyObs(),
            )
        assert exc.value.status_code == 422

        async def raise_runtime_reset(*args, **kwargs):
            raise RuntimeError("reset exploded")

        monkeypatch.setattr(auth_instance.auth_service, "reset_password", raise_runtime_reset)
        obs = DummyObs()
        with pytest.raises(RuntimeError):
            await reset_password(
                data=ResetPasswordRequest(token="ignored", new_password="Reset123!"),
                session=session,
                obs=obs,
            )
        assert obs.errors[0][0] == "RuntimeError"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_router_callback_invite_and_accept_error_branches(
    auth_instance: EnterpriseRBAC,
    auth_router,
    monkeypatch,
):
    invite_user = _endpoint(auth_router, "/v1/auth/invite", "POST")
    accept_invite = _endpoint(auth_router, "/v1/auth/accept-invite", "POST")

    async with auth_instance.get_session() as session:
        root = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"root-{_suffix()}",
            display_name="Root",
            slug=f"root-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )
        team = await auth_instance.entity_service.create_entity(
            session=session,
            name=f"team-{_suffix()}",
            display_name="Team",
            slug=f"team-{_suffix()}",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=root.id,
        )
        role = await auth_instance.role_service.create_role(
            session=session,
            name=f"role_{_suffix()}",
            display_name="Role",
            root_entity_id=root.id,
            is_global=False,
        )
        actor = await _create_user(auth_instance, session, email_prefix="invite-actor")

        duplicate_email = f"dup-{_suffix()}@example.com"
        await auth_instance.user_service.invite_user(
            session,
            email=duplicate_email,
            invited_by_id=actor.id,
        )

        with pytest.raises(UserAlreadyExistsError):
            await invite_user(
                data=InviteUserRequest(
                    email=duplicate_email,
                    entity_id=str(team.id),
                    role_ids=[str(role.id)],
                ),
                session=session,
                obs=DummyObs(str(actor.id)),
            )

        async def raise_http_add_member(*args, **kwargs):
            raise HTTPException(status_code=400, detail="bad membership")

        monkeypatch.setattr(auth_instance.membership_service, "add_member", raise_http_add_member)
        with pytest.raises(HTTPException) as exc:
            await invite_user(
                data=InviteUserRequest(
                    email=f"http-{_suffix()}@example.com",
                    entity_id=str(team.id),
                    role_ids=[str(role.id)],
                ),
                session=session,
                obs=DummyObs(str(actor.id)),
            )
        assert exc.value.status_code == 400

        async def raise_runtime_invite(*args, **kwargs):
            raise RuntimeError("invite exploded")

        monkeypatch.setattr(auth_instance.user_service, "invite_user", raise_runtime_invite)
        obs = DummyObs(str(actor.id))
        with pytest.raises(RuntimeError):
            await invite_user(
                data=InviteUserRequest(email=f"runtime-{_suffix()}@example.com"),
                session=session,
                obs=obs,
            )
        assert obs.errors[0][0] == "RuntimeError"

        with pytest.raises(TokenInvalidError):
            await accept_invite(
                data=AcceptInviteRequest(token="bad-token", new_password="Accept123!"),
                session=session,
                obs=DummyObs(),
            )

        async def raise_http_accept(*args, **kwargs):
            raise HTTPException(status_code=409, detail="cannot accept")

        monkeypatch.setattr(auth_instance.auth_service, "accept_invite", raise_http_accept)
        with pytest.raises(HTTPException) as exc:
            await accept_invite(
                data=AcceptInviteRequest(token="ignored", new_password="Accept123!"),
                session=session,
                obs=DummyObs(),
            )
        assert exc.value.status_code == 409

        async def raise_runtime_accept(*args, **kwargs):
            raise RuntimeError("accept exploded")

        monkeypatch.setattr(auth_instance.auth_service, "accept_invite", raise_runtime_accept)
        obs = DummyObs()
        with pytest.raises(RuntimeError):
            await accept_invite(
                data=AcceptInviteRequest(token="ignored", new_password="Accept123!"),
                session=session,
                obs=obs,
            )
        assert obs.errors[0][0] == "RuntimeError"
