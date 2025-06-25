import pytest
from unittest.mock import MagicMock, patch
from core.main import epic_exists


def test_epic_exists_success():
    jira = MagicMock()
    jira.issue.return_value = MagicMock()
    assert epic_exists(jira, "EPIC-1") is True
    jira.issue.assert_called_once_with("EPIC-1")


def test_epic_exists_failure_logs_error(caplog):
    jira = MagicMock()
    jira.issue.side_effect = Exception("not found")
    with caplog.at_level("ERROR"):
        result = epic_exists(jira, "EPIC-404")
    assert result is False
    assert "Epic EPIC-404 not found or inaccessible" in caplog.text
