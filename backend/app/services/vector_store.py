from pathlib import Path

import chromadb


class VectorStore:
    def __init__(
        self,
        storage_directory: Path,
        collection_name: str = "it_copilot",
    ) -> None:
        self.client = chromadb.PersistentClient(
            path=str(storage_directory)
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name
        )

    def add_chunks(
        self,
        chunks: list[dict[str, str | int | list[float]]],
    ) -> None:
        if not chunks:
            return

        ids = [
            str(chunk["chunk_index"])
            for chunk in chunks
        ]

        documents = [
            str(chunk["text"])
            for chunk in chunks
        ]

        embeddings = [
            chunk["embedding"]
            for chunk in chunks
        ]

        metadatas = [
            {
                "chunk_index": int(chunk["chunk_index"]),
            }
            for chunk in chunks
        ]

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def count(self) -> int:
        return self.collection.count()