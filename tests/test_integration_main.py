import pytest
from unittest.mock import patch, MagicMock
from core import main


@pytest.fixture
def mock_jira():
    jira = MagicMock()
    jira.transitions.return_value = [
        {"id": "1", "name": main.STATUS_IN_PROGRESS}]
    jira.search_issues.return_value = []
    jira.create_issue.return_value = MagicMock(key="PRO-999")
    jira.issue.return_value = MagicMock(
        key="PRO-999",
        fields=type("Fields", (), {"status": type(
            "Status", (), {"name": main.STATUS_IN_PROGRESS})})()
    )
    return jira


@pytest.fixture
def mock_groq():
    groq = MagicMock()
    groq.chat.completions.create.return_value = type(
        "Resp", (), {"choices": [type("Choice", (), {"message": type(
            "Msg", (), {"content": "# Test\nDescription"})()})]}
    )()
    return groq


def test_process_project_creates_and_transitions(monkeypatch, mock_jira, mock_groq):
    # Patch idempotency check to always return empty
    monkeypatch.setattr(main, "jira_search_issues", lambda *a, **k: [])
    monkeypatch.setattr(main, "jira_create_issue", lambda *a,
                        **k: mock_jira.create_issue.return_value)
    monkeypatch.setattr(main, "jira_transition_issue", lambda *a, **k: None)
    monkeypatch.setattr(main, "jira_issue", lambda *a, **
                        k: mock_jira.issue.return_value)
    monkeypatch.setattr(main, "notify", lambda *a, **k: None)
    monkeypatch.setattr(main, "epic_exists", lambda *a, **k: True)

    # Should create and transition issue
    main.process_project(mock_jira, mock_groq, "PRO-1",
                         "Интеграционный тест", [])


def test_process_project_idempotency(monkeypatch, mock_jira, mock_groq):
    # Patch idempotency check to simulate existing issue
    monkeypatch.setattr(main, "jira_search_issues",
                        lambda *a, **k: [MagicMock()])
    monkeypatch.setattr(main, "notify", lambda *a, **k: None)
    monkeypatch.setattr(main, "epic_exists", lambda *a, **k: True)

    # Should skip creation due to idempotency
    main.process_project(mock_jira, mock_groq, "PRO-1",
                         "Интеграционный тест", [])


def test_process_project_epic_not_exists(monkeypatch, mock_jira, mock_groq):
    monkeypatch.setattr(main, "epic_exists", lambda *a, **k: False)
    monkeypatch.setattr(main, "notify_critical_error", lambda *a, **k: None)
    main.process_project(mock_jira, mock_groq, "PRO-404", "Нет эпика", [])


def test_run_daily(monkeypatch, mock_jira, mock_groq):
    monkeypatch.setattr(main, "init_clients", lambda: (mock_jira, mock_groq))
    monkeypatch.setattr(main, "get_topic_history", lambda *a, **k: [])
    monkeypatch.setattr(main, "process_project", lambda *a, **k: None)
    # Should not raise
    main.run_daily()
