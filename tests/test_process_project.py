import pytest
from unittest.mock import MagicMock, patch, ANY
from core import main


@pytest.fixture
def mock_jira():
    return MagicMock()


@pytest.fixture
def mock_groq():
    return MagicMock()


@pytest.fixture
def epic_key():
    return "PRO-1"


@pytest.fixture
def topic():
    return "Тестовая тема"


@pytest.fixture
def history():
    return "История"


@patch("core.main.notify")
@patch("core.main.notify_critical_error")
@patch("core.main.epic_exists", return_value=False)
def test_process_project_epic_not_exists(mock_epic_exists, mock_notify_critical, mock_notify, mock_jira, mock_groq, epic_key, topic, history, monkeypatch):
    monkeypatch.setattr("core.main.DRY_RUN", False)
    main.process_project(mock_jira, mock_groq, epic_key, topic, history)
    mock_notify_critical.assert_called_once()
    mock_notify.assert_not_called()


@patch("core.main.notify")
@patch("core.main.epic_exists", return_value=True)
@patch("core.main.jira_search_issues")
def test_process_project_in_progress_exists(mock_search, mock_epic_exists, mock_notify, mock_jira, mock_groq, epic_key, topic, history, monkeypatch):
    monkeypatch.setattr("core.main.DRY_RUN", False)
    issue = MagicMock()
    issue.key = "PRO-123"
    # in_progress_issues, backlog_issues
    mock_search.side_effect = [[issue], []]
    main.process_project(mock_jira, mock_groq, epic_key, topic, history)
    mock_notify.assert_called_once_with(
        mock_jira,
        issue.key,
        ANY
    )


@patch("core.main.notify")
@patch("core.main.update_topic_history")
@patch("core.main.transition_issue_to_status")
@patch("core.main.epic_exists", return_value=True)
@patch("core.main.jira_search_issues")
def test_process_project_backlog_exists(
    mock_search, mock_epic_exists, mock_transition, mock_update_history, mock_notify, mock_jira, mock_groq, epic_key, topic, history, monkeypatch
):
    monkeypatch.setattr("core.main.DRY_RUN", False)
    backlog_issue = MagicMock()
    backlog_issue.fields.summary = "Backlog summary"
    backlog_issue.key = "PRO-456"
    # in_progress_issues, backlog_issues
    mock_search.side_effect = [[], [backlog_issue]]
    main.process_project(mock_jira, mock_groq, epic_key, topic, history)
    mock_transition.assert_called_once_with(
        mock_jira, backlog_issue, main.STATUS_IN_PROGRESS)
    mock_update_history.assert_called_once_with(
        mock_jira, epic_key, "Backlog summary")
    mock_notify.assert_called_once_with(
        mock_jira,
        backlog_issue.key,
        ANY
    )


@patch("core.main.notify")
@patch("core.main.update_topic_history")
@patch("core.main.jira_issue")
@patch("core.main.transition_issue_to_status")
@patch("core.main.jira_create_issue")
@patch("core.main.generate_new_task")
@patch("core.main.epic_exists", return_value=True)
@patch("core.main.jira_search_issues")
def test_process_project_creates_new_issue(
    mock_search, mock_epic_exists, mock_generate, mock_create, mock_transition, mock_jira_issue, mock_update_history, mock_notify,
    mock_jira, mock_groq, epic_key, topic, history, monkeypatch
):
    monkeypatch.setattr("core.main.DRY_RUN", False)
    # No in progress, no backlog
    mock_search.side_effect = [[], []]
    mock_generate.return_value = {
        "summary": "New summary", "description": "desc"}
    new_issue = MagicMock()
    new_issue.fields.summary = "New summary"
    new_issue.key = "PRO-789"
    mock_create.return_value = new_issue
    updated_issue = MagicMock()
    updated_issue.fields.status.name = main.STATUS_IN_PROGRESS
    mock_jira_issue.return_value = updated_issue

    main.process_project(mock_jira, mock_groq, epic_key, topic, history)

    mock_create.assert_called_once()
    mock_update_history.assert_called_once_with(
        mock_jira, epic_key, "New summary")
    mock_transition.assert_called_once_with(
        mock_jira, new_issue, main.STATUS_IN_PROGRESS)
    mock_notify.assert_called_once_with(mock_jira, new_issue.key, ANY)


@patch("core.main.notify_critical_error")
@patch("core.main.notify")
@patch("core.main.update_topic_history")
@patch("core.main.jira_issue")
@patch("core.main.transition_issue_to_status")
@patch("core.main.jira_create_issue")
@patch("core.main.generate_new_task")
@patch("core.main.epic_exists", return_value=True)
@patch("core.main.jira_search_issues")
def test_process_project_create_issue_fail(
    mock_search, mock_epic_exists, mock_generate, mock_create, mock_transition, mock_jira_issue, mock_update_history, mock_notify, mock_notify_critical,
    mock_jira, mock_groq, epic_key, topic, history, monkeypatch
):
    monkeypatch.setattr("core.main.DRY_RUN", False)
    # No in progress, no backlog
    mock_search.side_effect = [[], []]
    mock_generate.return_value = {
        "summary": "New summary", "description": "desc"}
    mock_create.return_value = None  # Simulate failure

    main.process_project(mock_jira, mock_groq, epic_key, topic, history)

    mock_notify_critical.assert_called_once()
    mock_notify.assert_not_called()
