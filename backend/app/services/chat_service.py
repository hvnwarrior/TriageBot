from app.services.anthropic_service import AnthropicService
from app.services.conversation_service import ConversationService
from app.services.search_service import SearchService


class ChatService:
    def __init__(
        self,
        search_service: SearchService,
        anthropic_service: AnthropicService,
        conversation_service: ConversationService,
    ) -> None:
        self.search_service = search_service
        self.anthropic_service = anthropic_service
        self.conversation_service = conversation_service

    def chat(
        self,
        message: str,
        conversation_id: int | None = None,
        number_of_results: int = 5,
    ) -> dict:
        if not message.strip():
            raise ValueError("Message cannot be empty.")

        if conversation_id is None:
            conversation_id = self.conversation_service.create_conversation(
                title=self._create_title(message),
            )

        elif not self.conversation_service.conversation_exists(
            conversation_id
        ):
            raise ValueError("Conversation not found.")

        previous_messages = self.conversation_service.get_messages(
            conversation_id
        )

        search_results = self.search_service.search(
            query=message,
            number_of_results=number_of_results,
        )

        context = self._build_context(search_results)

        self.conversation_service.add_message(
            conversation_id=conversation_id,
            role="user",
            content=message,
        )

        prompt = self._build_prompt(
            message=message,
            context=context,
            history=previous_messages,
        )

        answer = self.anthropic_service.generate_response(
            prompt=prompt,
        )

        self.conversation_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
        )

        sources = self._build_sources(search_results)

        return {
            "conversation_id": conversation_id,
            "answer": answer,
            "sources": sources,
        }

    def _build_prompt(
        self,
        message: str,
        context: str,
        history: list[dict[str, str]],
    ) -> str:
        conversation_history = self._build_history(history)

        return f"""
You are IT Copilot, a private AI assistant for IT troubleshooting.

Use the provided knowledge base context to help answer the user's question.

Knowledge Base Context:
------------------------
{context}
------------------------

Previous Conversation:
------------------------
{conversation_history}
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

    @staticmethod
    def _build_history(
        history: list[dict[str, str]],
    ) -> str:
        if not history:
            return "No previous conversation."

        history_parts = []

        for message in history:
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

    @staticmethod
    def _create_title(
        message: str,
    ) -> str:
        title = " ".join(message.split())

        if len(title) <= 50:
            return title

        return f"{title[:47]}..."