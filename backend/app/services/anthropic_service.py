from anthropic import Anthropic

from app.config import get_settings


class AnthropicService:
    def __init__(self) -> None:
        settings = get_settings()

        self.client = Anthropic(
            api_key=settings.anthropic_api_key,
        )

        self.model = settings.chat_model

    def generate_response(
        self,
        prompt: str,
        max_tokens: int = 1024,
    ) -> str:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        for block in response.content:
            if block.type == "text":
                return block.text

        raise ValueError("Claude returned no text response.")