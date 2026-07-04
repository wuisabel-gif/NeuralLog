from __future__ import annotations

from neurallog.chunking import chunk_messages
from neurallog.embeddings import HashingEmbedder
from neurallog.index import VectorIndex
from tests.conftest import make_message


def build_index(*contents: str) -> VectorIndex:
    # one message per chunk (max_messages=1) so ranking maps to content cleanly
    msgs = [make_message(str(i), text, minutes=i) for i, text in enumerate(contents)]
    chunks = chunk_messages(msgs, max_messages=1)
    index = VectorIndex(embedder=HashingEmbedder(dimensions=256), backend="inmemory")
    index.add(chunks)
    return index


def test_empty_index_returns_no_results():
    index = VectorIndex(embedder=HashingEmbedder(), backend="inmemory")
    assert index.search("anything") == []


def test_lexical_match_ranks_first():
    index = build_index(
        "the mapping pipeline switched to slam toolbox",
        "unrelated notes about lunch and coffee",
    )
    results = index.search("mapping slam toolbox", limit=2)
    assert results[0].message_ids == ["0"]
    assert results[0].score > results[1].score


def test_min_score_filters_low_matches():
    index = build_index("mapping slam toolbox", "lunch and coffee")
    results = index.search("mapping slam toolbox", limit=5, min_score=0.5)
    assert all(r.score >= 0.5 for r in results)
    assert [r.message_ids[0] for r in results] == ["0"]


def test_limit_caps_result_count():
    index = build_index("a apple", "b banana", "c cherry", "d date")
    assert len(index.search("apple banana cherry date", limit=2)) == 2


def test_hybrid_coverage_beats_pure_semantic():
    # both mention 'ekf'; only the first also covers 'covariance tuning'
    index = build_index(
        "ekf covariance tuning improved localization",
        "ekf estimate is fine and stable now",
    )
    results = index.search("ekf covariance tuning", limit=2)
    assert results[0].message_ids == ["0"]
