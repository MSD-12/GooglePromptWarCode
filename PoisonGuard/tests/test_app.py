import pytest
from unittest.mock import MagicMock, patch
import json
import os
from app import analyze_input, init_gemini

# Mock Image for testing
class MockImage:
    pass

@pytest.fixture
def mock_model():
    model = MagicMock()
    return model

def test_analyze_input_success(mock_model):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "mode": "EDUCATION",
        "identified_threat": "Poison Ivy",
        "toxicity_level": "Mild",
        "urgency": "Low",
        "call_911": False,
        "first_aid_steps": ["Wash skin with soap", "Apply calamine lotion"],
        "educational_info": {
            "common_names": "Poison Ivy",
            "preventative_measures": "Wear long sleeves",
            "toxicity_to_groups": "Mild rash to humans",
            "symptoms_to_watch": ["Itching", "Redness"]
        }
    })
    mock_model.generate_content.return_value = mock_response

    # Execute
    result = analyze_input(model=mock_model, image=MockImage(), text="Is this plant harmful?")
    
    # Assert
    assert result["mode"] == "EDUCATION"
    assert result["identified_threat"] == "Poison Ivy"
    assert result["call_911"] is False
    assert len(result["first_aid_steps"]) == 2
    mock_model.generate_content.assert_called_once()


def test_analyze_input_empty():
    """Test that empty inputs immediately return an error without API calls."""
    result = analyze_input(MagicMock(), image=None, text="")
    assert "error" in result
    assert "No input provided" in result["error"]

def test_analyze_input_json_error(mock_model):
    """Test that malformed JSON from the API is gracefully handled."""
    mock_response = MagicMock()
    mock_response.text = "This is not valid JSON!!!"
    mock_model.generate_content.return_value = mock_response

    result = analyze_input(model=mock_model, image=None, text="test")
    assert "error" in result
    assert "malformed data" in result["error"]

@patch.dict(os.environ, {"GEMINI_API_KEY": ""})
def test_init_gemini_no_api_key():
    """Test the init function gracefully returns None when API key is missing."""
    with patch("app.logger") as mock_logger:
        model = init_gemini()
        assert model is None
        mock_logger.error.assert_called_once_with("GEMINI_API_KEY environment variable is missing.")
