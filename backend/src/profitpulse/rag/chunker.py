"""Text extraction and deterministic character-window chunking for knowledge documents."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv"}
MAX_PDF_PAGES = 250


def extract_document_pages(filename: str, content: bytes) -> list[dict[str, object]]:
    """Return page-aware text. Scanned PDFs without text are rejected; OCR is not implicit."""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Supported document types are PDF, TXT, Markdown and CSV")
    if not content:
        raise ValueError("The uploaded document is empty")

    if extension == ".pdf":
        try:
            reader = PdfReader(BytesIO(content), strict=False)
        except Exception as exc:  # pypdf raises several parser-specific exceptions
            raise ValueError("The PDF could not be parsed") from exc
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f"PDF exceeds the {MAX_PDF_PAGES}-page limit")
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append({"page_number": index, "text": text})
        if not pages:
            raise ValueError("No selectable text found in PDF. Scanned PDFs need OCR before ingestion")
        return pages

    try:
        text = content.decode("utf-8-sig").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("Text documents must use UTF-8 encoding") from exc
    if not text:
        raise ValueError("The uploaded document contains no readable text")
    return [{"page_number": 1, "text": text}]


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 180) -> list[str]:
    """Split text into overlapping windows, preferring whitespace boundaries."""
    if chunk_size < 100:
        raise ValueError("chunk_size must be at least 100 characters")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    normalized = " ".join((text or "").split())
    if not normalized:
        return []
    chunks = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            boundary = normalized.rfind(" ", start + chunk_size // 2, end)
            if boundary > start:
                end = boundary
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_page_chunks(pages: Iterable[dict[str, object]], chunk_size: int = 1200, overlap: int = 180) -> list[dict[str, object]]:
    output = []
    for page in pages:
        page_number = int(page["page_number"])
        chunks = chunk_text(str(page["text"]), chunk_size=chunk_size, overlap=overlap)
        for chunk_index, text in enumerate(chunks):
            output.append({"page_number": page_number, "chunk_index": chunk_index, "text": text})
    return output
