from pathlib import Path

from pypdf import PdfReader


class DocumentExtractor:
    def extract(self, file_path: Path) -> str:
        file_type = file_path.suffix.lower()

        if file_type in {".md", ".txt"}:
            return self._extract_text(file_path)

        if file_type == ".pdf":
            return self._extract_pdf(file_path)

        raise ValueError(
            f"Unsupported document type: {file_path.suffix}"
        )

    @staticmethod
    def _extract_text(file_path: Path) -> str:
        return file_path.read_text(encoding="utf-8")

    @staticmethod
    def _extract_pdf(file_path: Path) -> str:
        reader = PdfReader(file_path)

        pages = []

        for page in reader.pages:
            text = page.extract_text()

            if text:
                pages.append(text)

        return "\n\n".join(pages)