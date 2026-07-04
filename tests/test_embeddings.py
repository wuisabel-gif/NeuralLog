from __future__ import annotations

import math

from neurallog.embeddings import HashingEmbedder


def test_hash_embedding_is_deterministic():
    emb = HashingEmbedder(dimensions=64)
    assert emb.embed("EKF drift after pool test") == emb.embed("EKF drift after pool test")


def test_hash_embedding_is_unit_normalized():
    vec = HashingEmbedder(dimensions=64).embed("some content here")
    assert math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0, rel_tol=1e-9)


def test_empty_text_is_zero_vector():
    emb = HashingEmbedder(dimensions=16)
    assert emb.embed("") == [0.0] * 16


def test_tokenization_is_case_insensitive():
    emb = HashingEmbedder(dimensions=64)
    assert emb.embed("EKF Drift") == emb.embed("ekf drift")


def test_self_similarity_is_one():
    vec = HashingEmbedder(dimensions=128).embed("localization tuning")
    assert math.isclose(HashingEmbedder.similarity(vec, vec), 1.0, rel_tol=1e-9)


def test_disjoint_texts_are_orthogonal():
    emb = HashingEmbedder(dimensions=512)
    a = emb.embed("apple banana")
    b = emb.embed("zebra xylophone")
    # no shared tokens -> dot product should be 0 (barring hash collisions in 512 dims)
    assert math.isclose(HashingEmbedder.similarity(a, b), 0.0, abs_tol=1e-9)


def test_cache_namespace_is_stable():
    ns = HashingEmbedder(dimensions=384).cache_namespace()
    assert ns == "hash|384"
