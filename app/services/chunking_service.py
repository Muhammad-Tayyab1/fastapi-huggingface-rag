import re
from dataclasses import dataclass

from app.services.extraction_service import ExtractedPage


@dataclass(frozen=True)
class TextChunk:
    content: str
    chunk_index: int
    page_number: int | None
    token_count: int


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_text(text: str, size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start + size // 2:
                end = boundary
        content = text[start:end].strip()
        if content:
            chunks.append(content)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def chunk_pages(pages: list[ExtractedPage], size: int, overlap: int) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for page in pages:
        normalized = normalize_text(page.text)
        for content in _split_text(normalized, size, overlap):
            chunks.append(
                TextChunk(
                    content=content,
                    chunk_index=len(chunks),
                    page_number=page.page_number,
                    token_count=len(content.split()),
                )
            )
    return chunks
