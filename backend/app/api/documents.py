from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.services.document_chunker import DocumentChunker
from app.services.document_extractor import DocumentExtractor
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService
from app.services.document_indexer import DocumentIndexer


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

settings = get_settings()

document_service = DocumentService(
    knowledge_base_directory=settings.knowledge_base_directory,
)

document_extractor = DocumentExtractor()
document_chunker = DocumentChunker()
embedding_service = EmbeddingService()
document_indexer = DocumentIndexer(
    document_extractor=document_extractor,
    document_chunker=document_chunker,
    embedding_service=embedding_service,
)


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
    file_path = document_service.get_file_path(category, filename)

    if file_path is None:
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


@router.get("/{category}/{filename}/chunks")
def get_document_chunks(
    category: str,
    filename: str,
) -> dict[str, str | int | list[str]]:
    file_path = document_service.get_file_path(category, filename)

    if file_path is None:
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

    chunks = document_chunker.chunk_text(content)

    return {
        "category": category,
        "filename": filename,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }

@router.get("/{category}/{filename}/embedding")
def get_document_embedding(
    category: str,
    filename: str,
) -> dict[str, str | int]:
    file_path = document_service.get_file_path(category, filename)

    if file_path is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    try:
        indexed_chunks = document_indexer.index_document(file_path)

    except ValueError as error:
        raise HTTPException(
            status_code=415,
            detail=str(error),
        )

    if not indexed_chunks:
        raise HTTPException(
            status_code=400,
            detail="Document contains no extractable text.",
        )

    return {
        "category": category,
        "filename": filename,
        "chunk_count": len(indexed_chunks),
        "status": "document_indexed",
    }