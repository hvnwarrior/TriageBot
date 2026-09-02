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
    ) -> list[dict[str, str | int | float]]:
        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        query_embedding = self.embedding_service.create_embedding(query)

        results = self.vector_store.search(
            embedding=query_embedding,
            number_of_results=number_of_results,
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        search_results = []

        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        ):
            search_results.append(
                {
                    "text": document,
                    "category": metadata["category"],
                    "filename": metadata["filename"],
                    "chunk_index": metadata["chunk_index"],
                    "distance": distance,
                }
            )

        return search_results