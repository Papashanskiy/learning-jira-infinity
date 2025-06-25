import pytest
from unittest.mock import MagicMock, patch
from core.main import call_groq_generate_content


def test_call_groq_generate_content_dry_run():
    groq_client = MagicMock()
    prompt = "test prompt"
    with patch("core.main.DRY_RUN", True):
        result = call_groq_generate_content(groq_client, prompt)
    assert result.startswith("# DRY-RUN")
    # groq_client should not be called
    assert not groq_client.chat.completions.create.called


def test_call_groq_generate_content_normal():
    groq_client = MagicMock()
    prompt = "test prompt"
    expected_content = "Generated content"
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = expected_content
    groq_client.chat.completions.create.return_value = mock_response

    with patch("core.main.DRY_RUN", False):
        result = call_groq_generate_content(groq_client, prompt)
    assert result == expected_content
    groq_client.chat.completions.create.assert_called_once()
