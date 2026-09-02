from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore


class SearchService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def search(
        self,
        query: str,
        number_of_results: int = 5,
    ) -> dict:
        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        query_embedding = self.embedding_service.create_embedding(query)

        return self.vector_store.search(
            embedding=query_embedding,
            number_of_results=number_of_results,
        )