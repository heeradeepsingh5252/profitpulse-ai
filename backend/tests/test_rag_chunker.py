import pytest

from profitpulse.rag.chunker import build_page_chunks, chunk_text, extract_document_pages


def test_chunk_text_is_empty_for_whitespace():
    assert chunk_text("   \n ") == []


def test_chunk_text_preserves_content_with_overlap():
    text = "word " * 500
    chunks = chunk_text(text, chunk_size=300, overlap=40)
    assert len(chunks) > 1
    assert all(chunks)
    assert "word" in chunks[0]


def test_chunk_validation():
    with pytest.raises(ValueError):
        chunk_text("hello", chunk_size=10)
    with pytest.raises(ValueError):
        chunk_text("hello", chunk_size=100, overlap=100)


def test_extract_text_document():
    pages = extract_document_pages("policy.md", b"# Policy\nApprove purchases with evidence.")
    assert pages == [{"page_number": 1, "text": "# Policy\nApprove purchases with evidence."}]


def test_reject_unsupported_extension():
    with pytest.raises(ValueError, match="Supported document types"):
        extract_document_pages("program.exe", b"x")


def test_reject_non_utf8_text():
    with pytest.raises(ValueError, match="UTF-8"):
        extract_document_pages("policy.txt", b"\xff\xfe")


def test_page_chunk_metadata_is_preserved():
    chunks = build_page_chunks([
        {"page_number": 2, "text": "The policy applies to expense claims."}
    ])
    assert chunks[0]["page_number"] == 2
    assert chunks[0]["chunk_index"] == 0
