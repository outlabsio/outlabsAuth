from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from jose import JWTError, jwt
import uuid
import secrets
from fastapi import HTTPException, status

from beanie import PydanticObjectId

from ..config import settings
from ..schemas.auth_schema import TokenDataSchema, EnrichedTokenDataSchema
from ..models.password_reset_token_model import PasswordResetTokenModel
from ..models.user_model import UserModel

# Create a password context using bcrypt, which is a strong hashing algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class SecurityService:
    """
    A service class for handling security-related operations like password hashing.
    """

    @staticmethod
    def get_password_hash(password: str) -> str:
        """
        Hashes a plain-text password.
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verifies a plain-text password against a hashed password.
        """
        return pwd_context.verify(plain_password, hashed_password)

    async def create_password_reset_token(self, user_id: PydanticObjectId) -> str:
        """
        Generates a password reset token, stores its hash, and returns the raw token using Beanie ODM.
        """
        # Get the user to create the Link
        user = await UserModel.get(user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found")
        
        # Generate a secure, URL-safe token
        raw_token = secrets.token_urlsafe(32)
        token_hash = self.get_password_hash(raw_token)
        
        expires_delta = timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
        expires_at = datetime.now(timezone.utc) + expires_delta

        reset_token_doc = PasswordResetTokenModel(
            user=user,
            token_hash=token_hash,
            expires_at=expires_at
        )
        
        await reset_token_doc.insert()
        
        return raw_token

    async def verify_password_reset_token(self, token: str) -> Optional[PasswordResetTokenModel]:
        """
        Finds a token document by hashing the raw token and checking for a match
        in the database using Beanie ODM. Returns the token document if a valid, 
        unexpired, and unused token is found, else None.
        """
        # Get all valid tokens
        tokens = await PasswordResetTokenModel.find(
            PasswordResetTokenModel.expires_at > datetime.now(timezone.utc),
            PasswordResetTokenModel.used_at == None
        ).to_list()

        # Iterate through all valid tokens to prevent timing attacks.
        for token_doc in tokens:
            if self.verify_password(token, token_doc.token_hash):
                return token_doc
        
        return None

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """
        Creates a new JWT access token.
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    async def create_enriched_access_token(self, user_id: str, client_account_id: Optional[str] = None, jti: Optional[str] = None, expires_delta: Optional[timedelta] = None):
        """
        Creates an enriched JWT access token with user permissions and role information.
        This reduces frontend API calls by including essential user data in the token.
        
        Args:
            user_id: User's ObjectId as string
            client_account_id: Client account ID as string (optional)
            jti: JWT ID for session tracking (optional)
            expires_delta: Custom expiration time (optional)
            
        Returns:
            Encoded JWT token with enriched payload
        """
        from .user_service import user_service
        from beanie import PydanticObjectId
        
        # Get user with populated roles and permissions
        user = await user_service.get_user_by_id(PydanticObjectId(user_id))
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Get effective permissions (flattened permission names)
        permissions = await user_service.get_user_effective_permissions(PydanticObjectId(user_id))
        
        # Extract role information
        roles = []
        role_scopes = set()
        for role in user.roles:
            roles.append({
                "id": str(role.id),
                "name": role.name,
                "scope": role.scope.value if hasattr(role.scope, 'value') else str(role.scope),
                "scope_id": role.scope_id
            })
            role_scopes.add(role.scope.value if hasattr(role.scope, 'value') else str(role.scope))
        
        # Build enriched payload
        to_encode = {
            # Standard claims
            "sub": user_id,
            "client_account_id": client_account_id,
            "jti": jti,
            
            # User information
            "user": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "status": user.status.value if hasattr(user.status, 'value') else str(user.status),
                "is_platform_staff": user.is_platform_staff,
                "platform_scope": user.platform_scope
            },
            
            # Authorization data
            "roles": roles,
            "permissions": sorted(list(permissions)),  # Sorted for consistent token size
            "scopes": sorted(list(role_scopes)),       # Available scopes for quick checks
            
            # Session metadata
            "session": {
                "is_main_client": user.is_main_client,
                "mfa_enabled": user.mfa_enabled,
                "locale": user.locale or "en-US"
            }
        }
        
        # Set expiration
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire, 
            "iat": datetime.now(timezone.utc)
        })
        
        # Encode JWT
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        # Check token size and optimize if needed
        if len(encoded_jwt.encode('utf-8')) > settings.MAX_JWT_SIZE_BYTES:
            # Try to optimize by reducing permission granularity
            optimized_permissions = self._optimize_permissions_for_jwt(permissions)
            to_encode["permissions"] = optimized_permissions
            
            # Re-encode with optimized permissions
            encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
            
            # If still too large, fallback to basic token
            if len(encoded_jwt.encode('utf-8')) > settings.MAX_JWT_SIZE_BYTES:
                # Log warning and fallback to basic token
                print(f"Warning: Enriched token too large ({len(encoded_jwt.encode('utf-8'))} bytes), falling back to basic token")
                basic_token_data = {
                    "sub": user_id,
                    "client_account_id": client_account_id,
                    "jti": jti
                }
                encoded_jwt = self.create_access_token(basic_token_data, expires_delta)
        
        return encoded_jwt

    def _optimize_permissions_for_jwt(self, permissions: set) -> list:
        """
        Optimize permissions for JWT payload by using hierarchical permissions and wildcards.
        
        Args:
            permissions: Set of permission names
            
        Returns:
            Optimized list of permissions using hierarchical compression
        """
        permission_list = list(permissions)
        
        # Define permission hierarchies for compression
        hierarchies = {
            # If user has all these permissions, replace with the parent
            "user:manage_all": ["user:manage_platform", "user:manage_client", "user:read_all", "user:read_platform", "user:read_client", "user:read_self"],
            "user:manage_platform": ["user:manage_client", "user:read_platform", "user:read_client", "user:read_self"],
            "user:manage_client": ["user:read_client", "user:read_self"],
            "user:read_all": ["user:read_platform", "user:read_client", "user:read_self"],
            "user:read_platform": ["user:read_client", "user:read_self"],
            
            "role:manage_all": ["role:manage_platform", "role:manage_client", "role:read_all", "role:read_platform", "role:read_client"],
            "role:manage_platform": ["role:manage_client", "role:read_platform", "role:read_client"],
            "role:manage_client": ["role:read_client"],
            "role:read_all": ["role:read_platform", "role:read_client"],
            "role:read_platform": ["role:read_client"],
            
            "group:manage_all": ["group:manage_platform", "group:manage_client", "group:read_all", "group:read_platform", "group:read_client"],
            "group:manage_platform": ["group:manage_client", "group:read_platform", "group:read_client"],
            "group:manage_client": ["group:read_client"],
            "group:read_all": ["group:read_platform", "group:read_client"],
            "group:read_platform": ["group:read_client"],
        }
        
        optimized = set(permission_list)
        
        # Check each hierarchy and compress if possible
        for parent, children in hierarchies.items():
            if all(child in optimized for child in children):
                # Remove children and add parent
                for child in children:
                    optimized.discard(child)
                optimized.add(parent)
        
        return sorted(list(optimized))

    def create_refresh_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()) # Unique ID for this token
        })
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt, to_encode["jti"], expire

    def decode_access_token(self, token: str):
        """
        Decodes the access token and returns the enriched payload.
        Now returns enriched token data by default.
        """
        from ..schemas.auth_schema import EnrichedTokenDataSchema
        
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise credentials_exception
            
            # Check if this is an enriched token (has user data)
            if "user" in payload and "permissions" in payload:
                # Return enriched token data
                return EnrichedTokenDataSchema.model_validate(payload)
            else:
                # Fallback to basic token data for any legacy tokens
                return TokenDataSchema(
                    user_id=user_id,
                    jti=payload.get("jti"),
                    client_account_id=payload.get("client_account_id")
                )
        except (JWTError, Exception):
            raise credentials_exception

    def decode_refresh_token(self, token: str) -> TokenDataSchema:
        """
        Decodes the refresh token and returns the payload.
        """
        refresh_token_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise refresh_token_exception
            
            client_account_id_str = payload.get("client_account_id")
            
            token_data = TokenDataSchema(
                user_id=user_id, 
                jti=payload.get("jti"),
                client_account_id=client_account_id_str
            )
        except (JWTError, Exception):
            raise refresh_token_exception
        return token_data

# Instantiate the service for use in other parts of the application
security_service = SecurityService() 