import numpy as np

from treasury_rag.baseline import BaselineIndex
from treasury_rag.models import Chunk


def test_dense_search_orders_cosine_scores() -> None:
    chunks = [
        Chunk("a", 1, 0, "alpha", 0, 1),
        Chunk("b", 2, 0, "beta", 0, 1),
        Chunk("c", 3, 0, "gamma", 0, 1),
    ]
    vectors = np.asarray([[1.0, 0.0], [0.8, 0.2], [0.0, 1.0]], dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    index = BaselineIndex(chunks, vectors, {})

    results = index.search(np.asarray([1.0, 0.0]), top_k=2)

    assert [result.chunk.chunk_id for result in results] == ["a", "b"]
    assert results[0].score > results[1].score

