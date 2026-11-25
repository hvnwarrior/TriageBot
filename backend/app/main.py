from fastapi import FastAPI

from app.api.assistant import router as assistant_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.it_console import router as it_console_router
from app.config import get_settings
from app.dependencies import initialize_services


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    debug=settings.debug,
)


@app.on_event("startup")
def on_startup() -> None:
    # Build and cache all services on first boot.
    initialize_services(app)


app.include_router(health_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(assistant_router)
app.include_router(it_console_router)


@app.get("/", tags=["General"])
def root() -> dict[str, str]:
    return {
        "message": f"Welcome to {settings.app_name}!",
        "status": "running",
        "environment": settings.environment,
    }
