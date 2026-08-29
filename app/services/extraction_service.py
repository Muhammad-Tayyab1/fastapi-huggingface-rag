from dataclasses import dataclass
from pathlib import Path

import anyio
from docx import Document as DocxDocument
from pypdf import PdfReader


@dataclass(frozen=True)
class ExtractedPage:
    text: str
    page_number: int | None


def _extract_pdf(path: Path) -> list[ExtractedPage]:
    reader = PdfReader(path)
    pages: list[ExtractedPage] = []
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(ExtractedPage(text=text, page_number=number))
    return pages


def _extract_docx(path: Path) -> list[ExtractedPage]:
    document = DocxDocument(path)
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return [ExtractedPage(text="\n\n".join(paragraphs), page_number=None)] if paragraphs else []


def _extract_text(path: Path) -> list[ExtractedPage]:
    text = path.read_text(encoding="utf-8")
    return [ExtractedPage(text=text, page_number=None)] if text.strip() else []


async def extract(path: Path, content_type: str) -> list[ExtractedPage]:
    if content_type == "application/pdf":
        return await anyio.to_thread.run_sync(_extract_pdf, path)
    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return await anyio.to_thread.run_sync(_extract_docx, path)
    if content_type == "text/plain":
        return await anyio.to_thread.run_sync(_extract_text, path)
    raise ValueError(f"Unsupported content type: {content_type}")
