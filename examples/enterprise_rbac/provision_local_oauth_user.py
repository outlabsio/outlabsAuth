#!/usr/bin/env python3
"""Provision one private, local-only account for live OAuth smoke tests.

The email is read from ``LOCAL_OAUTH_TEST_EMAIL`` in the ignored example
``.env`` file. No real identity belongs in the public seed dataset.
"""

import asyncio
import os
import secrets

from outlabs_auth import UserStatus

from main import ENV, auth


async def provision_local_oauth_user() -> None:
    if ENV == "production":
        raise RuntimeError("Local OAuth test users cannot be provisioned in production")

    email = os.getenv("LOCAL_OAUTH_TEST_EMAIL", "").strip()
    if not email:
        raise RuntimeError("Set LOCAL_OAUTH_TEST_EMAIL in examples/enterprise_rbac/.env first")

    await auth.initialize()
    try:
        async with auth.get_session() as session:
            user = await auth.user_service.get_user_by_email(session, email)
            if user is None:
                user = await auth.user_service.create_user(
                    session,
                    email=email,
                    password=f"Aa1!{secrets.token_urlsafe(44)}",
                    first_name=os.getenv("LOCAL_OAUTH_TEST_FIRST_NAME", "Local"),
                    last_name=os.getenv("LOCAL_OAUTH_TEST_LAST_NAME", "OAuth Tester"),
                    is_superuser=True,
                )

            # The unknown random password is only needed to satisfy the current
            # create-user contract. Keep this account genuinely OAuth-only.
            user.hashed_password = None
            user.auth_methods = [method for method in (user.auth_methods or []) if method != "PASSWORD"]
            user.status = UserStatus.ACTIVE
            user.email_verified = True
            user.is_superuser = True
            await session.commit()
    finally:
        await auth.shutdown()

    print("Local OAuth test user is ready.")


if __name__ == "__main__":
    asyncio.run(provision_local_oauth_user())
