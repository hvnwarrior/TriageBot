from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.services.anthropic_service import AnthropicService
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.embedding_service import EmbeddingService
from app.services.search_service import SearchService
from app.services.vector_store import VectorStore


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

conversation_service = ConversationService(
    database_path=settings.data_directory / "it_copilot.db",
)

chat_service = ChatService(
    search_service=search_service,
    anthropic_service=anthropic_service,
    conversation_service=conversation_service,
)


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None
    number_of_results: int = 5


@router.post("")
def chat(
    request: ChatRequest,
) -> dict:
    try:
        response = chat_service.chat(
            message=request.message,
            conversation_id=request.conversation_id,
            number_of_results=request.number_of_results,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    return response