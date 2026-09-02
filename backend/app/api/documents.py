from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.services.document_extractor import DocumentExtractor
from app.services.document_service import DocumentService


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

settings = get_settings()

document_service = DocumentService(
    knowledge_base_directory=settings.knowledge_base_directory,
)

document_extractor = DocumentExtractor()


@router.get("")
def list_documents() -> dict[str, list[str]]:
    return {
        "directories": document_service.list_directories(),
    }


@router.get("/{category}")
def list_category_documents(
    category: str,
) -> dict[str, list[dict[str, str | int]] | str]:
    return {
        "category": category,
        "files": document_service.list_files(category),
    }


@router.get("/{category}/{filename}/content")
def get_document_content(
    category: str,
    filename: str,
) -> dict[str, str]:
    category_directory = settings.knowledge_base_directory / category
    file_path = category_directory / filename

    try:
        category_directory = category_directory.resolve()
        file_path = file_path.resolve()

        file_path.relative_to(category_directory)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid document path.",
        )

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    try:
        content = document_extractor.extract(file_path)
    except ValueError as error:
        raise HTTPException(
            status_code=415,
            detail=str(error),
        )

    return {
        "category": category,
        "filename": filename,
        "content": content,
    }