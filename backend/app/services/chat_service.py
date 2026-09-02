from app.services.anthropic_service import AnthropicService
from app.services.search_service import SearchService


class ChatService:
    def __init__(
        self,
        search_service: SearchService,
        anthropic_service: AnthropicService,
    ) -> None:
        self.search_service = search_service
        self.anthropic_service = anthropic_service

    def chat(
        self,
        message: str,
        number_of_results: int = 5,
    ) -> dict:
        if not message.strip():
            raise ValueError("Message cannot be empty.")

        search_results = self.search_service.search(
            query=message,
            number_of_results=number_of_results,
        )

        context = self._build_context(search_results)

        prompt = self._build_prompt(
            message=message,
            context=context,
        )

        answer = self.anthropic_service.generate_response(
            prompt=prompt,
        )

        sources = self._build_sources(search_results)

        return {
            "answer": answer,
            "sources": sources,
        }

    @staticmethod
    def _build_context(
        search_results: list[dict],
    ) -> str:
        if not search_results:
            return "No relevant knowledge base information was found."

        context_parts = []

        for index, result in enumerate(search_results, start=1):
            context_parts.append(
                f"""
Source {index}
Category: {result["category"]}
Document: {result["filename"]}
Content:
{result["text"]}
""".strip()
            )

        return "\n\n".join(context_parts)

    @staticmethod
    def _build_prompt(
        message: str,
        context: str,
    ) -> str:
        return f"""
You are IT Copilot, a private AI assistant for IT troubleshooting.

Use the provided knowledge base context to help answer the user's question.

Knowledge Base Context:
------------------------
{context}
------------------------

User Question:
{message}

Instructions:
- Give a clear and practical IT troubleshooting answer.
- Prefer information from the knowledge base when it is relevant.
- Do not claim that the knowledge base says something it does not say.
- If the available knowledge is insufficient, clearly say so.
- Do not invent technical facts or sources.
- When recommending commands, explain what they do.
- Use concise steps when troubleshooting.
""".strip()

    @staticmethod
    def _build_sources(
        search_results: list[dict],
    ) -> list[dict[str, str]]:
        sources = []

        seen = set()

        for result in search_results:
            source_key = (
                result["category"],
                result["filename"],
            )

            if source_key in seen:
                continue

            seen.add(source_key)

            sources.append(
                {
                    "category": result["category"],
                    "filename": result["filename"],
                }
            )

        return sources