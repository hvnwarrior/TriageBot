from sentence_transformers import SentenceTransformer


class EmbeddingService:
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        self.model = SentenceTransformer(model_name)

    def create_embedding(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Cannot create an embedding from empty text.")

        embedding = self.model.encode(text)

        return embedding.tolist()