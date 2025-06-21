import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
from fastapi import HTTPException
import uuid

from api.services.user_service import user_service
from api.models.user_model import UserModel
from api.models.group_model import GroupModel
from api.models.client_account_model import ClientAccountModel
from api.schemas.user_schema import UserCreateSchema, UserUpdateSchema
from api.services.security_service import security_service


class TestUserService:
    """Test suite for user service business logic with Beanie ODM."""
    
    @pytest.fixture
    def sample_user_create_schema(self):
        """Sample user creation schema for testing."""
        return UserCreateSchema(
            email="test@example.com",
            password="testpassword123",
            first_name="Test",
            last_name="User",
            is_main_client=False,
            roles=[],
            groups=[],  # New groups field
            client_account_id=str(ObjectId())
        )

    @pytest.mark.asyncio
    async def test_create_user_success(self, sample_user_create_schema):
        """Test successful user creation with Beanie ODM."""
        # Mock ClientAccountModel.get
        mock_client_account = MagicMock()
        mock_client_account.id = ObjectId()
        
        # Mock UserModel.insert
        mock_user = MagicMock()
        mock_user.id = ObjectId()
        mock_user.email = sample_user_create_schema.email
        mock_user.first_name = sample_user_create_schema.first_name
        mock_user.last_name = sample_user_create_schema.last_name
        
        with patch('api.services.user_service.ClientAccountModel') as mock_client_model, \
             patch('api.services.user_service.UserModel') as mock_user_model, \
             patch.object(security_service, 'get_password_hash', return_value='hashed_password'):
            
            mock_client_model.get = AsyncMock(return_value=mock_client_account)
            mock_user_instance = mock_user_model.return_value
            mock_user_instance.insert = AsyncMock(return_value=mock_user)
            mock_user_instance.id = mock_user.id
            mock_user_instance.email = mock_user.email
            mock_user_instance.first_name = mock_user.first_name
            mock_user_instance.last_name = mock_user.last_name
            
            result = await user_service.create_user(sample_user_create_schema)
        
        # Verify the result
        assert result is not None
        mock_user_instance.insert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_sub_user_success(self, sample_user_create_schema):
        """Test successful sub-user creation."""
        client_account_id = str(ObjectId())
        
        # Mock role service
        mock_role = MagicMock()
        mock_role.is_assignable_by_main_client = True
        
        # Mock ClientAccountModel.get and UserModel
        mock_client_account = MagicMock()
        mock_client_account.id = ObjectId()
        
        mock_user = MagicMock()
        mock_user.id = ObjectId()
        
        with patch('api.services.user_service.role_service') as mock_role_service, \
             patch('api.services.user_service.ClientAccountModel') as mock_client_model, \
             patch('api.services.user_service.UserModel') as mock_user_model, \
             patch.object(security_service, 'get_password_hash', return_value='hashed_password'):
            
            mock_role_service.get_role_by_id = AsyncMock(return_value=mock_role)
            mock_client_model.get = AsyncMock(return_value=mock_client_account)
            mock_user_instance = mock_user_model.return_value
            mock_user_instance.insert = AsyncMock(return_value=mock_user)
            mock_user_instance.is_main_client = False
            
            result = await user_service.create_sub_user(sample_user_create_schema, client_account_id)
        
        # Verify the result
        assert result is not None
        mock_user_instance.insert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self):
        """Test getting user by ID when user exists."""
        user_id = ObjectId()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.email = "test@example.com"
        
        with patch('api.services.user_service.UserModel') as mock_user_model:
            mock_user_model.get = AsyncMock(return_value=mock_user)
            
            result = await user_service.get_user_by_id(user_id)
        
        assert result == mock_user
        mock_user_model.get.assert_called_once_with(user_id)
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self):
        """Test getting user by ID when user doesn't exist."""
        user_id = ObjectId()
        
        with patch('api.services.user_service.UserModel') as mock_user_model:
            mock_user_model.get = AsyncMock(return_value=None)
            
            result = await user_service.get_user_by_id(user_id)
        
        assert result is None
        mock_user_model.get.assert_called_once_with(user_id)
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_found(self):
        """Test getting user by email when user exists."""
        email = "test@example.com"
        mock_user = MagicMock()
        mock_user.email = email
        
        with patch('api.services.user_service.UserModel') as mock_user_model:
            mock_user_model.find_one = AsyncMock(return_value=mock_user)
            
            result = await user_service.get_user_by_email(email)
        
        assert result == mock_user
        mock_user_model.find_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self):
        """Test getting user by email when user doesn't exist."""
        email = "nonexistent@example.com"
        
        with patch('api.services.user_service.UserModel') as mock_user_model:
            mock_user_model.find_one = AsyncMock(return_value=None)
            
            result = await user_service.get_user_by_email(email)
        
        assert result is None
        mock_user_model.find_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_users_without_filter(self):
        """Test getting all users without client account filter."""
        mock_users = [MagicMock(), MagicMock()]
        mock_query = MagicMock()
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=mock_users)
        
        with patch('api.services.user_service.UserModel') as mock_user_model:
            mock_user_model.find.return_value = mock_query
            
            result = await user_service.get_users(skip=0, limit=100)
        
        assert result == mock_users
        mock_user_model.find.assert_called_once()
        mock_query.skip.assert_called_once_with(0)
        mock_query.limit.assert_called_once_with(100)
    
    @pytest.mark.asyncio
    async def test_update_user_success(self):
        """Test successful user update."""
        user_id = ObjectId()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.save = AsyncMock()
        mock_user.update_timestamp = MagicMock()
        
        current_user = MagicMock()
        current_user.is_main_client = False
        
        update_data = UserUpdateSchema(first_name="Updated Name")
        
        with patch('api.services.user_service.UserModel') as mock_user_model:
            mock_user_model.get = AsyncMock(return_value=mock_user)
            
            result = await user_service.update_user(user_id, update_data, current_user)
        
        assert result == mock_user
        mock_user.save.assert_called_once()
        mock_user.update_timestamp.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_password_success(self):
        """Test successful password update."""
        user_id = ObjectId()
        new_password = "newpassword123"
        
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.save = AsyncMock()
        mock_user.update_timestamp = MagicMock()
        
        with patch('api.services.user_service.UserModel') as mock_user_model, \
             patch.object(security_service, 'get_password_hash', return_value='new_hashed_password'):
            
            mock_user_model.get = AsyncMock(return_value=mock_user)
            
            await user_service.update_password(user_id, new_password)
        
        assert mock_user.password_hash == 'new_hashed_password'
        mock_user.save.assert_called_once()
        mock_user.update_timestamp.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_user_success(self):
        """Test successful user deletion."""
        user_id = ObjectId()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.delete = AsyncMock()
        
        with patch('api.services.user_service.UserModel') as mock_user_model:
            mock_user_model.get = AsyncMock(return_value=mock_user)
            
            result = await user_service.delete_user(user_id)
        
        assert result is True
        mock_user.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_user_not_found(self):
        """Test user deletion when user doesn't exist."""
        user_id = ObjectId()
        
        with patch('api.services.user_service.UserModel') as mock_user_model:
            mock_user_model.get = AsyncMock(return_value=None)
            
            result = await user_service.delete_user(user_id)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_bulk_create_users_all_success(self):
        """Test bulk user creation with all successful creations."""
        user_data_list = [
            UserCreateSchema(
                email=f"user{i}@example.com",
                password="password123",
                first_name=f"User{i}",
                last_name="Test",
                is_main_client=False,
                roles=[],
                groups=[],
                client_account_id=str(ObjectId())
            ) for i in range(3)
        ]
        
        mock_users = [MagicMock() for _ in range(3)]
        
        # Mock successful user creation
        with patch.object(user_service, 'create_user') as mock_create:
            mock_create.side_effect = mock_users
            
            successful, failed = await user_service.bulk_create_users(user_data_list)
        
        assert len(successful) == 3
        assert len(failed) == 0
        assert mock_create.call_count == 3
    
    @pytest.mark.asyncio
    async def test_bulk_create_users_partial_failure(self):
        """Test bulk user creation with some failures."""
        user_data_list = [
            UserCreateSchema(
                email=f"user{i}@example.com",
                password="password123",
                first_name=f"User{i}",
                last_name="Test",
                is_main_client=False,
                roles=[],
                groups=[],
                client_account_id=str(ObjectId())
            ) for i in range(3)
        ]
        
        # Mock mixed success/failure
        def mock_create_side_effect(user_data):
            if "user1" in user_data.email:
                raise Exception("Creation failed")
            return MagicMock()
        
        with patch.object(user_service, 'create_user', side_effect=mock_create_side_effect):
            successful, failed = await user_service.bulk_create_users(user_data_list)
        
        assert len(successful) == 2
        assert len(failed) == 1
        assert "Creation failed" in failed[0].error 