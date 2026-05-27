from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from neurallog.models import MessageRecord


def load_discord_export(export_path: str | Path) -> list[MessageRecord]:
    path = Path(export_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    channel_name = _first_non_empty(
        payload.get("channel", {}).get("name"),
        payload.get("channel", {}).get("topic"),
        payload.get("guild", {}).get("name"),
        path.stem,
    )
    channel_id = str(
        _first_non_empty(payload.get("channel", {}).get("id"), payload.get("channelId"), path.stem)
    )

    messages = []
    for raw in payload.get("messages", []):
        content = _extract_content(raw)
        if not content.strip():
            continue

        author = _first_non_empty(raw.get("author", {}).get("name"), "unknown")
        author_id = raw.get("author", {}).get("id")

        message = MessageRecord(
            id=str(raw.get("id")),
            channel_id=channel_id,
            channel_name=str(channel_name),
            author=str(author),
            author_id=str(author_id) if author_id is not None else None,
            timestamp=_parse_timestamp(raw.get("timestamp")),
            content=content,
            source_path=str(path.resolve()),
            attachments=_extract_attachments(raw),
            references=_extract_references(raw),
        )
        messages.append(message)

    messages.sort(key=lambda message: message.timestamp)
    return messages


def _extract_content(message: dict[str, Any]) -> str:
    sections: list[str] = []

    content = message.get("content")
    if isinstance(content, str) and content.strip():
        sections.append(content.strip())

    for embed in message.get("embeds", []):
        title = embed.get("title")
        description = embed.get("description")
        if title:
            sections.append(f"Embed title: {title}")
        if description:
            sections.append(f"Embed description: {description}")

    stickers = message.get("stickers") or []
    if stickers:
        sections.append(
            "Stickers: " + ", ".join(str(sticker.get("name", "unknown")) for sticker in stickers)
        )

    return "\n".join(section for section in sections if section).strip()


def _extract_attachments(message: dict[str, Any]) -> list[str]:
    attachments = []
    for attachment in message.get("attachments", []):
        name = attachment.get("fileName") or attachment.get("file_name") or attachment.get("url")
        if name:
            attachments.append(str(name))
    return attachments


def _extract_references(message: dict[str, Any]) -> list[str]:
    references = []
    reference = message.get("reference")
    if isinstance(reference, dict):
        reference_id = reference.get("messageId") or reference.get("message_id")
        if reference_id:
            references.append(str(reference_id))
    return references


def _parse_timestamp(raw_timestamp: Any) -> datetime:
    if isinstance(raw_timestamp, str):
        normalized = raw_timestamp.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    if isinstance(raw_timestamp, (int, float)):
        return datetime.fromtimestamp(raw_timestamp, tz=UTC)
    raise ValueError(f"Unsupported timestamp format: {raw_timestamp!r}")


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", []):
            return value
    return None
