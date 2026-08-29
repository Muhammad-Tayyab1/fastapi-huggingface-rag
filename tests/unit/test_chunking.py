from app.services.chunking_service import chunk_pages, normalize_text
from app.services.extraction_service import ExtractedPage


def test_normalize_text() -> None:
    assert normalize_text(" Hello\x00   world\r\n\r\n\r\nNext ") == "Hello world\n\nNext"


def test_chunking_is_deterministic_and_preserves_page() -> None:
    pages = [ExtractedPage(text="one two three four five six seven", page_number=3)]
    first = chunk_pages(pages, size=18, overlap=4)
    second = chunk_pages(pages, size=18, overlap=4)
    assert first == second
    assert len(first) > 1
    assert [chunk.chunk_index for chunk in first] == list(range(len(first)))
    assert all(chunk.page_number == 3 for chunk in first)
