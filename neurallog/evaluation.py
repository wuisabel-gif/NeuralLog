from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from neurallog.services import NeuralLogService


@dataclass(slots=True)
class QueryEvaluation:
    query: str
    retrieved_message_ids: list[str]
    relevant_message_ids: list[str]
    precision_at_k: float
    recall_at_k: float
    reciprocal_rank: float

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "retrieved_message_ids": self.retrieved_message_ids,
            "relevant_message_ids": self.relevant_message_ids,
            "precision_at_k": self.precision_at_k,
            "recall_at_k": self.recall_at_k,
            "reciprocal_rank": self.reciprocal_rank,
        }


def evaluate_export(
    service: NeuralLogService,
    export_path: str | Path,
    evaluation_set_path: str | Path,
    *,
    limit: int = 5,
) -> dict[str, object]:
    service.ingest_discord_export(export_path)
    evaluation_set = json.loads(Path(evaluation_set_path).read_text(encoding="utf-8"))

    per_query: list[QueryEvaluation] = []
    for item in evaluation_set["queries"]:
        query = item["query"]
        relevant_message_ids = [str(value) for value in item["relevant_message_ids"]]
        results = service.search(query, limit=limit)
        retrieved_message_ids = _flatten_message_ids(results)

        precision = _precision_at_k(retrieved_message_ids, relevant_message_ids, limit)
        recall = _recall_at_k(retrieved_message_ids, relevant_message_ids, limit)
        reciprocal_rank = _reciprocal_rank(retrieved_message_ids, relevant_message_ids)

        per_query.append(
            QueryEvaluation(
                query=query,
                retrieved_message_ids=retrieved_message_ids,
                relevant_message_ids=relevant_message_ids,
                precision_at_k=precision,
                recall_at_k=recall,
                reciprocal_rank=reciprocal_rank,
            )
        )

    summary = {
        "queries_evaluated": len(per_query),
        "mean_precision_at_k": _mean(item.precision_at_k for item in per_query),
        "mean_recall_at_k": _mean(item.recall_at_k for item in per_query),
        "mean_reciprocal_rank": _mean(item.reciprocal_rank for item in per_query),
    }

    return {
        "summary": summary,
        "per_query": [item.to_dict() for item in per_query],
    }


def compare_embedding_backends(
    service_factory,
    export_path: str | Path,
    evaluation_set_path: str | Path,
    specs: list[dict[str, object]],
    *,
    limit: int = 5,
    skip_unavailable: bool = False,
) -> dict[str, object]:
    comparisons: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    for spec in specs:
        try:
            service = service_factory(spec)
            report = evaluate_export(
                service,
                export_path,
                evaluation_set_path,
                limit=limit,
            )
            comparisons.append(
                {
                    "label": spec["label"],
                    "embedding_backend": spec["embedding_backend"],
                    "embedding_model": spec.get("embedding_model"),
                    "summary": report["summary"],
                }
            )
        except RuntimeError as exc:
            failure = {
                "label": str(spec["label"]),
                "error": str(exc),
            }
            if skip_unavailable:
                failures.append(failure)
                continue
            raise RuntimeError(f"{failure['label']}: {failure['error']}") from exc

    comparisons.sort(
        key=lambda item: (
            -float(item["summary"]["mean_reciprocal_rank"]),
            -float(item["summary"]["mean_precision_at_k"]),
        )
    )

    return {
        "comparisons": comparisons,
        "failures": failures,
    }


def _flatten_message_ids(results) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for result in results:
        for message_id in result.message_ids:
            if message_id not in seen:
                seen.add(message_id)
                ids.append(message_id)
    return ids


def _precision_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for item in top_k if item in set(relevant))
    return hits / len(top_k)


def _recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for item in top_k if item in set(relevant))
    return hits / len(relevant)


def _reciprocal_rank(retrieved: list[str], relevant: list[str]) -> float:
    relevant_set = set(relevant)
    for index, item in enumerate(retrieved, start=1):
        if item in relevant_set:
            return 1.0 / index
    return 0.0


def _mean(values) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)
