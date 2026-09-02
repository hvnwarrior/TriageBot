from datetime import datetime
from pathlib import Path


class DocumentService:
    def __init__(self, knowledge_base_directory: Path) -> None:
        self.knowledge_base_directory = knowledge_base_directory

    def list_directories(self) -> list[str]:
        if not self.knowledge_base_directory.exists():
            return []

        return sorted(
            item.name
            for item in self.knowledge_base_directory.iterdir()
            if item.is_dir() and not item.name.startswith(".")
        )

    def list_files(self, category: str) -> list[dict[str, str | int]]:
        category_directory = self.knowledge_base_directory / category

        if not category_directory.exists() or not category_directory.is_dir():
            return []

        files = []

        for item in category_directory.iterdir():
            if not item.is_file() or item.name.startswith("."):
                continue

            files.append(
                {
                    "name": item.name,
                    "type": self._get_file_type(item),
                    "size": item.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        item.stat().st_mtime
                    ).isoformat(),
                }
            )

        return sorted(files, key=lambda file: str(file["name"]))

    @staticmethod
    def _get_file_type(file: Path) -> str:
        extension = file.suffix.lower()

        file_types = {
            ".md": "markdown",
            ".txt": "text",
            ".pdf": "pdf",
            ".docx": "word",
            ".doc": "word",
            ".html": "html",
            ".htm": "html",
            ".csv": "csv",
            ".json": "json",
        }

        return file_types.get(extension, "unknown")