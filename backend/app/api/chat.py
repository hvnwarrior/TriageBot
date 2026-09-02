from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.anthropic_service import AnthropicService
from app.services.chat_service import ChatService
from app.services.embedding_service import EmbeddingService
from app.services.search_service import SearchService
from app.services.vector_store import VectorStore
from app.config import get_settings


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


settings = get_settings()

embedding_service = EmbeddingService()

vector_store = VectorStore(
    storage_directory=settings.vector_store_directory,
)

search_service = SearchService(
    embedding_service=embedding_service,
    vector_store=vector_store,
)

anthropic_service = AnthropicService()

chat_service = ChatService(
    search_service=search_service,
    anthropic_service=anthropic_service,
)


class ChatRequest(BaseModel):
    message: str
    number_of_results: int = 5


@router.post("")
def test_chat(
    request: ChatRequest,
) -> dict:
    try:
        response = chat_service.chat(
            message=request.message,
            number_of_results=request.number_of_results,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    return response