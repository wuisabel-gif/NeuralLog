from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from neurallog.chunking import chunk_messages
from neurallog.discord_ingest import load_discord_export
from neurallog.embeddings import EmbeddingBackendName, create_embedder
from neurallog.index import IndexBackendName, VectorIndex
from neurallog.models import SearchResult, TimelineEvent


class NeuralLogService:
    def __init__(
        self,
        index_path: str | Path | None = None,
        *,
        backend: IndexBackendName = "auto",
        embedding_backend: EmbeddingBackendName = "hash",
        sentence_transformers_model: str = "all-MiniLM-L6-v2",
        openai_model: str = "text-embedding-3-small",
        openai_dimensions: int | None = None,
        embedding_batch_size: int | None = None,
        embedding_cache_path: str | None = "neurallog-embeddings.sqlite3",
    ) -> None:
        self.embedder = create_embedder(
            embedding_backend,
            sentence_transformers_model=sentence_transformers_model,
            openai_model=openai_model,
            openai_dimensions=openai_dimensions,
            batch_size=embedding_batch_size,
            cache_path=embedding_cache_path,
        )
        self.index = VectorIndex(backend=backend, embedder=self.embedder)
        self.index_path = Path(index_path) if index_path else None

        if self.index_path and self.index_path.exists():
            self.index.load(self.index_path)

    def ingest_discord_export(self, export_path: str | Path) -> dict[str, int | str]:
        messages = load_discord_export(export_path)
        chunks = chunk_messages(messages)
        self.index.add(chunks)

        if self.index_path:
            self.index.save(self.index_path)

        return {
            "messages_indexed": len(messages),
            "chunks_created": len(chunks),
            "index_size": self.index.size,
            "backend": self.index.backend_name,
            "embedding_backend": self.embedder.name,
        }

    def search(self, query: str, limit: int = 5, min_score: float | None = None) -> list[SearchResult]:
        return self.index.search(query, limit=limit, min_score=min_score)

    def build_timeline(self, query: str, limit: int = 8, min_score: float | None = None) -> list[TimelineEvent]:
        retrieved = self.search(query, limit=limit, min_score=min_score)
        grouped: dict[str, list[SearchResult]] = defaultdict(list)

        for result in retrieved:
            date_key = result.start_time.date().isoformat()
            grouped[date_key].append(result)

        events = []
        for _, group in sorted(grouped.items(), key=lambda item: item[0]):
            group.sort(key=lambda result: result.start_time)
            lead = group[0]
            participants = list(dict.fromkeys(name for result in group for name in result.participants))
            title = f"{lead.channel_name}: {query}"
            summary = " ".join(result.preview for result in group)[:500]
            message_ids = [message_id for result in group for message_id in result.message_ids]

            events.append(
                TimelineEvent(
                    timestamp=lead.start_time,
                    title=title,
                    summary=summary,
                    channel_name=lead.channel_name,
                    participants=participants,
                    message_ids=message_ids,
                )
            )

        return events
