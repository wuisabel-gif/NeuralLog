from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from pathlib import Path


class EmbeddingCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def get_many(self, namespace: str, texts: list[str]) -> list[list[float] | None]:
        if not texts:
            return []

        keys = [self._make_key(namespace, text) for text in texts]
        placeholders = ",".join("?" for _ in keys)
        query = f"SELECT cache_key, vector_json FROM embeddings WHERE cache_key IN ({placeholders})"

        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(query, keys).fetchall()

        cached_by_key = {row[0]: json.loads(row[1]) for row in rows}
        return [cached_by_key.get(key) for key in keys]

    def put_many(self, namespace: str, items: list[tuple[str, list[float]]]) -> None:
        if not items:
            return

        rows = [
            (self._make_key(namespace, text), namespace, json.dumps(vector))
            for text, vector in items
        ]

        with sqlite3.connect(self.path) as conn:
            conn.executemany(
                """
                INSERT INTO embeddings (cache_key, namespace, vector_json)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET vector_json = excluded.vector_json
                """,
                rows,
            )
            conn.commit()

    def _initialize(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    cache_key TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    vector_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_embeddings_namespace ON embeddings(namespace)"
            )
            conn.commit()

    @staticmethod
    def _make_key(namespace: str, text: str) -> str:
        digest = sha256(text.encode("utf-8")).hexdigest()
        return f"{namespace}:{digest}"
