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

        self.conversation_history: list[dict[str, str]] = []

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

        self.conversation_history.append(
            {
                "role": "user",
                "content": message,
            }
        )

        prompt = self._build_prompt(
            message=message,
            context=context,
        )

        answer = self.anthropic_service.generate_response(
            prompt=prompt,
        )

        self.conversation_history.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        sources = self._build_sources(search_results)

        return {
            "answer": answer,
            "sources": sources,
        }

    def _build_prompt(
        self,
        message: str,
        context: str,
    ) -> str:
        history = self._build_history()

        return f"""
You are IT Copilot, a private AI assistant for IT troubleshooting.

Use the provided knowledge base context to help answer the user's question.

Knowledge Base Context:
------------------------
{context}
------------------------

Previous Conversation:
------------------------
{history}
------------------------

Current User Question:
{message}

Instructions:
- Give a clear and practical IT troubleshooting answer.
- Use the knowledge base when it is relevant.
- Use previous conversation messages to understand context.
- Do not claim that the knowledge base says something it does not say.
- If the knowledge base does not contain enough information, clearly say so.
- Do not invent technical facts or sources.
- When recommending commands, explain what they do.
- If the user provides an error message, use it to narrow down the troubleshooting steps.
- Avoid repeating information the user has already received unless it is necessary.
- Ask a focused follow-up question when additional information is needed.
""".strip()

    def _build_history(self) -> str:
        if len(self.conversation_history) <= 1:
            return "No previous conversation."

        previous_messages = self.conversation_history[:-1]

        history_parts = []

        for message in previous_messages:
            role = message["role"].capitalize()

            history_parts.append(
                f"{role}: {message['content']}"
            )

        return "\n\n".join(history_parts)

    @staticmethod
    def _build_context(
        search_results: list[dict],
    ) -> str:
        if not search_results:
            return "No relevant knowledge base information was found."

        context_parts = []

        for index, result in enumerate(
            search_results,
            start=1,
        ):
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