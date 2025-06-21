from fastapi import FastAPI

app = FastAPI(
    title="Outlabs RBAC Microservice",
    description="A standalone, generic Role-Based Access Control (RBAC) microservice.",
    version="0.1.0",
)

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Basic health check to confirm the service is running.
    """
    return {"status": "ok"} 