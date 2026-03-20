import pytest
from unittest.mock import AsyncMock, patch
import json
import os
from app import analyze_input_async, init_gemini, validate_inputs, render_list

class MockImage:
    def __init__(self, format="JPEG"):
        self.format = format

@pytest.fixture
def mock_async_model():
    model = AsyncMock()
    return model

@pytest.mark.asyncio
async def test_analyze_input_async_success(mock_async_model):
    """Integration style mocked test verifying JSON parsing from an async API call."""
    mock_response = AsyncMock()
    mock_response.text = json.dumps({
        "mode": "EDUCATION",
        "identified_threat": "Poison Ivy",
        "toxicity_level": "Mild",
        "urgency": "Low",
        "call_911": False,
        "first_aid_steps": ["Wash skin with soap"],
        "educational_info": {
            "symptoms_to_watch": ["Itching"]
        }
    })
    mock_async_model.generate_content_async.return_value = mock_response

    result = await analyze_input_async(model=mock_async_model, image=MockImage(), text="Is this harmful?")
    
    assert result["mode"] == "EDUCATION"
    assert result["identified_threat"] == "Poison Ivy"
    assert result["call_911"] is False

def test_validate_inputs_empty():
    """Unit Test: Ensure scalability by blocking empty requests."""
    error = validate_inputs(None, "", None)
    assert error is not None
    assert "Input required" in error

def test_validate_inputs_unsupported_image():
    """Unit Test: Robust validation blocking unknown formats."""
    error = validate_inputs(MockImage(format="TIFF"), "Check this out", None)
    assert error is not None
    assert "Unsupported image format" in error

def test_validate_inputs_length_limit():
    """Unit Test: Performance protection against massive text payloads."""
    long_text = "a" * 2005
    error = validate_inputs(None, long_text, None)
    assert error is not None
    assert "too long" in error
