from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    EntityNotFoundError,
    InvalidCredentialsError,
    InvalidInputError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.enums import EntityClass, UserStatus
from outlabs_auth.services.user import UserService
from outlabs_auth.utils.password import verify_password


class NotificationRecorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def emit(self, event: str, data: dict) -> None:
        self.events.append((event, data))


class AuditRecorder:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def record_event(self, session, **kwargs) -> None:
        self.events.append(kwargs)


class AuthRecorder:
    def __init__(self, revoked_count: int = 0) -> None:
        self.calls: list[tuple[str, str]] = []
        self.revoked_count = revoked_count

    async def revoke_all_user_tokens(self, session, user_id, reason: str = "Revoke all sessions") -> int:
        self.calls.append((str(user_id), reason))
        return self.revoked_count


class MailRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def send_invite(self, intent) -> object:
        self.calls.append(("invite", intent))
        return type("MailResult", (), {"accepted": True})()

    async def send_forgot_password(self, intent) -> object:
        self.calls.append(("forgot_password", intent))
        return type("MailResult", (), {"accepted": True})()

    async def send_password_reset_confirmation(self, intent) -> object:
        self.calls.append(("password_reset_confirmation", intent))
        return type("MailResult", (), {"accepted": True})()

    async def send_access_granted(self, intent) -> object:
        self.calls.append(("access_granted", intent))
        return type("MailResult", (), {"accepted": True})()


