from treasury_rag.bm25 import BM25Index
from treasury_rag.models import Chunk


def test_bm25_prefers_exact_rare_identifier() -> None:
    chunks = [
        Chunk("a", 1, 0, "general fiscal policy and public spending", 0, 6),
        Chunk("b", 2, 0, "The E-731 control requires a restart.", 0, 6),
        Chunk("c", 3, 0, "general controls and restart guidance", 0, 5),
    ]
    index = BM25Index(chunks)

    results = index.search("What does E-731 require?", top_k=2)

    assert results[0].chunk.chunk_id == "b"
    assert results[0].score > results[1].score

