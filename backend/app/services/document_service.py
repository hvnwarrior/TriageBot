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

    def list_files(self, category: str) -> list[str]:
        category_directory = self.knowledge_base_directory / category

        if not category_directory.exists() or not category_directory.is_dir():
            return []

        return sorted(
            item.name
            for item in category_directory.iterdir()
            if item.is_file() and not item.name.startswith(".")
        )