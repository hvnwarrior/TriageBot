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
        category: str,
        filename: str,
    ) -> None:
        if not chunks:
            return

        ids = [
            f"{category}_{filename}_{chunk['chunk_index']}"
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
                "category": category,
                "filename": filename,
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

    def search(
        self,
        embedding: list[float],
        number_of_results: int = 5,
    ) -> dict:
        return self.collection.query(
            query_embeddings=[embedding],
            n_results=number_of_results,
        )

    def count(self) -> int:
        return self.collection.count()