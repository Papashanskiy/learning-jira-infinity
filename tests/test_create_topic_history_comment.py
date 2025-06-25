import pytest
from unittest.mock import MagicMock, patch
import core.main as main


@pytest.mark.parametrize("dry_run", [True, False])
def test_create_topic_history_comment(dry_run):
    jira = MagicMock()
    epic_key = "EPIC-1"
    topic = "Some topic"
    comment_body = f"Топик: {topic}\nКлюч топика: {epic_key}\n\nИстория топика:"

    with patch("core.main.DRY_RUN", dry_run), \
            patch("core.main.JIRA_HISTORY_KEY", "HIST-1"), \
            patch("core.main.logging") as mock_logging:
        main.create_topic_history_comment(jira, epic_key, topic)

        if dry_run:
            jira.add_comment.assert_not_called()
            assert mock_logging.info.call_count == 1
            assert "[DRY-RUN]" in mock_logging.info.call_args[0][0]
            assert epic_key in mock_logging.info.call_args[0][0]
        else:
            jira.add_comment.assert_called_once_with("HIST-1", comment_body)
