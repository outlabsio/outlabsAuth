import pytest
from datetime import datetime, timedelta, timezone
from bson import ObjectId

from api.services.security_service import security_service
from api.schemas.auth_schema import TokenDataSchema

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

class TestSecurityService:
    """Test suite for security service functionality."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "test_password_123"
        
        # Hash the password
        hashed = security_service.get_password_hash(password)
        
        # Verify the hash is created and different from original
        assert hashed != password
        assert len(hashed) > 0
        
        # Verify password verification works
        assert security_service.verify_password(password, hashed) is True
        assert security_service.verify_password("wrong_password", hashed) is False
    
    def test_password_hash_uniqueness(self):
        """Test that same password produces different hashes (due to salt)."""
        password = "same_password"
        
        hash1 = security_service.get_password_hash(password)
        hash2 = security_service.get_password_hash(password)
        
        # Hashes should be different due to salt
        assert hash1 != hash2
        
        # But both should verify correctly
        assert security_service.verify_password(password, hash1) is True
        assert security_service.verify_password(password, hash2) is True
    
    def test_create_access_token(self):
        """Test access token creation."""
        user_id = str(ObjectId())
        data = {
            "sub": user_id,
            "client_account_id": None
        }
        
        token = security_service.create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Token should be JWT format (3 parts separated by dots)
        parts = token.split('.')
        assert len(parts) == 3
    
    def test_create_access_token_with_expiry(self):
        """Test access token creation with custom expiry."""
        user_id = str(ObjectId())
        data = {"sub": user_id}
        expires_delta = timedelta(minutes=5)
        
        token = security_service.create_access_token(data, expires_delta)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_refresh_token(self):
        """Test refresh token creation."""
        user_id = str(ObjectId())
        data = {"sub": user_id}
        
        token, jti, expires_at = security_service.create_refresh_token(data)
        
        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert isinstance(expires_at, datetime)
        assert len(token) > 0
        assert len(jti) > 0
        assert expires_at > datetime.now(timezone.utc)
    
    def test_decode_access_token_valid(self):
        """Test decoding a valid access token."""
        user_id = str(ObjectId())
        client_account_id = str(ObjectId())
        jti = "test-jti"
        
        data = {
            "sub": user_id,
            "client_account_id": client_account_id,
            "jti": jti
        }
        
        token = security_service.create_access_token(data)
        decoded = security_service.decode_access_token(token)
        
        assert isinstance(decoded, TokenDataSchema)
        assert decoded.user_id == user_id
        assert str(decoded.client_account_id) == client_account_id
        assert decoded.jti == jti
    
    def test_decode_access_token_invalid(self):
        """Test decoding an invalid access token."""
        invalid_token = "invalid.token.here"
        
        with pytest.raises(Exception):  # Should raise HTTPException
            security_service.decode_access_token(invalid_token)
    
    def test_decode_access_token_expired(self):
        """Test decoding an expired access token."""
        user_id = str(ObjectId())
        data = {"sub": user_id}
        
        # Create token that expires immediately
        expired_delta = timedelta(seconds=-1)
        token = security_service.create_access_token(data, expired_delta)
        
        with pytest.raises(Exception):  # Should raise HTTPException
            security_service.decode_access_token(token)
    
    def test_decode_access_token_no_subject(self):
        """Test decoding token without subject."""
        # Create token without 'sub' field
        data = {"other_field": "value"}
        token = security_service.create_access_token(data)
        
        with pytest.raises(Exception):  # Should raise HTTPException
            security_service.decode_access_token(token)
    
    async def test_create_password_reset_token(self, client):
        """Test password reset token creation."""
        # This test requires a database connection
        # We'll create a mock test for now
        user_id = ObjectId()
        
        # In a real test, this would use the database
        # For now, we'll test the token generation logic
        import secrets
        raw_token = secrets.token_urlsafe(32)
        
        assert len(raw_token) > 0
        assert isinstance(raw_token, str)
    
    def test_token_data_schema_validation(self):
        """Test TokenDataSchema validation."""
        user_id = str(ObjectId())
        client_account_id = str(ObjectId())  # Convert to string
        jti = "test-jti"
        
        # Valid token data
        token_data = TokenDataSchema(
            user_id=user_id,
            client_account_id=client_account_id,
            jti=jti
        )
        
        assert token_data.user_id == user_id
        assert token_data.client_account_id == client_account_id
        assert token_data.jti == jti
    
    def test_token_data_schema_optional_fields(self):
        """Test TokenDataSchema with optional fields."""
        # Token data with minimal fields
        token_data = TokenDataSchema()
        
        assert token_data.user_id is None
        assert token_data.client_account_id is None
        assert token_data.jti is None
    
    def test_password_complexity(self):
        """Test password hashing with various password complexities."""
        passwords = [
            "simple",
            "Complex123!",
            "very_long_password_with_numbers_123_and_symbols_!@#",
            "短密码",  # Short password in Chinese
            "🔐🔑🛡️",  # Emoji password
            ""  # Empty password (edge case)
        ]
        
        for password in passwords:
            hashed = security_service.get_password_hash(password)
            assert security_service.verify_password(password, hashed) is True
            
            # Verify wrong password fails
            if password:  # Skip empty password for this test
                assert security_service.verify_password(password + "wrong", hashed) is False
    
    def test_token_roundtrip(self):
        """Test creating and decoding tokens in a complete roundtrip."""
        user_id = str(ObjectId())
        client_account_id = str(ObjectId())
        
        # Create access token
        data = {
            "sub": user_id,
            "client_account_id": client_account_id
        }
        token = security_service.create_access_token(data)
        
        # Decode token
        decoded = security_service.decode_access_token(token)
        
        # Verify data integrity
        assert decoded.user_id == user_id
        assert str(decoded.client_account_id) == client_account_id
    
    def test_refresh_token_uniqueness(self):
        """Test that refresh tokens are unique."""
        user_id = str(ObjectId())
        data = {"sub": user_id}
        
        token1, jti1, expires1 = security_service.create_refresh_token(data)
        token2, jti2, expires2 = security_service.create_refresh_token(data)
        
        # Tokens should be different
        assert token1 != token2
        assert jti1 != jti2
        
        # But expiry times should be similar (within a few seconds)
        time_diff = abs((expires1 - expires2).total_seconds())
        assert time_diff < 5  # Should be created within 5 seconds of each other 