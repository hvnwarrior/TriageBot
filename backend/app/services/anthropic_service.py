from anthropic import Anthropic

from app.config import get_settings


class AnthropicService:
    def __init__(self) -> None:
        settings = get_settings()

        # Prefer an explicit key from settings; otherwise fall back to
        # the local sign-in stored by the `ant` CLI (OAuth credentials
        # in ~/.config/anthropic). Keeps the app at zero stored API
        # keys when signed in, and works unchanged with a key too.
        self.client = (
            Anthropic(api_key=settings.anthropic_api_key)
            if settings.anthropic_api_key
            else Anthropic()
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