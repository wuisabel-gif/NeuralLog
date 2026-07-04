from __future__ import annotations

from neurallog.chunking import chunk_messages
from tests.conftest import make_message


def test_empty_input_returns_empty():
    assert chunk_messages([]) == []


def test_messages_in_one_window_stay_together():
    msgs = [make_message(str(i), "short", minutes=i) for i in range(3)]
    chunks = chunk_messages(msgs)
    assert len(chunks) == 1
    assert chunks[0].message_ids == ["0", "1", "2"]


def test_split_on_channel_change():
    msgs = [
        make_message("1", "a", channel_id="A", channel_name="a"),
        make_message("2", "b", channel_id="B", channel_name="b", minutes=1),
    ]
    chunks = chunk_messages(msgs)
    assert [c.channel_id for c in chunks] == ["A", "B"]


def test_split_on_time_gap():
    msgs = [
        make_message("1", "a", minutes=0),
        make_message("2", "b", minutes=200),  # > default 90 min gap
    ]
    assert len(chunk_messages(msgs, max_gap_minutes=90)) == 2


def test_split_on_max_messages():
    msgs = [make_message(str(i), "x", minutes=i) for i in range(5)]
    chunks = chunk_messages(msgs, max_messages=2)
    assert [len(c.message_ids) for c in chunks] == [2, 2, 1]


def test_split_on_max_characters():
    msgs = [make_message(str(i), "y" * 60, minutes=i) for i in range(3)]
    chunks = chunk_messages(msgs, max_characters=100)
    # each message is 60 chars, so no two fit in a 100-char window
    assert [len(c.message_ids) for c in chunks] == [1, 1, 1]


def test_chunk_id_is_deterministic():
    msgs = [make_message("1", "a"), make_message("2", "b", minutes=1)]
    first = chunk_messages(msgs)[0]
    second = chunk_messages(msgs)[0]
    assert first.id == second.id


def test_participants_deduped_in_order():
    msgs = [
        make_message("1", "a", author="Maya"),
        make_message("2", "b", author="Alex", minutes=1),
        make_message("3", "c", author="Maya", minutes=2),
    ]
    chunk = chunk_messages(msgs)[0]
    assert chunk.participants == ["Maya", "Alex"]
