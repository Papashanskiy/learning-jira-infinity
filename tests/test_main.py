import pytest
from unittest.mock import MagicMock, patch
from core.main import (
    epic_exists,
    generate_new_task,
    transition_issue_to_status,
    notify,
    get_topic_history,
)
import logging


class DummyIssue:
    def __init__(self, key="ISSUE-1", summary="Test summary", status_name="Backlog"):
        self.key = key
        self.summary = summary
        self.fields = type("Fields", (), {"status": type(
            "Status", (), {"name": status_name})})()


def test_epic_exists_true():
    jira = MagicMock()
    jira.issue.return_value = DummyIssue()
    assert epic_exists(jira, "PRO-1") is True


def test_epic_exists_false():
    jira = MagicMock()
    jira.issue.side_effect = Exception("Not found")
    assert epic_exists(jira, "PRO-404") is False


def test_generate_new_task(monkeypatch):
    monkeypatch.setattr("core.main.DRY_RUN", False)
    groq_client = MagicMock()
    groq_client.chat.completions.create.return_value = type(
        "Resp", (), {"choices": [type("Choice", (), {"message": type(
            "Msg", (), {"content": "# Test\nDescription"})()})]}
    )()
    result = generate_new_task(
        groq_client, "Old", "Test")
    assert "summary" in result and "description" in result
    assert result["summary"] == "Test"


def test_transition_issue_to_status_success(monkeypatch):
    monkeypatch.setattr("core.main.DRY_RUN", False)
    jira = MagicMock()
    issue = DummyIssue()
    jira.transitions.return_value = [{"id": "1", "name": "In Progress"}]
    with patch("core.main.jira_transition_issue") as mock_trans:
        transition_issue_to_status(jira, issue, "In Progress")
        mock_trans.assert_called_once_with(jira, issue, "1")


def test_transition_issue_to_status_no_transition(monkeypatch, caplog):
    monkeypatch.setattr("core.main.DRY_RUN", False)
    logger = logging.getLogger()
    logger.setLevel(logging.ERROR)
    jira = MagicMock()
    issue = DummyIssue()
    jira.transitions.return_value = [{"id": "1", "name": "Done"}]
    with caplog.at_level("ERROR"):
        transition_issue_to_status(jira, issue, "In Progress")
        assert "No transition found" in caplog.text


def test_notify_success(monkeypatch):
    monkeypatch.setattr("core.main.DRY_RUN", False)
    with patch("core.main.requests.post"):
        notify("ISSUE-1", "msg")


def test_get_topic_history_success():
    jira = MagicMock()
    jira.issue.return_value.fields.comment.comments = []
    comment = MagicMock()
    comment.body = (
        "Топик: Test\nКлюч топика: PRO-1\n\nИстория топика:\nTheme1\nTheme2"
    )
    with patch("core.main.seek_topic_history_comment", return_value=comment):
        result = get_topic_history(jira, "PRO-1", "Test")
        assert isinstance(result, str)
        assert "Theme1" in result and "Theme2" in result
