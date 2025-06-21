from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from jose import JWTError, jwt
import uuid
import secrets
from fastapi import HTTPException, status

from beanie import PydanticObjectId

from ..config import settings
from ..schemas.auth_schema import TokenDataSchema
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

    def decode_access_token(self, token: str) -> TokenDataSchema:
        """
        Decodes the access token and returns the payload.
        """
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
            
            client_account_id_str = payload.get("client_account_id")
            
            token_data = TokenDataSchema(
                user_id=user_id, 
                jti=payload.get("jti"),
                client_account_id=client_account_id_str  # Now using string ID
            )
        except (JWTError, Exception):
            raise credentials_exception
        return token_data
    
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