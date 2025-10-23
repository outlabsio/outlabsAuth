# Installation Guide

**Tags**: #getting-started #installation #setup

Complete guide to installing OutlabsAuth with different configurations.

---

## Requirements

### Python Version
- **Python 3.12+** (required)
- Tested on Python 3.12, 3.13

### Database
- **MongoDB 5.0+** (required)
  - Local installation, Docker, or cloud (MongoDB Atlas)
  - Connection via `motor` (async MongoDB driver)

### Optional Dependencies
- **Redis 6.0+** (recommended for production)
  - Caching, counters, pub/sub
- **SMTP Server** (for email verification)
  - SendGrid, AWS SES, Mailgun, or local SMTP

---

## Installation Options

### Option 1: Core Installation (Minimal)

Install just the core authentication and authorization features:

```bash
pip install outlabs-auth
```

**Includes**:
- ✅ Email/password authentication
- ✅ JWT access and refresh tokens
- ✅ API keys (argon2id hashing)
- ✅ SimpleRBAC and EnterpriseRBAC
- ✅ Entity hierarchy and tree permissions
- ✅ Lifecycle hooks
- ❌ OAuth/social login
- ❌ Redis caching
- ❌ Notification system

**Dependencies**:
- `fastapi>=0.110.0`
- `motor>=3.3.2` (async MongoDB)
- `beanie>=1.23.0` (ODM)
- `pydantic>=2.5.0`
- `python-jose[cryptography]>=3.3.0` (JWT)
- `passlib[argon2]>=1.7.4` (password hashing)
- `makefun>=1.15.0` (dynamic dependencies)

**Use Case**: Simple applications, rapid prototyping, minimal dependencies

---

### Option 2: OAuth Support

Add OAuth/social login support:

```bash
pip install outlabs-auth[oauth]
```

**Includes**: Core + OAuth

**Additional Dependencies**:
- `httpx-oauth>=0.13.0` (async OAuth clients)

**Supported Providers**:
- Google
- Facebook
- GitHub
- Microsoft
- Discord
- Twitter/X

**Use Case**: Applications that need social login

---

### Option 3: Redis Caching

Add Redis for performance optimization:

```bash
pip install outlabs-auth[redis]
```

**Includes**: Core + Redis

**Additional Dependencies**:
- `redis>=5.0.0` (async Redis client)

**Features**:
- Permission check caching (10x-100x speedup)
- Role lookup caching
- Entity hierarchy caching
- API key usage counters (99%+ write reduction)
- Pub/Sub cache invalidation across instances

**Use Case**: Production deployments, high-traffic applications

---

### Option 4: Notification System (v1.1)

Add notification support:

```bash
pip install outlabs-auth[notifications]
```

**Includes**: Core + Notifications

**Additional Dependencies**:
- `aiosmtplib>=3.0.0` (async email)
- `jinja2>=3.1.0` (email templates)
- `twilio>=8.0.0` (SMS, optional)

**Features**:
- Welcome emails
- Password reset emails
- Email verification
- Security alerts
- Webhook notifications
- SMS notifications (optional)

**Use Case**: Applications that need user notifications

---

### Option 5: Complete Installation (Recommended for Production)

Install everything:

```bash
pip install outlabs-auth[all]
```

**Includes**: Core + OAuth + Redis + Notifications

**Use Case**: Production applications with all features

---

## Installation Methods

### pip (PyPI)

```bash
# Latest stable release
pip install outlabs-auth

# Specific version
pip install outlabs-auth==1.5.0

# With extras
pip install outlabs-auth[oauth,redis]
```

### uv (Recommended for Development)

```bash
# Add to project
uv add outlabs-auth

# With extras
uv add "outlabs-auth[all]"

# Development installation (editable)
git clone https://github.com/outlabsio/outlabsAuth.git
cd outlabsAuth
uv sync --extra all
```

### poetry

