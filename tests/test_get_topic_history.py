import pytest
from unittest.mock import MagicMock, patch
from core.main import get_topic_history


@pytest.fixture
def mock_jira():
    return MagicMock()


@pytest.fixture
def mock_comment():
    comment = MagicMock()
    comment.body = (
        "Топик: Test\nКлюч топика: PRO-1\n\nИстория топика:\nTheme1\nTheme2"
    )
    return comment


def test_get_topic_history_found(monkeypatch, mock_jira, mock_comment):
    # Комментарий найден, история возвращается корректно
    mock_jira.issue.return_value.fields.comment.comments = [mock_comment]
    with patch("core.main.seek_topic_history_comment", return_value=mock_comment):
        result = get_topic_history(mock_jira, "PRO-1", "Test")
        assert "Theme1" in result and "Theme2" in result


def test_get_topic_history_not_found(monkeypatch, mock_jira):
    # Комментарий не найден, вызывается create_topic_history_comment
    mock_jira.issue.return_value.fields.comment.comments = []
    with patch("core.main.seek_topic_history_comment", return_value=None), \
            patch("core.main.create_topic_history_comment") as create_mock:
        result = get_topic_history(mock_jira, "PRO-1", "Test")
        create_mock.assert_called_once_with(mock_jira, "PRO-1", "Test")
        assert result == ""


def test_get_topic_history_exception(monkeypatch, mock_jira):
    # Исключение при получении issue
    mock_jira.issue.side_effect = Exception("fail")
    result = get_topic_history(mock_jira, "PRO-1", "Test")
    assert result == ""
