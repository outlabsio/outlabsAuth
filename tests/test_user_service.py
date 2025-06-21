import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
from fastapi import HTTPException
import uuid

from api.services.user_service import user_service
from api.models.user_model import UserModel
from api.schemas.user_schema import UserCreateSchema, UserUpdateSchema
from api.services.security_service import security_service


class TestUserService:
    """Test suite for user service business logic."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database for testing."""
        db = MagicMock()
        db.users = MagicMock()  # Use MagicMock instead of AsyncMock for the collection
        # Async methods should return AsyncMock
        db.users.insert_one = AsyncMock()
        db.users.find_one = AsyncMock()
        db.users.update_one = AsyncMock() 
        db.users.delete_one = AsyncMock()
        # find() method should return a synchronous cursor
        db.users.find = MagicMock()
        return db
    
    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing."""
        return {
            "_id": ObjectId(),
            "email": "test@example.com",
            "password_hash": "hashed_password",
            "first_name": "Test",
            "last_name": "User",
            "is_active": True,
            "is_main_client": False,
            "roles": [],
            "client_account_id": ObjectId()
        }
    
    @pytest.fixture
    def sample_user_create_schema(self):
        """Sample user creation schema for testing."""
        return UserCreateSchema(
            email="test@example.com",
            password="testpassword123",
            first_name="Test",
            last_name="User",
            is_active=True,
            is_main_client=False,
            roles=[],
            client_account_id=str(ObjectId())
        )
    
    @pytest.fixture
    def sample_user_model(self, sample_user_data):
        """Sample user model for testing."""
        return UserModel(**sample_user_data)

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_db, sample_user_create_schema):
        """Test successful user creation."""
        # Mock the database insert
        mock_db.users.insert_one.return_value = AsyncMock()
        mock_db.users.insert_one.return_value.inserted_id = ObjectId()
        
        # Mock password hashing
        with patch.object(security_service, 'get_password_hash', return_value='hashed_password'):
            result = await user_service.create_user(mock_db, sample_user_create_schema)
        
        # Verify the result
        assert isinstance(result, UserModel)
        assert result.email == sample_user_create_schema.email
        assert result.first_name == sample_user_create_schema.first_name
        assert result.last_name == sample_user_create_schema.last_name
        
        # Verify database interaction
        mock_db.users.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_sub_user_success(self, mock_db, sample_user_create_schema):
        """Test successful sub-user creation."""
        client_account_id = ObjectId()
        
        # Mock role service
        with patch('api.services.user_service.role_service') as mock_role_service:
            mock_role_service.get_role_by_id.return_value = AsyncMock()
            mock_role_service.get_role_by_id.return_value.is_assignable_by_main_client = True
            
            # Mock database insert
            mock_db.users.insert_one.return_value = AsyncMock()
            mock_db.users.insert_one.return_value.inserted_id = ObjectId()
            
            # Mock password hashing
            with patch.object(security_service, 'get_password_hash', return_value='hashed_password'):
                result = await user_service.create_sub_user(mock_db, sample_user_create_schema, client_account_id)
        
        # Verify the result
        assert isinstance(result, UserModel)
        assert result.is_main_client == False
        
        # Verify database interaction
        mock_db.users.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_sub_user_invalid_role(self, mock_db, sample_user_create_schema):
        """Test sub-user creation with invalid role."""
        client_account_id = ObjectId()
        sample_user_create_schema.roles = [str(ObjectId())]
        
        # Mock role service to return non-assignable role
        with patch('api.services.user_service.role_service') as mock_role_service:
            mock_role = MagicMock()
            mock_role.is_assignable_by_main_client = False
            mock_role_service.get_role_by_id = AsyncMock(return_value=mock_role)
            
            # Should raise HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await user_service.create_sub_user(mock_db, sample_user_create_schema, client_account_id)
            
            assert exc_info.value.status_code == 403
    
    @pytest.mark.asyncio
    async def test_create_sub_user_role_not_found(self, mock_db, sample_user_create_schema):
        """Test sub-user creation with non-existent role."""
        client_account_id = ObjectId()
        sample_user_create_schema.roles = [str(ObjectId())]
        
        # Mock role service to return None (role not found)
        with patch('api.services.user_service.role_service') as mock_role_service:
            mock_role_service.get_role_by_id = AsyncMock(return_value=None)
            
            # Should raise HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await user_service.create_sub_user(mock_db, sample_user_create_schema, client_account_id)
            
            assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self, mock_db, sample_user_data):
        """Test getting user by ID when user exists."""
        user_id = ObjectId()
        mock_db.users.find_one.return_value = sample_user_data
        
        result = await user_service.get_user_by_id(mock_db, user_id)
        
        assert isinstance(result, UserModel)
        assert result.email == sample_user_data["email"]
        mock_db.users.find_one.assert_called_once_with({"_id": user_id})
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, mock_db):
        """Test getting user by ID when user doesn't exist."""
        user_id = ObjectId()
        mock_db.users.find_one.return_value = None
        
        result = await user_service.get_user_by_id(mock_db, user_id)
        
        assert result is None
        mock_db.users.find_one.assert_called_once_with({"_id": user_id})
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_found(self, mock_db, sample_user_data):
        """Test getting user by email when user exists."""
        email = "test@example.com"
        mock_db.users.find_one.return_value = sample_user_data
        
        result = await user_service.get_user_by_email(mock_db, email)
        
        assert isinstance(result, UserModel)
        assert result.email == sample_user_data["email"]
        mock_db.users.find_one.assert_called_once_with({"email": email})
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self, mock_db):
        """Test getting user by email when user doesn't exist."""
        email = "nonexistent@example.com"
        mock_db.users.find_one.return_value = None
        
        result = await user_service.get_user_by_email(mock_db, email)
        
        assert result is None
        mock_db.users.find_one.assert_called_once_with({"email": email})
    
    @pytest.mark.asyncio
    async def test_get_users_without_filter(self, mock_db, sample_user_data):
        """Test getting all users without client account filter."""
        # Set up the mock chain correctly - find() should return a synchronous cursor mock
        mock_cursor = MagicMock()  # Use MagicMock instead of AsyncMock for the cursor itself
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=[sample_user_data])
        
        mock_db.users.find.return_value = mock_cursor

        result = await user_service.get_users(mock_db, skip=0, limit=100)
        
        assert len(result) == 1
        assert result[0].email == sample_user_data["email"]
        mock_db.users.find.assert_called_once_with({})
    
    @pytest.mark.asyncio
    async def test_get_users_with_client_filter(self, mock_db, sample_user_data):
        """Test getting users filtered by client account."""
        client_account_id = ObjectId()
        
        # Set up the mock chain correctly - find() should return a synchronous cursor mock
        mock_cursor = MagicMock()  # Use MagicMock instead of AsyncMock for the cursor itself
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=[sample_user_data])
        
        mock_db.users.find.return_value = mock_cursor

        result = await user_service.get_users(mock_db, skip=0, limit=100, client_account_id=client_account_id)
        
        assert len(result) == 1
        assert result[0].email == sample_user_data["email"]
        mock_db.users.find.assert_called_once_with({"client_account_id": client_account_id})
    
    @pytest.mark.asyncio
    async def test_update_user_success(self, mock_db, sample_user_model):
        """Test successful user update."""
        user_id = ObjectId()
        update_data = UserUpdateSchema(first_name="Updated Name")
        
        # Mock the update and get operations
        mock_db.users.update_one.return_value = AsyncMock()
        
        with patch.object(user_service, 'get_user_by_id', return_value=sample_user_model):
            result = await user_service.update_user(mock_db, user_id, update_data, sample_user_model)
        
        assert isinstance(result, UserModel)
        mock_db.users.update_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_user_with_roles_by_main_client(self, mock_db, sample_user_model):
        """Test user update with roles by main client."""
        user_id = ObjectId()
        sample_user_model.is_main_client = True
        update_data = UserUpdateSchema(roles=[str(ObjectId())])
        
        # Mock role service
        with patch('api.services.user_service.role_service') as mock_role_service:
            mock_role = MagicMock()
            mock_role.is_assignable_by_main_client = True
            mock_role_service.get_role_by_id = AsyncMock(return_value=mock_role)
            
            # Mock the update and get operations
            mock_db.users.update_one = AsyncMock()
            
            with patch.object(user_service, 'get_user_by_id', return_value=sample_user_model):
                result = await user_service.update_user(mock_db, user_id, update_data, sample_user_model)
        
        assert isinstance(result, UserModel)
        mock_db.users.update_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_user_invalid_role_assignment(self, mock_db, sample_user_model):
        """Test user update with invalid role assignment by main client."""
        user_id = ObjectId()
        sample_user_model.is_main_client = True
        update_data = UserUpdateSchema(roles=[str(ObjectId())])
        
        # Mock role service to return non-assignable role
        with patch('api.services.user_service.role_service') as mock_role_service:
            mock_role = MagicMock()
            mock_role.is_assignable_by_main_client = False
            mock_role_service.get_role_by_id = AsyncMock(return_value=mock_role)
            
            # Should raise HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await user_service.update_user(mock_db, user_id, update_data, sample_user_model)
            
            assert exc_info.value.status_code == 403
    
    @pytest.mark.asyncio
    async def test_update_password_success(self, mock_db):
        """Test successful password update."""
        user_id = ObjectId()
        new_password = "newpassword123"
        
        # Mock password hashing and database update
        with patch.object(security_service, 'get_password_hash', return_value='new_hashed_password'):
            mock_db.users.update_one.return_value = AsyncMock()
            
            await user_service.update_password(mock_db, user_id=user_id, new_password=new_password)
        
        mock_db.users.update_one.assert_called_once_with(
            {"_id": user_id},
            {"$set": {"password_hash": "new_hashed_password"}}
        )
    
    @pytest.mark.asyncio
    async def test_delete_user_success(self, mock_db):
        """Test successful user deletion."""
        user_id = ObjectId()
        mock_result = AsyncMock()
        mock_result.deleted_count = 1
        mock_db.users.delete_one.return_value = mock_result
        
        result = await user_service.delete_user(mock_db, user_id)
        
        assert result == 1
        mock_db.users.delete_one.assert_called_once_with({"_id": user_id})
    
    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, mock_db):
        """Test user deletion when user doesn't exist."""
        user_id = ObjectId()
        mock_result = AsyncMock()
        mock_result.deleted_count = 0
        mock_db.users.delete_one.return_value = mock_result
        
        result = await user_service.delete_user(mock_db, user_id)
        
        assert result == 0
        mock_db.users.delete_one.assert_called_once_with({"_id": user_id})
    
    @pytest.mark.asyncio
    async def test_bulk_create_users_all_success(self, mock_db):
        """Test bulk user creation with all successful creations."""
        user_data_list = [
            UserCreateSchema(
                email=f"user{i}@example.com",
                password="password123",
                first_name=f"User{i}",
                last_name="Test",
                is_active=True,
                is_main_client=False,
                roles=[],
                client_account_id=str(ObjectId())
            ) for i in range(3)
        ]
        
        # Mock successful user creation
        with patch.object(user_service, 'create_user') as mock_create:
            mock_create.side_effect = [
                UserModel(
                    email=f"user{i}@example.com", 
                    password_hash="hashed_password",
                    first_name=f"User{i}",
                    last_name="Test",
                    id=ObjectId()
                ) for i in range(3)
            ]
            
            successful, failed = await user_service.bulk_create_users(mock_db, user_data_list)
        
        assert len(successful) == 3
        assert len(failed) == 0
        assert mock_create.call_count == 3
    
    @pytest.mark.asyncio
    async def test_bulk_create_users_partial_failure(self, mock_db):
        """Test bulk user creation with some failures."""
        user_data_list = [
            UserCreateSchema(
                email=f"user{i}@example.com",
                password="password123",
                first_name=f"User{i}",
                last_name="Test",
                is_active=True,
                is_main_client=False,
                roles=[],
                client_account_id=str(ObjectId())
            ) for i in range(3)
        ]
        
        # Mock mixed success/failure
        def mock_create_side_effect(db, user_data):
            if "user1" in user_data.email:
                raise Exception("Creation failed")
            return UserModel(
                email=user_data.email, 
                password_hash="hashed_password",
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                id=ObjectId()
            )
        
        with patch.object(user_service, 'create_user', side_effect=mock_create_side_effect):
            successful, failed = await user_service.bulk_create_users(mock_db, user_data_list)
        
        assert len(successful) == 2
        assert len(failed) == 1
        assert failed[0].error == "Creation failed" 