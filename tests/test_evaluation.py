from __future__ import annotations

import math

from neurallog.evaluation import (
    _flatten_message_ids,
    _precision_at_k,
    _recall_at_k,
    _reciprocal_rank,
    evaluate_export,
)
from neurallog.services import NeuralLogService


class _FakeResult:
    def __init__(self, message_ids):
        self.message_ids = message_ids


def test_precision_at_k():
    assert _precision_at_k(["a", "b", "c"], ["a", "c"], 2) == 0.5  # a hit, b miss


def test_recall_at_k():
    assert _recall_at_k(["a", "x", "y"], ["a", "b"], 5) == 0.5  # 1 of 2 relevant found


def test_recall_zero_when_no_relevant():
    assert _recall_at_k(["a"], [], 5) == 0.0


def test_reciprocal_rank_uses_first_hit():
    assert _reciprocal_rank(["x", "y", "a"], ["a"]) == 1.0 / 3


def test_reciprocal_rank_zero_when_no_hit():
    assert _reciprocal_rank(["x", "y"], ["a"]) == 0.0


def test_flatten_dedups_preserving_order():
    results = [_FakeResult(["1", "2"]), _FakeResult(["2", "3"])]
    assert _flatten_message_ids(results) == ["1", "2", "3"]


def test_evaluate_export_end_to_end(sample_export, sample_eval):
    service = NeuralLogService(embedding_cache_path=None, backend="inmemory")
    report = evaluate_export(service, sample_export, sample_eval, limit=5)
    summary = report["summary"]
    assert summary["queries_evaluated"] == 3
    assert len(report["per_query"]) == 3
    for key in ("mean_precision_at_k", "mean_recall_at_k", "mean_reciprocal_rank"):
        assert 0.0 <= summary[key] <= 1.0
    # sanity: hash backend should recover at least some relevant messages
    assert summary["mean_recall_at_k"] > 0.0
