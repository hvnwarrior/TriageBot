from pathlib import Path

from app.services.document_chunker import DocumentChunker
from app.services.document_extractor import DocumentExtractor
from app.services.embedding_service import EmbeddingService


class DocumentIndexer:
    def __init__(
        self,
        document_extractor: DocumentExtractor,
        document_chunker: DocumentChunker,
        embedding_service: EmbeddingService,
    ) -> None:
        self.document_extractor = document_extractor
        self.document_chunker = document_chunker
        self.embedding_service = embedding_service

    def index_document(
        self,
        file_path: Path,
    ) -> list[dict[str, str | int | list[float]]]:
        content = self.document_extractor.extract(file_path)

        chunks = self.document_chunker.chunk_text(content)

        indexed_chunks = []

        for index, chunk in enumerate(chunks):
            embedding = self.embedding_service.create_embedding(chunk)

            indexed_chunks.append(
                {
                    "chunk_index": index,
                    "text": chunk,
                    "embedding": embedding,
                }
            )

        return indexed_chunks