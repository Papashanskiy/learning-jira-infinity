import pytest
from unittest.mock import MagicMock, patch
from jira import Issue
import core.main as main


@pytest.fixture
def jira_mock():
    return MagicMock()


@pytest.fixture
def issue_mock():
    return MagicMock(spec=Issue)


@pytest.fixture
def fields():
    return {"summary": "Test", "description": "Desc"}


@patch("core.main.retry", lambda *a, **kw: (lambda f: f))
def test_jira_create_issue(jira_mock, fields):
    expected_issue = MagicMock()
    jira_mock.create_issue.return_value = expected_issue
    result = main.jira_create_issue(jira_mock, fields)
    jira_mock.create_issue.assert_called_once_with(fields=fields)
    assert result == expected_issue


@patch("core.main.retry", lambda *a, **kw: (lambda f: f))
def test_jira_transition_issue(jira_mock, issue_mock):
    jira_mock.transition_issue.return_value = None
    result = main.jira_transition_issue(jira_mock, issue_mock, "123")
    jira_mock.transition_issue.assert_called_once_with(issue_mock, "123")
    assert result is None


@patch("core.main.retry", lambda *a, **kw: (lambda f: f))
def test_jira_add_comment(jira_mock):
    jira_mock.add_comment.return_value = "comment"
    result = main.jira_add_comment(jira_mock, "ISSUE-1", "msg")
    jira_mock.add_comment.assert_called_once_with("ISSUE-1", "msg")
    assert result == "comment"


@patch("core.main.retry", lambda *a, **kw: (lambda f: f))
def test_jira_issue(jira_mock, issue_mock):
    jira_mock.issue.return_value = issue_mock
    result = main.jira_issue(jira_mock, "ISSUE-1")
    jira_mock.issue.assert_called_once_with("ISSUE-1")
    assert result == issue_mock


def test_jira_search_issues_success():
    mock_jira = MagicMock()
    mock_jira.search_issues.return_value = ["ISSUE-1", "ISSUE-2"]
    result = main.jira_search_issues(mock_jira, "project = TEST")
    assert result == ["ISSUE-1", "ISSUE-2"]
    mock_jira.search_issues.assert_called_once_with(
        "project = TEST", maxResults=1000)


def test_jira_search_issues_with_max_results():
    mock_jira = MagicMock()
    mock_jira.search_issues.return_value = ["ISSUE-1"]
    result = main.jira_search_issues(mock_jira, "project = TEST", maxResults=5)
    assert result == ["ISSUE-1"]
    mock_jira.search_issues.assert_called_once_with(
        "project = TEST", maxResults=5)


def test_jira_search_issues_raises(monkeypatch):
    mock_jira = MagicMock()
    mock_jira.search_issues.side_effect = Exception("Jira error")
    with pytest.raises(Exception):
        main.jira_search_issues(mock_jira, "project = TEST")