```bash
# Add to project
poetry add outlabs-auth

# With extras
poetry add "outlabs-auth[oauth,redis]"
```

### pipenv

```bash
# Add to project
pipenv install outlabs-auth

# With extras
pipenv install "outlabs-auth[all]"
```

---

## MongoDB Setup

### Option 1: Local MongoDB (Development)

**Docker** (easiest):
```bash
# Start MongoDB container
docker run -d \
  --name mongodb \
  -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=password \
  mongo:latest

# Connection string
mongodb://admin:password@localhost:27017
```

**Homebrew** (macOS):
```bash
# Install
brew install mongodb-community

# Start service
brew services start mongodb-community

# Connection string
mongodb://localhost:27017
```

**apt** (Ubuntu/Debian):
```bash
# Install
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update
sudo apt install -y mongodb-org

# Start service
sudo systemctl start mongod

# Connection string
mongodb://localhost:27017
```

### Option 2: MongoDB Atlas (Production)

**Free tier** (512 MB storage, shared):

1. Sign up at https://www.mongodb.com/cloud/atlas
2. Create free cluster (M0)
3. Create database user
4. Whitelist IP addresses (or 0.0.0.0/0 for development)
5. Get connection string:

```
mongodb+srv://username:password@cluster.mongodb.net/myapp?retryWrites=true&w=majority
```

**Pricing**:
- M0 (Free): 512 MB, shared
- M2 ($9/mo): 2 GB, shared
- M5 ($25/mo): 5 GB, dedicated

---

## Redis Setup (Optional)

### Option 1: Local Redis (Development)

**Docker** (easiest):
```bash
# Start Redis container
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:latest

# Connection string
redis://localhost:6379
```

**Homebrew** (macOS):
```bash
# Install
brew install redis

# Start service
brew services start redis

# Connection string
redis://localhost:6379
```

**apt** (Ubuntu/Debian):
```bash
# Install
sudo apt update
sudo apt install redis-server

# Start service
sudo systemctl start redis-server

# Connection string
redis://localhost:6379
```

### Option 2: Redis Cloud (Production)

**Free tier** (30 MB):

1. Sign up at https://redis.com/try-free/
2. Create free database
3. Get connection string:

```
redis://username:password@redis-12345.c123.us-east-1-1.ec2.cloud.redislabs.com:12345
```

**Pricing**:
- Free: 30 MB
- $5/mo: 100 MB
- $10/mo: 250 MB

---

## Verify Installation

Create a test file to verify everything is working:

```python
# test_installation.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC

async def main():
    # Connect to MongoDB
    mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = mongo_client["test_outlabs_auth"]

    # Initialize OutlabsAuth
    auth = SimpleRBAC(database=db)

    # Initialize database (creates indexes)
    await auth.initialize()

    print("✅ OutlabsAuth installed successfully!")
    print(f"✅ MongoDB connection: OK")
    print(f"✅ SimpleRBAC initialized: OK")

    # Check optional dependencies
    try:
        from httpx_oauth.clients.google import GoogleOAuth2
        print("✅ OAuth support: Available")
    except ImportError:
        print("⚠️  OAuth support: Not installed (pip install outlabs-auth[oauth])")

    try:
        import redis.asyncio as redis
        print("✅ Redis support: Available")
    except ImportError:
        print("⚠️  Redis support: Not installed (pip install outlabs-auth[redis])")

    # Cleanup
    await mongo_client.drop_database("test_outlabs_auth")
    mongo_client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

Run the test:

```bash
python test_installation.py
```

Expected output:
```
✅ OutlabsAuth installed successfully!
✅ MongoDB connection: OK
✅ SimpleRBAC initialized: OK
✅ OAuth support: Available
✅ Redis support: Available
```

---

## Project Structure

Recommended project structure for FastAPI + OutlabsAuth:

```
myapp/
├── main.py                  # FastAPI app with OutlabsAuth
├── requirements.txt         # Dependencies
├── .env                     # Environment variables
├── config.py               # Configuration
├── models/                 # Custom Pydantic models
├── routers/                # Custom FastAPI routers
├── services/               # Custom business logic
└── tests/                  # Tests
    ├── test_auth.py
    └── test_permissions.py
