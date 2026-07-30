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