def _entity(
    *,
    name: str,
    slug: str,
    parent_id=None,
    depth: int = 0,
    path: str | None = None,
) -> Entity:
    return Entity(
        name=name,
        display_name=name.title(),
        slug=slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type="organization" if parent_id is None else "team",
        parent_id=parent_id,
        depth=depth,
        path=path or f"/{slug}/",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_user_emits_notification_and_rejects_duplicate_email(
    test_session,
    auth_config: AuthConfig,
):
    recorder = NotificationRecorder()
    service = UserService(config=auth_config, notification_service=recorder)

    user = await service.create_user(
        test_session,
        email="User@Example.COM",
        password="TestPass123!",
        first_name="Alice",
        last_name="User",
    )

    assert user.email == "user@example.com"
    assert verify_password("TestPass123!", user.hashed_password)
    assert recorder.events[0][0] == "user.created"
    assert recorder.events[0][1]["email"] == "user@example.com"

    with pytest.raises(UserAlreadyExistsError):
        await service.create_user(
            test_session,
            email="user@example.com",
            password="TestPass123!",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_user_validates_root_entity_constraints(
    test_session,
    auth_config: AuthConfig,
):
    service = UserService(config=auth_config)

    root = _entity(name="tenant root", slug="tenant-root", path="/tenant-root/")
    test_session.add(root)
    await test_session.flush()

    child = _entity(
        name="tenant child",
        slug="tenant-child",
        parent_id=root.id,
        depth=1,
        path="/tenant-root/tenant-child/",
    )
    test_session.add(child)
    await test_session.flush()

    created = await service.create_user(
        test_session,
        email="tenant-user@example.com",
        password="TestPass123!",
        root_entity_id=root.id,
    )
    assert created.root_entity_id == root.id

    with pytest.raises(InvalidInputError):
        await service.create_user(
            test_session,
            email="child-root@example.com",
            password="TestPass123!",
            root_entity_id=child.id,
        )

    with pytest.raises(EntityNotFoundError):
        await service.create_user(
            test_session,
            email="missing-root@example.com",
            password="TestPass123!",
            root_entity_id=uuid4(),
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_user_fields_and_verify_email_handle_duplicate_and_missing_users(
    test_session,
    auth_config: AuthConfig,
):
    audit = AuditRecorder()
    actor_id = uuid4()
    service = UserService(config=auth_config, user_audit_service=audit)

    primary = await service.create_user(
        test_session,
        email="primary@example.com",
        password="TestPass123!",
        first_name="Primary",
        last_name="User",
    )
    secondary = await service.create_user(
        test_session,
        email="secondary@example.com",
        password="TestPass123!",
        first_name="Secondary",
        last_name="User",
    )

    updated = await service.update_user_fields(
        test_session,
        primary.id,
        email="Renamed@Example.COM",
        first_name="Renamed",
        last_name="Person",
        changed_by_id=actor_id,
    )
    assert updated.email == "renamed@example.com"
    assert updated.first_name == "Renamed"
    assert updated.last_name == "Person"
    assert [event["event_type"] for event in audit.events] == [
        "user.email_changed",
        "user.profile_updated",
    ]
    assert audit.events[0]["actor_user_id"] == actor_id
    assert audit.events[0]["before"]["email"] == "primary@example.com"
    assert audit.events[0]["after"]["email"] == "renamed@example.com"
    assert audit.events[1]["metadata"]["changed_fields"] == ["first_name", "last_name"]
    assert audit.events[1]["after"]["first_name"] == "Renamed"

    with pytest.raises(UserAlreadyExistsError):
        await service.update_user_fields(
            test_session,
            primary.id,
            email=secondary.email,
        )

    verified = await service.verify_email(test_session, primary.id)
    assert verified.email_verified is True

    changed_email = await service.update_user_fields(
        test_session,
        primary.id,
        email="changed@example.com",
    )
    assert changed_email.email_verified is False

    with pytest.raises(UserNotFoundError):
        await service.update_user_fields(test_session, uuid4(), email="missing@example.com")

    with pytest.raises(UserNotFoundError):
        await service.verify_email(test_session, uuid4())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_user_change_password_missing_and_default_hooks_are_noops(
    test_session,
    auth_config: AuthConfig,
):
    service = UserService(config=auth_config)
    user = await service.create_user(
        test_session,
        email="legacy-update@example.com",
        password="TestPass123!",
        first_name="Legacy",
        last_name="User",
    )

    updated = await service.update_user(
        test_session,
        user.id,
        first_name="Updated",
        last_name="Person",
    )
    assert updated.first_name == "Updated"
    assert updated.last_name == "Person"

    with pytest.raises(UserNotFoundError):
        await service.update_user(test_session, uuid4(), first_name="Missing")

    with pytest.raises(UserNotFoundError):
        await service.change_password_with_current(
            test_session,
            user_id=uuid4(),
            current_password="TestPass123!",
            new_password="NewPass123!",
        )

    assert await service.on_after_request_verify(user, "verify-token") is None
    assert await service.on_after_verify(user) is None
    assert await service.on_after_forgot_password(user, "reset-token") is None
    assert await service.on_failed_login("legacy-update@example.com", reason="wrong-password") is None
    assert await service.on_after_oauth_register(user, "github") is None
    assert await service.on_after_oauth_login(user, "github") is None
    assert await service.on_after_oauth_associate(user, "github") is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_default_mail_hooks_delegate_to_transactional_mail_service(
    test_session,
    auth_config: AuthConfig,
):
    mail_recorder = MailRecorder()
    service = UserService(config=auth_config, transactional_mail_service=mail_recorder)
    user = await service.create_user(
        test_session,
        email="mail-hooks@example.com",
        password="TestPass123!",
        first_name="Mail",
        last_name="Hooks",
    )
    user.invite_token_expires = datetime.now(timezone.utc) + timedelta(days=1)
    user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    user.last_password_change = datetime.now(timezone.utc)

    assert await service.send_invitation_email(user, "invite-token", target_entity_name="Internal Admin") is True
    assert await service.send_forgot_password_email(user, "reset-token") is True
    assert await service.send_password_reset_confirmation_email(user) is True
    assert await service.send_entity_access_granted_email(user, role_names=["internal_admin"]) is True
    assert await service.on_after_invite(user, "invite-token") is None
    assert await service.on_after_forgot_password(user, "reset-token") is None
    assert await service.on_after_reset_password(user) is None

    event_types = [event_type for event_type, _intent in mail_recorder.calls]
    assert event_types == [
        "invite",
        "forgot_password",
        "password_reset_confirmation",
        "access_granted",
        "invite",
        "forgot_password",
        "password_reset_confirmation",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_change_password_and_record_login_reset_security_state_and_emit_notifications(
    test_session,
    auth_config: AuthConfig,
):
    recorder = NotificationRecorder()
    audit = AuditRecorder()
    auth_recorder = AuthRecorder(revoked_count=2)
    service = UserService(
        config=auth_config,
        notification_service=recorder,
        auth_service=auth_recorder,
        user_audit_service=audit,
    )

    user = await service.create_user(
        test_session,
        email="password-user@example.com",
        password="OldPass123!",
        first_name="Password",
        last_name="User",
    )

    user.failed_login_attempts = 4
    user.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
    await test_session.flush()

    changed = await service.change_password(
        test_session,
        user_id=user.id,
        new_password="NewPass123!",
        changed_by_id=user.id,
    )
    assert verify_password("NewPass123!", changed.hashed_password)
    assert changed.last_password_change is not None
    assert changed.failed_login_attempts == 0
    assert changed.locked_until is None
    assert recorder.events[-1][0] == "user.password_changed"
    assert auth_recorder.calls == [(str(user.id), "Password changed")]
    assert audit.events[-1]["event_type"] == "user.password_changed"
    assert audit.events[-1]["actor_user_id"] == user.id
    assert audit.events[-1]["metadata"]["revoked_refresh_token_count"] == 2

    with pytest.raises(InvalidCredentialsError):
        await service.change_password_with_current(
            test_session,
            user_id=user.id,
            current_password="WrongPass123!",
            new_password="AnotherPass123!",
        )

    changed_with_current = await service.change_password_with_current(
        test_session,
        user_id=user.id,
        current_password="NewPass123!",
        new_password="NewestPass123!",
    )
    assert verify_password("NewestPass123!", changed_with_current.hashed_password)

    await service.record_login(test_session, changed_with_current, success=False)
    assert changed_with_current.failed_login_attempts == 1

    changed_with_current.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    await test_session.flush()
    await service.record_login(test_session, changed_with_current, success=True)
    assert changed_with_current.failed_login_attempts == 0
    assert changed_with_current.locked_until is None
    assert changed_with_current.last_login is not None

    with pytest.raises(UserNotFoundError):
        await service.change_password(test_session, uuid4(), "MissingPass123!")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_status_list_search_and_delete_cover_filters_and_notifications(
    test_session,
    auth_config: AuthConfig,
):
    recorder = NotificationRecorder()
    service = UserService(config=auth_config, notification_service=recorder)

    root_a = _entity(name="root a", slug="root-a", path="/root-a/")
    root_b = _entity(name="root b", slug="root-b", path="/root-b/")
    test_session.add(root_a)
    test_session.add(root_b)
    await test_session.flush()

    target = await service.create_user(
        test_session,
        email="listable@example.com",
        password="TestPass123!",
        first_name="Listable",
        last_name="Person",
        root_entity_id=root_a.id,
    )
    other = await service.create_user(
        test_session,
        email="other@example.com",
        password="TestPass123!",
        first_name="Other",
        last_name="Person",
        is_superuser=True,
        root_entity_id=root_b.id,
    )

    suspended_until = datetime.now(timezone.utc) + timedelta(hours=2)
    suspended = await service.update_user_status(
        test_session,
        target.id,
        UserStatus.SUSPENDED,
        suspended_until=suspended_until,
    )
    assert suspended.status == UserStatus.SUSPENDED
    assert suspended.suspended_until == suspended_until
    assert recorder.events[-1][0] == "user.status_changed"

    reactivated = await service.update_user_status(test_session, target.id, UserStatus.ACTIVE)
    assert reactivated.status == UserStatus.ACTIVE
    assert reactivated.suspended_until is None

    users, total = await service.list_users(
        test_session,
        page=1,
        limit=10,
        status=UserStatus.ACTIVE,
        is_superuser=False,
        root_entity_id=root_a.id,
    )
    assert total == 1
    assert [user.id for user in users] == [target.id]

    matches = await service.search_users(
        test_session,
        "Listable",
        limit=10,
        status=UserStatus.ACTIVE,
        is_superuser=False,
        root_entity_id=root_a.id,
    )
    assert [user.id for user in matches] == [target.id]

    assert await service.delete_user(test_session, other.id) is True
    assert recorder.events[-1][0] == "user.deleted"
    deleted_user = await service.get_user_by_id(test_session, other.id)
    assert deleted_user is not None
    assert deleted_user.status == UserStatus.DELETED
    assert deleted_user.deleted_at is not None
    assert await service.delete_user(test_session, other.id) is False

    with pytest.raises(UserNotFoundError):
        await service.update_user_status(test_session, uuid4(), UserStatus.ACTIVE)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invite_user_and_resend_invite_validate_lifecycle_constraints(
    test_session,
    auth_config: AuthConfig,
):
    recorder = NotificationRecorder()
    audit = AuditRecorder()
    service = UserService(
        config=auth_config,
        notification_service=recorder,
        user_audit_service=audit,
    )

    root = _entity(name="invite root", slug="invite-root", path="/invite-root/")
    test_session.add(root)
    await test_session.flush()

    child = _entity(
        name="invite child",
        slug="invite-child",
        parent_id=root.id,
        depth=1,
        path="/invite-root/invite-child/",
    )
    test_session.add(child)
    await test_session.flush()

    inviter = await service.create_user(
        test_session,
        email="inviter@example.com",
        password="TestPass123!",
        root_entity_id=root.id,
    )

    invited, plain_token = await service.invite_user(
        test_session,
        email="invitee@example.com",
        first_name="Invited",
        last_name="User",
        invited_by_id=inviter.id,
        root_entity_id=root.id,
    )
    original_hashed_token = invited.invite_token
    original_expiry = invited.invite_token_expires

    assert invited.status == UserStatus.INVITED
    assert plain_token
    assert invited.invite_token != plain_token
    assert invited.root_entity_id == root.id
    assert recorder.events[-1][0] == "user.invited"
    assert audit.events[-1]["event_type"] == "user.invited"
    assert audit.events[-1]["actor_user_id"] == inviter.id

    resent, resent_token = await service.resend_invite(
        test_session,
        invited.id,
        resent_by_id=inviter.id,
    )
    assert resent.id == invited.id
    assert resent_token != plain_token
    assert resent.invite_token != original_hashed_token
    assert resent.invite_token_expires > original_expiry
    assert audit.events[-1]["event_type"] == "user.invite_resent"
    assert audit.events[-1]["actor_user_id"] == inviter.id

    with pytest.raises(EntityNotFoundError):
        await service.invite_user(
            test_session,
            email="missing-root-invite@example.com",
            root_entity_id=uuid4(),
        )

    with pytest.raises(InvalidInputError):
        await service.invite_user(
            test_session,
            email="child-root-invite@example.com",
            root_entity_id=child.id,
        )

    with pytest.raises(UserAlreadyExistsError):
        await service.invite_user(
            test_session,
            email="invitee@example.com",
        )

    invited.status = UserStatus.ACTIVE
    await test_session.flush()

    with pytest.raises(InvalidInputError):
        await service.resend_invite(test_session, invited.id)

    with pytest.raises(UserNotFoundError):
        await service.resend_invite(test_session, uuid4())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deleted_email_remains_reserved_for_create_and_invite_flows(
    test_session,
    auth_config: AuthConfig,
):
    service = UserService(config=auth_config)

    deleted_user = await service.create_user(
        test_session,
        email="deleted-user@example.com",
        password="TestPass123!",
        first_name="Deleted",
        last_name="User",
    )

    assert await service.delete_user(test_session, deleted_user.id) is True

    retained = await service.get_user_by_id(test_session, deleted_user.id)
    assert retained is not None
    assert retained.status == UserStatus.DELETED
    assert retained.deleted_at is not None

    with pytest.raises(UserAlreadyExistsError):
        await service.create_user(
            test_session,
            email="deleted-user@example.com",
            password="TestPass123!",
        )

    with pytest.raises(UserAlreadyExistsError):
        await service.invite_user(
            test_session,
            email="deleted-user@example.com",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_restore_user_clears_deleted_state_and_emits_notification(
    test_session,
    auth_config: AuthConfig,
):
    recorder = NotificationRecorder()
    service = UserService(config=auth_config, notification_service=recorder)

    user = await service.create_user(
        test_session,
        email="restore-user@example.com",
        password="TestPass123!",
        first_name="Restore",
        last_name="User",
    )
    assert await service.delete_user(test_session, user.id) is True

    restored = await service.restore_user(test_session, user.id)
    assert restored.status == UserStatus.ACTIVE
    assert restored.deleted_at is None
    assert recorder.events[-1][0] == "user.restored"

    with pytest.raises(InvalidInputError):
        await service.restore_user(test_session, user.id)
