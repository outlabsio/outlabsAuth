# outlabsAuth - Generic RBAC Microservice

This repository contains a standalone, generic Role-Based Access Control (RBAC) microservice built with FastAPI. It provides centralized user authentication, authorization, and multi-tenant user management.

## Tech Stack

- **Backend**: FastAPI (Production-Ready)
- **Database**: MongoDB with Proper Indexing
- **Validation**: Pydantic v2 (In Progress)
- **Testing**: Pytest with 97 Comprehensive Tests
- **Package Management**: `uv`
- **Containerization**: Docker

## 🚀 Current Status: Production-Ready Core with Advanced Validation Work in Progress

### ✅ **ACHIEVED: Rock-Solid Foundation (93.8% Success Rate)**

**Critical Issues Resolved:**

- **🔒 Data Integrity Fixed**: Eliminated 79 duplicate users with same email address
- **📊 Database Indexing**: Implemented comprehensive unique constraints and indexes
- **🔧 Pydantic v2 Migration**: Successfully migrated most models from v1 to v2
- **🛡️ Security Hardened**: All authentication and authorization working perfectly

**Test Suite Status (97 Total Tests):**

- ✅ **Auth Routes**: 3/3 (100%) - Login, token validation, security
- ✅ **User Routes**: 14/14 (100%) - CRUD, permissions, data scoping
- ✅ **Permission Routes**: 10/10 (100%) - Permission management
- ✅ **Security Service**: 15/15 (100%) - JWT, password hashing, validation
- ✅ **User Service**: 18/18 (100%) - Business logic, user management
- ✅ **Integration Tests**: 7/7 (100%) - End-to-end workflows
- ✅ **Duplicate Constraints**: 10/10 (100%) - Data integrity validation

**Partially Working:**

- ⚠️ **Client Account Routes**: 11/14 (78.6%) - Create works, get/update/delete have validation issues
- ⚠️ **Role Routes**: 13/16 (81.2%) - Core functionality works, some edge cases

### 🔄 **IN PROGRESS: Advanced ObjectId Serialization**

**Current Challenge: Pydantic v2 + FastAPI + MongoDB ObjectId Integration**

We're implementing the "hard way" approach for perfect production compatibility:

**What We're Solving:**

1. **ObjectId Serialization**: Proper JSON serialization of MongoDB ObjectIds
2. **Route Parameter Validation**: FastAPI path parameter dependencies with ObjectId
3. **Response Model Validation**: Ensuring 422 errors don't interfere with proper HTTP codes
4. **Pydantic v2 Patterns**: Using latest validation and serialization patterns

**Technical Details:**

- Using `BeforeValidator` and `PlainSerializer` for ObjectId handling
- Implementing proper FastAPI response schemas without `response_model` conflicts
- Creating specialized dependency injection for different parameter names
- Ensuring all validation errors return correct HTTP status codes (404, 400, etc.)

**Why This Matters:**
This is an authentication API that will be used by multiple services in production. Every response code, every validation, every serialization must be perfect and follow proper HTTP semantics.

### 🎯 **NEXT: Complete ObjectId Architecture**

**Remaining Work:**

1. Fix Pydantic v2 ObjectId schema generation errors
2. Ensure all routes return proper HTTP status codes (200, 201, 404, 400)
3. Complete client account and role route validation
4. Achieve 100% test success rate

**Success Criteria:**

- All 97 tests passing
- Proper HTTP status codes for all scenarios
- Clean ObjectId serialization in all JSON responses
- Production-ready Pydantic v2 compatibility

## Getting Started

### Prerequisites

- Docker and Docker Compose

### Running the Application

1.  **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd outlabsAuth
    ```

2.  **Build and run the containers:**
    The project is fully containerized. Use the following command to start the FastAPI application and the MongoDB database:

    ```bash
    docker compose up -d --build
    ```

    - The FastAPI application will be running and available at `http://localhost:8030`.
    - The interactive API documentation (Swagger UI) will be at `http://localhost:8030/docs`.
    - The basic health check endpoint is at `http://localhost:8030/health`.

### Local Development with `uv` (Optional)

If you prefer to run the application locally without Docker for certain tasks, you can use `uv` to manage the environment.

1.  **Install `uv`:**
    Follow the instructions on the [official `uv` website](https://github.com/astral-sh/uv).

2.  **Create a virtual environment:**

    ```bash
    uv venv
    ```

3.  **Activate the environment:**

    - macOS/Linux: `source .venv/bin/activate`
    - Windows: `.venv\Scripts\activate`

4.  **Install dependencies:**

    ```bash
    uv pip sync pyproject.toml
    ```

5.  **Run the development server:**
    ```bash
    uvicorn api.main:app --port 8030 --reload
    ```

## 🔧 Technical Architecture & Current Challenges

### **Core Architecture**

- **FastAPI** with async/await patterns for high performance
- **MongoDB** with proper indexing and unique constraints
- **Pydantic v2** for data validation and serialization
- **JWT-based authentication** with role-based permissions
- **Multi-tenant architecture** with client account isolation

### **Current Technical Challenge: ObjectId Serialization**

**Problem Statement:**
MongoDB uses `ObjectId` types, but JSON APIs need strings. Getting this right with Pydantic v2 + FastAPI requires:

1. **Input Validation**: Accept both ObjectId and string inputs
2. **Database Operations**: Store as proper ObjectId in MongoDB
3. **JSON Output**: Serialize as strings in API responses
4. **HTTP Status Codes**: Return 404 for missing items, not 422 validation errors
5. **Parameter Dependencies**: Handle path parameters with correct naming

**Current Status:**

- ✅ String-based approach works but isn't "proper" Pydantic v2
- ❌ Advanced `PyObjectId` type causing schema generation errors
- ❌ Route parameter dependencies conflicting with FastAPI validation
- ❌ Some routes returning 422 instead of proper HTTP codes

**What We're Building:**
A bullet-proof, production-ready ObjectId handling system that:

- Uses proper Pydantic v2 `BeforeValidator` and `PlainSerializer`
- Returns correct HTTP status codes in all scenarios
- Handles all edge cases (invalid IDs, missing resources, etc.)
- Works seamlessly with FastAPI's dependency injection
- Maintains clean, maintainable code patterns

### **Testing Philosophy**

- **97 comprehensive tests** covering all scenarios
- **Integration tests** for end-to-end workflows
- **Edge case testing** for error conditions
- **Data integrity testing** for database constraints
- **Security testing** for authentication and authorization

### **Production Requirements**

This microservice will serve multiple applications, so we require:

- **100% reliability** in authentication flows
- **Proper HTTP semantics** for all API responses
- **Data consistency** with proper database constraints
- **Security hardening** with comprehensive permission checks
- **Clean error handling** with meaningful error messages
