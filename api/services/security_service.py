from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import uuid

from ..config import settings
from ..schemas.auth_schema import TokenDataSchema

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
            token_data = TokenDataSchema(user_id=user_id, jti=payload.get("jti"))
        except JWTError:
            raise credentials_exception
        return token_data

# Instantiate the service for use in other parts of the application
security_service = SecurityService() 