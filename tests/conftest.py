from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from neurallog.models import MessageRecord

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
SAMPLE_EXPORT = EXAMPLES / "sample-discord-export.json"
SAMPLE_EVAL = EXAMPLES / "sample-evaluation.json"

BASE_TIME = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)


def make_message(
    msg_id: str,
    content: str,
    *,
    channel_id: str = "chan",
    channel_name: str = "systems",
    author: str = "Maya",
    minutes: int = 0,
) -> MessageRecord:
    return MessageRecord(
        id=msg_id,
        channel_id=channel_id,
        channel_name=channel_name,
        author=author,
        author_id=None,
        timestamp=BASE_TIME + timedelta(minutes=minutes),
        content=content,
        source_path="test.json",
    )


@pytest.fixture
def sample_export() -> Path:
    return SAMPLE_EXPORT


@pytest.fixture
def sample_eval() -> Path:
    return SAMPLE_EVAL
