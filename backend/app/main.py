from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(
    title="IT Copilot",
    version="0.1.0",
    description="Private AI-powered IT assistant.",
)

app.include_router(health_router)


@app.get("/", tags=["General"])
def root() -> dict[str, str]:
    return {
        "message": "Welcome to IT Copilot!",
        "status": "running",
    }