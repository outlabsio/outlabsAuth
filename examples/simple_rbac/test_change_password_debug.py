import asyncio
import httpx

async def test_change_password():
    base_url = "http://localhost:8003"
    
    # Login
    print("1. Logging in as writer...")
    login_response = await httpx.AsyncClient().post(
        f"{base_url}/v1/auth/login",
        json={"email": "writer@test.com", "password": "Test123!!"}
    )
    token = login_response.json()["access_token"]
    print(f"   Token: {token[:50]}...")
    
    # Change password
    print("\n2. Changing password...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/v1/users/me/change-password",
                json={"current_password": "Test123!!", "new_password": "ChangedPassword123!!"},
                headers={"Authorization": f"Bearer {token}"}
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_change_password())
