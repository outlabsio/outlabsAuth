"""
Test routes to verify API is working
"""
from fastapi import APIRouter
from api.models import EntityModel, UserModel

router = APIRouter()


@router.get("/test/models")
async def test_models():
    """Test that models are properly initialized"""
    return {
        "message": "Models loaded successfully",
        "models": [
            "UserModel",
            "EntityModel",
            "EntityMembershipModel",
            "RoleModel",
            "RefreshTokenModel"
        ]
    }


@router.get("/test/db")
async def test_database():
    """Test database connection"""
    try:
        # Try to count users (should be 0 initially)
        user_count = await UserModel.count()
        entity_count = await EntityModel.count()
        
        return {
            "status": "connected",
            "user_count": user_count,
            "entity_count": entity_count
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Database not connected - running in limited mode"
        }