```

**Minimal Example** (`main.py`):

```python
from fastapi import FastAPI, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC
from outlabs_auth.routers import get_auth_router, get_users_router

# FastAPI app
app = FastAPI(title="My App")

# MongoDB connection
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["myapp"]

# Initialize authentication
auth = SimpleRBAC(database=db)

# Initialize database on startup
@app.on_event("startup")
async def startup():
    await auth.initialize()

# Add authentication routes
app.include_router(
    get_auth_router(auth),
    prefix="/auth",
    tags=["auth"]
)

app.include_router(
    get_users_router(auth),
    prefix="/users",
    tags=["users"]
)

# Protected route example
@app.get("/protected")
async def protected_route(ctx = Depends(auth.deps.require_auth())):
    return {"message": f"Hello user {ctx['user_id']}!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Environment Variables

Create `.env` file for configuration:

```bash
# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=myapp

# JWT Secret (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET=your-super-secret-jwt-key-change-this-in-production

# OAuth (if using)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
OAUTH_STATE_SECRET=different-secret-from-jwt

# Redis (if using)
REDIS_URL=redis://localhost:6379

# Email (if using notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@yourapp.com
```

**Load environment variables**:

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "myapp"
    jwt_secret: str
    google_client_id: str | None = None
    google_client_secret: str | None = None
    oauth_state_secret: str | None = None
    redis_url: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Next Steps

Now that OutlabsAuth is installed:

1. **Choose your preset**: [[41-SimpleRBAC|SimpleRBAC]] or [[42-EnterpriseRBAC|EnterpriseRBAC]]
2. **Add OAuth** (optional): [[31-OAuth-Setup|OAuth Setup Guide]]
3. **Configure Redis** (optional): [[120-Redis-Integration|Redis Integration]]
4. **Follow tutorial**: [[150-Tutorial-Simple-App|Build Your First App]]

---

## Troubleshooting

### Import Error

```
ModuleNotFoundError: No module named 'outlabs_auth'
```

**Solution**: Make sure package is installed:
```bash
pip list | grep outlabs-auth
pip install outlabs-auth
```

### MongoDB Connection Error

```
pymongo.errors.ServerSelectionTimeoutError: localhost:27017: [Errno 61] Connection refused
```

**Solution**: Make sure MongoDB is running:
```bash
# Docker
docker ps | grep mongo

# Start if not running
docker start mongodb
```

### OAuth Import Error

```
ModuleNotFoundError: No module named 'httpx_oauth'
```

**Solution**: Install OAuth dependencies:
```bash
pip install outlabs-auth[oauth]
```

### Redis Connection Error

```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solution**: Make sure Redis is running:
```bash
# Docker
docker ps | grep redis

# Start if not running
docker start redis
```

### Pydantic Version Conflict

```
ImportError: cannot import name 'Field' from 'pydantic'
```

**Solution**: Upgrade to Pydantic v2:
```bash
pip install --upgrade pydantic>=2.5.0
```

---

## Upgrade Guide

### From v1.4 to v1.5

```bash
# Upgrade package
pip install --upgrade outlabs-auth

# No breaking changes, fully backward compatible
```

### From v1.3 to v1.4

```bash
# Upgrade package
pip install --upgrade outlabs-auth

# Breaking changes:
# - Renamed preset classes (SimplePreset → SimpleRBAC, EnterprisePreset → EnterpriseRBAC)
# - Update imports in your code
```

See [[172-Migration-Version-Guide|Version Migration Guide]] for detailed upgrade instructions.

---

**Previous**: [[02-Quick-Start|← Quick Start]]
**Next**: [[04-Basic-Concepts|Basic Concepts →]]
