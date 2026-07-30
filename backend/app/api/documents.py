from fastapi import APIRouter

from app.config import get_settings
from app.services.document_service import DocumentService


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

settings = get_settings()

document_service = DocumentService(
    knowledge_base_directory=settings.knowledge_base_directory,
)


@router.get("")
def list_documents() -> dict[str, list[str]]:
    return {
        "directories": document_service.list_directories(),
    }