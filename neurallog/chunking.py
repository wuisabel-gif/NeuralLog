from __future__ import annotations

from collections import OrderedDict
from datetime import timedelta
from hashlib import sha1

from neurallog.models import ChunkRecord, MessageRecord


def chunk_messages(
    messages: list[MessageRecord],
    *,
    max_messages: int = 8,
    max_characters: int = 2000,
    max_gap_minutes: int = 90,
) -> list[ChunkRecord]:
    if not messages:
        return []

    chunks: list[ChunkRecord] = []
    current: list[MessageRecord] = []
    current_chars = 0
    max_gap = timedelta(minutes=max_gap_minutes)

    for message in messages:
        if not current:
            current = [message]
            current_chars = len(message.content)
            continue

        previous = current[-1]
        should_split = (
            message.channel_id != previous.channel_id
            or message.timestamp - previous.timestamp > max_gap
            or len(current) >= max_messages
            or current_chars + len(message.content) > max_characters
        )

        if should_split:
            chunks.append(_build_chunk(current))
            current = [message]
            current_chars = len(message.content)
        else:
            current.append(message)
            current_chars += len(message.content)

    if current:
        chunks.append(_build_chunk(current))

    return chunks


def _build_chunk(messages: list[MessageRecord]) -> ChunkRecord:
    participants = list(OrderedDict.fromkeys(message.author for message in messages))
    text = "\n".join(f"[{message.author}] {message.content}" for message in messages)
    digest = sha1("|".join(message.id for message in messages).encode("utf-8")).hexdigest()[:12]

    return ChunkRecord(
        id=f"{messages[0].channel_id}-{digest}",
        message_ids=[message.id for message in messages],
        channel_id=messages[0].channel_id,
        channel_name=messages[0].channel_name,
        participants=participants,
        start_time=messages[0].timestamp,
        end_time=messages[-1].timestamp,
        text=text,
        source_path=messages[0].source_path,
    )
