import pytest
from unittest.mock import MagicMock, patch
from core.main import update_topic_history


@pytest.fixture
def mock_jira():
    return MagicMock()


@pytest.fixture
def mock_comment():
    comment = MagicMock()
    comment.body = "Топик: test\nКлюч топика: EPIC-1\nИстория топика:"
    return comment


def test_update_topic_history_updates_comment(mock_jira, mock_comment):
    mock_jira.issue.return_value.fields.comment.comments = [mock_comment]
    with patch("core.main.seek_topic_history_comment", return_value=mock_comment), \
            patch("core.main.DRY_RUN", False):
        update_topic_history(mock_jira, "EPIC-1", "New theme")
        mock_comment.update.assert_called_once()
        assert "New theme" in mock_comment.update.call_args[1]["body"]


def test_update_topic_history_dry_run(mock_jira, mock_comment):
    mock_jira.issue.return_value.fields.comment.comments = [mock_comment]
    with patch("core.main.seek_topic_history_comment", return_value=mock_comment), \
            patch("core.main.DRY_RUN", True):
        update_topic_history(mock_jira, "EPIC-1", "New theme")
        mock_comment.update.assert_not_called()


def test_update_topic_history_no_comment_found(mock_jira):
    mock_jira.issue.return_value.fields.comment.comments = []
    with patch("core.main.seek_topic_history_comment", return_value=None), \
            patch("core.main.DRY_RUN", False):
        # Should not raise
        update_topic_history(mock_jira, "EPIC-1", "New theme")
