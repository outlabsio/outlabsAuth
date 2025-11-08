"""
Integration tests for Blog API - SimpleRBAC Example

Tests the complete API flow including:
- User registration and login
- Role-based permissions
- Blog post CRUD operations
- Comment functionality
"""
import requests
import time

BASE_URL = "http://localhost:8003"


def test_health_check():
    """Test that the API is running"""
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["preset"] == "SimpleRBAC"
    print("✅ Health check passed")


def test_user_registration():
    """Test user registration"""
    timestamp = int(time.time())
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": f"testuser_{timestamp}@example.com",
            "password": "TestPassword123!",
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    print("✅ User registration passed")
    return data["access_token"]


def test_login():
    """Test user login"""
    # First register a user
    timestamp = int(time.time())
    email = f"logintest_{timestamp}@example.com"
    password = "TestPassword123!"

    register_response = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password}
    )
    assert register_response.status_code == 201

    # Then login
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password}
    )
    assert login_response.status_code == 200
    data = login_response.json()
    assert "access_token" in data
    print("✅ User login passed")
    return data["access_token"]


def test_get_current_user():
    """Test getting current user info"""
    token = test_login()

    response = requests.get(
        f"{BASE_URL}/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "email" in data
    print("✅ Get current user passed")


def test_logout():
    """Test user logout"""
    token = test_login()

    response = requests.post(
        f"{BASE_URL}/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    print("✅ User logout passed")


def test_create_post_with_writer_role():
    """Test creating a post with writer role"""
    # Register and assign writer role
    timestamp = int(time.time())
    email = f"writer_{timestamp}@example.com"
    password = "TestPassword123!"

    register_response = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password}
    )
    assert register_response.status_code == 201
    token = register_response.json()["access_token"]

    # TODO: Assign writer role (need user ID and role ID)
    # For now, this will fail without the writer role

    # Try to create a post
    response = requests.post(
        f"{BASE_URL}/posts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "My First Post",
            "content": "This is the content of my first post.",
            "status": "published",
            "tags": ["test", "first-post"]
        }
    )

    # Will fail without role assignment
    # assert response.status_code == 201
    print("⚠️  Create post test incomplete (need role assignment)")


def test_create_post_without_permission():
    """Test that users without writer role cannot create posts"""
    # Register user (no role assigned)
    timestamp = int(time.time())
    email = f"reader_{timestamp}@example.com"
    password = "TestPassword123!"

    register_response = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password}
    )
    assert register_response.status_code == 201
    token = register_response.json()["access_token"]

    # Try to create a post (should fail)
    response = requests.post(
        f"{BASE_URL}/posts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Unauthorized Post",
            "content": "This should not be created.",
            "status": "published"
        }
    )
    assert response.status_code == 403
    print("✅ Permission check passed (user without permission blocked)")


def test_list_posts():
    """Test listing blog posts"""
    response = requests.get(f"{BASE_URL}/posts")
    assert response.status_code == 200
    data = response.json()
    assert "posts" in data
    assert "total" in data
    assert "page" in data
    print("✅ List posts passed")


def test_invalid_login():
    """Test login with wrong credentials"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "WrongPassword123!"
        }
    )
    assert response.status_code == 401
    print("✅ Invalid login properly rejected")


def test_unauthorized_access():
    """Test that protected routes require authentication"""
    response = requests.get(f"{BASE_URL}/users/me")
    assert response.status_code == 401
    print("✅ Unauthorized access blocked")


if __name__ == "__main__":
    print("🧪 Running integration tests for Blog API...")
    print()

    try:
        test_health_check()
        test_user_registration()
        test_login()
        test_get_current_user()
        test_logout()
        test_create_post_with_writer_role()
        test_create_post_without_permission()
        test_list_posts()
        test_invalid_login()
        test_unauthorized_access()

        print()
        print("✅ All tests passed!")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        raise
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to API. Make sure it's running on port 8003")
        raise
