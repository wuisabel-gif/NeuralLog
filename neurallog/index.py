from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from neurallog.embeddings import BaseEmbedder, HashingEmbedder
from neurallog.models import ChunkRecord, SearchResult

try:
    import faiss  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    faiss = None


IndexBackendName = Literal["auto", "inmemory", "faiss"]


@dataclass(slots=True)
class IndexedChunk:
    chunk: ChunkRecord
    vector: list[float]

    def to_dict(self) -> dict[str, object]:
        return {"chunk": self.chunk.to_dict(), "vector": self.vector}


class VectorIndex:
    def __init__(
        self,
        *,
        embedder: BaseEmbedder | None = None,
        backend: IndexBackendName = "auto",
    ) -> None:
        self.embedder = embedder or HashingEmbedder()
        self.requested_backend = backend
        self.backend_name = self._resolve_backend_name(backend)
        self._chunks: list[IndexedChunk] = []
        self._faiss_index = None
        self._rebuild_backend_index()

    def add(self, chunks: list[ChunkRecord]) -> None:
        vectors = self.embedder.embed_many([chunk.text for chunk in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._chunks.append(IndexedChunk(chunk=chunk, vector=vector))
        self._rebuild_backend_index()

    def search(self, query: str, limit: int = 5, min_score: float | None = None) -> list[SearchResult]:
        if not self._chunks:
            return []

        if self.backend_name == "faiss":
            return self._search_faiss(query, limit, min_score)
        return self._search_inmemory(query, limit, min_score)

    def save(self, path: str | Path) -> None:
        payload = {
            "backend": self.backend_name,
            "embedder": self.embedder.metadata(),
            "chunks": [indexed.to_dict() for indexed in self._chunks],
        }
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        saved_embedder = payload.get("embedder", {})
        saved_dimensions = saved_embedder.get("dimensions")
        if saved_dimensions and int(saved_dimensions) != self.embedder.dimensions:
            raise RuntimeError(
                "Saved index dimensions do not match the active embedder. "
                f"Index expects {saved_dimensions}, but active embedder produces "
                f"{self.embedder.dimensions}."
            )
        self._chunks = []
        for item in payload.get("chunks", []):
            chunk_data = item["chunk"]
            chunk = ChunkRecord(
                id=chunk_data["id"],
                message_ids=chunk_data["message_ids"],
                channel_id=chunk_data["channel_id"],
                channel_name=chunk_data["channel_name"],
                participants=chunk_data["participants"],
                start_time=_parse_datetime(chunk_data["start_time"]),
                end_time=_parse_datetime(chunk_data["end_time"]),
                text=chunk_data["text"],
                source_path=chunk_data["source_path"],
            )
            self._chunks.append(IndexedChunk(chunk=chunk, vector=item["vector"]))

        saved_backend = payload.get("backend", "inmemory")
        self.backend_name = self._resolve_backend_name(self.requested_backend, saved_backend)
        self._rebuild_backend_index()

    @property
    def size(self) -> int:
        return len(self._chunks)

    @property
    def chunks(self) -> list[ChunkRecord]:
        return [indexed.chunk for indexed in self._chunks]

    @property
    def faiss_available(self) -> bool:
        return faiss is not None

    def _resolve_backend_name(
        self,
        requested: IndexBackendName,
        saved_backend: str | None = None,
    ) -> Literal["inmemory", "faiss"]:
        if requested == "inmemory":
            return "inmemory"
        if requested == "faiss":
            if faiss is None:
                raise RuntimeError(
                    "FAISS backend was requested, but the `faiss` package is not installed."
                )
            return "faiss"
        if saved_backend == "faiss" and faiss is not None:
            return "faiss"
        if faiss is not None:
            return "faiss"
        return "inmemory"

    def _rebuild_backend_index(self) -> None:
        if self.backend_name != "faiss":
            self._faiss_index = None
            return

        if faiss is None:
            raise RuntimeError("FAISS backend is active, but the `faiss` package is unavailable.")

        dimensions = self.embedder.dimensions
        index = faiss.IndexFlatIP(dimensions)
        if self._chunks:
            vectors = np.array([indexed.vector for indexed in self._chunks], dtype=np.float32)
            index.add(vectors)
        self._faiss_index = index

    def _search_inmemory(self, query: str, limit: int, min_score: float | None) -> list[SearchResult]:
        query_vector = self.embedder.embed(query)
        query_terms = _tokenize(query)
        scored = [
            (indexed, _hybrid_score(query, query_terms, indexed, self.embedder.similarity(query_vector, indexed.vector)))
            for indexed in self._chunks
        ]
        if min_score is not None:
            scored = [(indexed, score) for indexed, score in scored if score >= min_score]
        ranked = sorted(scored, key=lambda item: item[1], reverse=True)
        return [self._to_result(indexed, score) for indexed, score in ranked[:limit]]

    def _search_faiss(self, query: str, limit: int, min_score: float | None) -> list[SearchResult]:
        if self._faiss_index is None:
            return []

        query_terms = _tokenize(query)
        query_vector = np.array([self.embedder.embed(query)], dtype=np.float32)
        search_limit = len(self._chunks) if min_score is not None else min(max(limit * 5, limit), len(self._chunks))
        scores, indices = self._faiss_index.search(query_vector, search_limit)

        rescored: list[tuple[IndexedChunk, float]] = []
        for score, index_position in zip(scores[0], indices[0], strict=False):
            if index_position < 0:
                continue
            indexed = self._chunks[int(index_position)]
            combined_score = _hybrid_score(query, query_terms, indexed, float(score))
            if min_score is not None and combined_score < min_score:
                continue
            rescored.append((indexed, combined_score))

        ranked = sorted(rescored, key=lambda item: item[1], reverse=True)
        return [self._to_result(indexed, score) for indexed, score in ranked[:limit]]

    def _to_result(self, indexed: IndexedChunk, score: float) -> SearchResult:
        preview = indexed.chunk.text.replace("\n", " ")[:240]
        return SearchResult(
            chunk_id=indexed.chunk.id,
            score=score,
            channel_name=indexed.chunk.channel_name,
            start_time=indexed.chunk.start_time,
            end_time=indexed.chunk.end_time,
            participants=indexed.chunk.participants,
            preview=preview,
            message_ids=indexed.chunk.message_ids,
        )


def _parse_datetime(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "did",
    "do",
    "for",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "the",
    "to",
    "was",
    "we",
    "what",
    "when",
    "why",
    "with",
}


def _tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_PATTERN.findall(text.lower()) if token not in STOP_WORDS]


def _hybrid_score(
    query: str,
    query_terms: list[str],
    indexed: IndexedChunk,
    semantic_score: float,
) -> float:
    chunk_text = indexed.chunk.text.lower()
    if not query_terms:
        return semantic_score

    matches = sum(1 for term in query_terms if term in chunk_text)
    coverage = matches / len(query_terms)
    phrase_bonus = 0.15 if query.lower() in chunk_text else 0.0
    title_bonus = 0.10 if any(term in indexed.chunk.channel_name.lower() for term in query_terms) else 0.0

    return semantic_score + (0.35 * coverage) + phrase_bonus + title_bonus
