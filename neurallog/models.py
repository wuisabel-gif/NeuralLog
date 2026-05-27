from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class MessageRecord:
    id: str
    channel_id: str
    channel_name: str
    author: str
    author_id: str | None
    timestamp: datetime
    content: str
    source_path: str
    attachments: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(slots=True)
class ChunkRecord:
    id: str
    message_ids: list[str]
    channel_id: str
    channel_name: str
    participants: list[str]
    start_time: datetime
    end_time: datetime
    text: str
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["start_time"] = self.start_time.isoformat()
        payload["end_time"] = self.end_time.isoformat()
        return payload


@dataclass(slots=True)
class SearchResult:
    chunk_id: str
    score: float
    channel_name: str
    start_time: datetime
    end_time: datetime
    participants: list[str]
    preview: str
    message_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["start_time"] = self.start_time.isoformat()
        payload["end_time"] = self.end_time.isoformat()
        return payload


@dataclass(slots=True)
class TimelineEvent:
    timestamp: datetime
    title: str
    summary: str
    channel_name: str
    participants: list[str]
    message_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload
