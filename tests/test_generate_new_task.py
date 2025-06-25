import pytest
from unittest.mock import MagicMock, patch
from core.main import generate_new_task


def test_generate_new_task_success():
    groq_client = MagicMock()
    content = "# Test summary\nDescription"
    with patch("core.main.call_groq_generate_content", return_value=content):
        result = generate_new_task(groq_client, "history", "Test topic")
    assert result["summary"] == "Test summary"
    assert result["description"] == content


def test_generate_new_task_groq_exception():
    groq_client = MagicMock()
    with patch("core.main.call_groq_generate_content", side_effect=Exception("Groq error")):
        with pytest.raises(Exception) as excinfo:
            generate_new_task(groq_client, "history", "Test topic")
        assert "Groq error" in str(excinfo.value)
