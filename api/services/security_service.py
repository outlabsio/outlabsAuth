from passlib.context import CryptContext

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

# Instantiate the service for use in other parts of the application
security_service = SecurityService() 