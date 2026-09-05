from treasury_rag.chunking import chunk_pages
from treasury_rag.models import PageText


def test_chunking_is_page_local_and_overlaps() -> None:
    page = PageText(pdf_page=7, text=" ".join(f"w{i}" for i in range(12)))
    chunks = chunk_pages([page], chunk_words=5, overlap_words=2)

    assert [chunk.text for chunk in chunks] == [
        "w0 w1 w2 w3 w4",
        "w3 w4 w5 w6 w7",
        "w6 w7 w8 w9 w10",
        "w9 w10 w11",
    ]
    assert all(chunk.pdf_page == 7 for chunk in chunks)
    assert chunks[0].chunk_id == "p0007-c000"


def test_invalid_overlap_is_rejected() -> None:
    try:
        chunk_pages([], chunk_words=5, overlap_words=5)
    except ValueError as exc:
        assert "smaller" in str(exc)
    else:
        raise AssertionError("Expected ValueError")

