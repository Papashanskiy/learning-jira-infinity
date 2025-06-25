import pytest
from unittest.mock import patch, MagicMock
import core.main as main


@pytest.fixture
def fake_schedule():
    # today = 0 (понедельник)
    return {0: [("EPIC-1", "Тема 1"), ("EPIC-2", "Тема 2")]}


@patch("core.main.get_topic_history", return_value="history")
@patch("core.main.process_project")
@patch("core.main.init_clients")
def test_run_daily_calls_process_project(mock_init, mock_process, mock_get_history, monkeypatch, fake_schedule):
    jira = MagicMock()
    groq = MagicMock()
    mock_init.return_value = (jira, groq)
    # today = 0

    class FakeDate:
        @staticmethod
        def today():
            class D:
                @staticmethod
                def weekday(self=None):
                    return 0
            return D()
    monkeypatch.setattr(main, "PROJECT_SCHEDULE", fake_schedule)
    monkeypatch.setattr(main, "datetime", FakeDate)
    main.run_daily()
    assert mock_process.call_count == 2
    mock_process.assert_any_call(jira, groq, "EPIC-1", "Тема 1", "history")
    mock_process.assert_any_call(jira, groq, "EPIC-2", "Тема 2", "history")


@patch("core.main.get_topic_history")
@patch("core.main.process_project")
@patch("core.main.init_clients")
def test_run_daily_no_schedule_today(mock_init, mock_process, mock_get_history, monkeypatch):
    jira = MagicMock()
    groq = MagicMock()
    mock_init.return_value = (jira, groq)
    # today = 3, но PROJECT_SCHEDULE пустой для этого дня

    class FakeDate:
        @staticmethod
        def today():
            class D:
                @staticmethod
                def weekday(self=None):
                    return 3
            return D()
    monkeypatch.setattr(main, "PROJECT_SCHEDULE", {0: [("EPIC-1", "Тема 1")]})
    monkeypatch.setattr(main, "datetime", FakeDate)
    main.run_daily()
    mock_process.assert_not_called()


@patch("core.main.get_topic_history", return_value="history")
@patch("core.main.process_project")
@patch("core.main.init_clients")
def test_run_daily_process_project_exception(mock_init, mock_process, mock_get_history, monkeypatch, fake_schedule, caplog):
    jira = MagicMock()
    groq = MagicMock()
    mock_init.return_value = (jira, groq)
    mock_process.side_effect = Exception("fail")

    class FakeDate:
        @staticmethod
        def today():
            class D:
                @staticmethod
                def weekday(self=None):
                    return 0
            return D()
    monkeypatch.setattr(main, "PROJECT_SCHEDULE", fake_schedule)
    monkeypatch.setattr(main, "datetime", FakeDate)
    with caplog.at_level("ERROR"):
        # Should not raise
        try:
            main.run_daily()
        except Exception:
            pytest.fail("run_daily should not propagate exceptions")
