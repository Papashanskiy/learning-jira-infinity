import pytest
from types import SimpleNamespace
from core.main import seek_topic_history_comment


def make_comment(body):
    # Эмулирует объект jira.Comment с полем body
    return SimpleNamespace(body=body)


def test_found_comment_with_epic_key():
    comments = [
        make_comment("Топик: test\nКлюч топика: EPIC-1\nИстория топика:"),
        make_comment("Топик: another\nКлюч топика: EPIC-2\nИстория топика:"),
    ]
    result = seek_topic_history_comment(comments, "EPIC-1")
    assert result is comments[0]


def test_found_comment_with_epic_key_in_middle():
    comments = [
        make_comment("Some text\nКлюч топика: EPIC-3\nИстория топика:"),
        make_comment("Топик: test\nКлюч топика: EPIC-4\nИстория топика:"),
    ]
    result = seek_topic_history_comment(comments, "EPIC-4")
    assert result is comments[1]


def test_not_found_comment():
    comments = [
        make_comment("Топик: test\nКлюч топика: EPIC-1\nИстория топика:"),
        make_comment("Топик: another\nКлюч топика: EPIC-2\nИстория топика:"),
    ]
    result = seek_topic_history_comment(comments, "EPIC-999")
    assert result is None


def test_comment_without_key_line():
    comments = [
        make_comment("Топик: test\nИстория топика:"),
        make_comment("Just some text"),
    ]
    result = seek_topic_history_comment(comments, "EPIC-1")
    assert result is None


def test_comment_with_key_line_but_no_epic():
    comments = [
        make_comment("Топик: test\nКлюч топика: EPIC-1\nИстория топика:"),
    ]
    result = seek_topic_history_comment(comments, "EPIC-2")
    assert result is None
