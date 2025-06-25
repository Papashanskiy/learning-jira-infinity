import pytest
from core.main import parse_history_comment


@pytest.mark.parametrize(
    "input_text,expected",
    [
        (
            "Топик: Английский\nКлюч топика: PRO-1\n\nИстория топика:\nPresent Simple\nPast Simple",
            "Present Simple\nPast Simple"
        ),
        (
            "История топика:\nТема 1\nТема 2\nТема 3",
            "Тема 1\nТема 2\nТема 3"
        ),
        (
            "Что-то другое\nИстория топика:\nОдна тема",
            "Одна тема"
        ),
        (
            "История топика:",
            ""
        ),
        (
            "Нет нужной секции\nТема 1\nТема 2",
            ""
        ),
        (
            "История топика:\n\n\nТема 1\n\nТема 2",
            "Тема 1\nТема 2"
        ),
        (
            "История топика: \n   \n   Тема 1\n   Тема 2",
            "Тема 1\nТема 2"
        ),
    ]
)
def test_parse_history_comment(input_text, expected):
    assert parse_history_comment(input_text) == expected
