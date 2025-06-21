import pytest
from httpx import AsyncClient

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

# This data corresponds to the user created in the seed script
ADMIN_USER_DATA = {
    "email": "admin@test.com",
    "password": "a_very_secure_password"
}

async def test_successful_login(client: AsyncClient):
    """
    Tests successful user login and token generation for the seeded admin user.
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    response = await client.post("/v1/auth/login", data=login_data)
    
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"

async def test_failed_login(client: AsyncClient):
    """
    Tests that login fails with incorrect credentials.
    """
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": "wrong_password",
    }
    response = await client.post("/v1/auth/login", data=login_data)
    assert response.status_code == 401

async def test_get_me_endpoint(client: AsyncClient):
    """
    Tests the /me endpoint to retrieve the current user's profile.
    """
    # First, log in to get a token
    login_data = {
        "username": ADMIN_USER_DATA["email"],
        "password": ADMIN_USER_DATA["password"],
    }
    login_response = await client.post("/v1/auth/login", data=login_data)
    access_token = login_response.json()["access_token"]

    # Now, test the /me endpoint
    headers = {"Authorization": f"Bearer {access_token}"}
    me_response = await client.get("/v1/auth/me", headers=headers)
    
    assert me_response.status_code == 200
    user_profile = me_response.json()
    assert user_profile["email"] == ADMIN_USER_DATA["email"]
    assert user_profile["first_name"] == "Admin" 