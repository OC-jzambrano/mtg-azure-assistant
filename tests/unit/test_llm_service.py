import pytest
from unittest.mock import MagicMock
from pydantic import BaseModel, Field
from src.services.llm import LLMService


class SampleOutput(BaseModel):
    summary: str = Field(description="Sample summary")
    score: int = Field(description="Sample score")


def test_llm_service_unavailable_without_credentials():
    service = LLMService(api_key="", endpoint="")
    assert not service.is_available()

    # Graceful degradation returns None without throwing exceptions
    structured = service.generate_structured(
        messages=[{"role": "user", "content": "hello"}],
        response_model=SampleOutput
    )
    assert structured is None

    text = service.generate_text(
        messages=[{"role": "user", "content": "hello"}]
    )
    assert text is None


def test_llm_service_structured_success_mock():
    mock_client = MagicMock()
    mock_parsed_obj = SampleOutput(summary="Analysis complete", score=10)
    
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed_obj
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    
    mock_client.beta.chat.completions.parse.return_value = mock_completion

    service = LLMService(api_key="mock-key", client=mock_client)
    assert service.is_available()

    result = service.generate_structured(
        messages=[{"role": "user", "content": "test"}],
        response_model=SampleOutput
    )
    assert result is not None
    assert result.summary == "Analysis complete"
    assert result.score == 10


def test_llm_service_structured_exception_activates_fallback():
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse.side_effect = TimeoutError("Azure OpenAI timed out")

    service = LLMService(api_key="mock-key", client=mock_client)
    # Should catch exception and return None for graceful degradation
    result = service.generate_structured(
        messages=[{"role": "user", "content": "test"}],
        response_model=SampleOutput
    )
    assert result is None
