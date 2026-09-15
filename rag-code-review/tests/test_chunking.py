from rag_review.chunking import chunk_document
from rag_review.models import SourceDocument


def test_chunk_ids_are_stable() -> None:
    doc = SourceDocument(
        text="uno dos tres cuatro cinco seis siete ocho nueve diez",
        source="a.pdf",
        page=1,
        version="1",
    )
    first = chunk_document(doc, size=20, overlap=5)
    second = chunk_document(doc, size=20, overlap=5)
    assert [c.id for c in first] == [c.id for c in second]


def test_empty_document_returns_no_chunks() -> None:
    doc = SourceDocument(text="   ", source="empty.txt")
    assert chunk_document(doc, size=100, overlap=10) == []
