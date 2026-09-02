from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.anthropic_service import AnthropicService


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)

anthropic_service = AnthropicService()


class ChatTestRequest(BaseModel):
    prompt: str


@router.post("/test")
def test_chat(
    request: ChatTestRequest,
) -> dict[str, str]:
    try:
        response = anthropic_service.generate_response(
            request.prompt
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    return {
        "response": response,
    }