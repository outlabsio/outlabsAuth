# outlabsAuth - Generic RBAC Microservice

This repository contains a standalone, generic Role-Based Access Control (RBAC) microservice built with FastAPI. It provides centralized user authentication, authorization, and multi-tenant user management.

## Tech Stack

- **Backend**: FastAPI
- **Database**: MongoDB
- **Package Management**: `uv`
- **Containerization**: Docker

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

    - The FastAPI application will be running and available at `http://localhost:8000`.
    - The interactive API documentation (Swagger UI) will be at `http://localhost:8000/docs`.
    - The basic health check endpoint is at `http://localhost:8000/health`.

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
    uvicorn api.main:app --reload
    ```
