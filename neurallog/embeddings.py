from __future__ import annotations

import math
import os
import re
from abc import ABC, abstractmethod
from collections import Counter
from hashlib import sha256
from typing import Literal

from neurallog.cache import EmbeddingCache

EmbeddingBackendName = Literal["hash", "sentence-transformers", "openai"]
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_./:-]+")


class BaseEmbedder(ABC):
    name: str
    dimensions: int

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    @staticmethod
    def similarity(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right, strict=True))

    def metadata(self) -> dict[str, object]:
        return {"name": self.name, "dimensions": self.dimensions}

    def cache_namespace(self) -> str:
        metadata = self.metadata()
        parts = [str(metadata["name"]), str(metadata["dimensions"])]
        for key in sorted(k for k in metadata.keys() if k not in {"name", "dimensions"}):
            parts.append(f"{key}={metadata[key]}")
        return "|".join(parts)


class HashingEmbedder(BaseEmbedder):
    """Dependency-light semantic baseline using hashed token frequencies."""

    name = "hash"

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        counts = Counter(self._tokenize(text))
        vector = [0.0] * self.dimensions

        for token, count in counts.items():
            index = int(sha256(token.encode("utf-8")).hexdigest(), 16) % self.dimensions
            vector[index] += float(count)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector

        return [value / norm for value in vector]

    def _tokenize(self, text: str) -> list[str]:
        return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


class SentenceTransformersEmbedder(BaseEmbedder):
    name = "sentence-transformers"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", *, batch_size: int = 32) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Sentence-transformers backend was requested, but the `sentence-transformers` "
                "package is not installed."
            ) from exc

        self.model_name = model_name
        self.batch_size = batch_size
        self._model = SentenceTransformer(model_name)
        self.dimensions = int(self._model.get_sentence_embedding_dimension())

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vectors.tolist()

    def metadata(self) -> dict[str, object]:
        payload = super().metadata()
        payload["model"] = self.model_name
        return payload


class OpenAIEmbedder(BaseEmbedder):
    name = "openai"

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        *,
        dimensions: int | None = None,
        batch_size: int = 64,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "OpenAI embedding backend was requested, but the `openai` package is not installed."
            ) from exc

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OpenAI embedding backend was requested, but OPENAI_API_KEY is not set."
            )

        self.model = model
        self.requested_dimensions = dimensions
        self.batch_size = batch_size
        self._client = OpenAI(api_key=api_key)
        self.dimensions = dimensions or _default_openai_dimensions(model)

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_vectors: list[list[float]] = []
        for offset in range(0, len(texts), self.batch_size):
            batch = texts[offset : offset + self.batch_size]
            request: dict[str, object] = {
                "model": self.model,
                "input": batch,
                "encoding_format": "float",
            }
            if self.requested_dimensions is not None:
                request["dimensions"] = self.requested_dimensions

            response = self._client.embeddings.create(**request)
            vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
            all_vectors.extend([list(map(float, vector)) for vector in vectors])
        return all_vectors

    def metadata(self) -> dict[str, object]:
        payload = super().metadata()
        payload["model"] = self.model
        return payload


class CachedEmbedder(BaseEmbedder):
    def __init__(self, inner: BaseEmbedder, cache: EmbeddingCache) -> None:
        self.inner = inner
        self.cache = cache
        self.name = inner.name
        self.dimensions = inner.dimensions
        self.cache_hits = 0
        self.cache_misses = 0

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        namespace = self.inner.cache_namespace()
        cached = self.cache.get_many(namespace, texts)

        missing_texts: list[str] = []
        missing_positions: list[int] = []
        for index, vector in enumerate(cached):
            if vector is None:
                missing_positions.append(index)
                missing_texts.append(texts[index])

        self.cache_hits += len(texts) - len(missing_texts)
        self.cache_misses += len(missing_texts)

        computed_vectors = self.inner.embed_many(missing_texts) if missing_texts else []
        if missing_texts:
            self.cache.put_many(namespace, list(zip(missing_texts, computed_vectors, strict=True)))

        computed_iter = iter(computed_vectors)
        resolved: list[list[float]] = []
        for vector in cached:
            resolved.append(vector if vector is not None else next(computed_iter))
        return resolved

    def metadata(self) -> dict[str, object]:
        payload = self.inner.metadata()
        payload["cache"] = True
        return payload


def create_embedder(
    backend: EmbeddingBackendName = "hash",
    *,
    hash_dimensions: int = 384,
    sentence_transformers_model: str = "all-MiniLM-L6-v2",
    openai_model: str = "text-embedding-3-small",
    openai_dimensions: int | None = None,
    batch_size: int | None = None,
    cache_path: str | None = "neurallog-embeddings.sqlite3",
) -> BaseEmbedder:
    embedder: BaseEmbedder
    if backend == "hash":
        embedder = HashingEmbedder(dimensions=hash_dimensions)
    elif backend == "sentence-transformers":
        embedder = SentenceTransformersEmbedder(
            model_name=sentence_transformers_model,
            batch_size=batch_size or 32,
        )
    elif backend == "openai":
        embedder = OpenAIEmbedder(
            model=openai_model,
            dimensions=openai_dimensions,
            batch_size=batch_size or 64,
        )
    else:
        raise RuntimeError(f"Unsupported embedding backend: {backend}")

    if cache_path:
        return CachedEmbedder(embedder, EmbeddingCache(cache_path))
    return embedder


def _default_openai_dimensions(model: str) -> int:
    if model == "text-embedding-3-small":
        return 1536
    if model == "text-embedding-3-large":
        return 3072
    return 1536
