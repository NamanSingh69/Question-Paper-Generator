"""Offline API tests: Gemini calls are mocked, so no API key or network is needed."""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app  # noqa: E402


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "healthy"


@patch("app.analyze_content")
def test_upload_without_file_analyzes_subject_only(mock_analyze, client):
    """With no file, the app maps topics from the subject name alone."""
    mock_analyze.return_value = {"success": True, "topics": [{"topic": "Kinematics", "subtopics": [], "importance": "High"}]}
    response = client.post("/api/upload", data={"subject": "Physics"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["topics"][0]["topic"] == "Kinematics"
    assert mock_analyze.call_args.args[0] is None  # no file_uri was sent


@patch("app.analyze_content")
def test_upload_maps_quota_errors_to_429(mock_analyze, client):
    mock_analyze.return_value = {"success": False, "error": "429 Resource has been exhausted (quota)"}
    response = client.post("/api/upload", data={"subject": "Physics"})
    assert response.status_code == 429


@patch("app.generate_questions")
def test_generate_questions_with_defaults(mock_generate, client):
    """An empty body falls back to defaults: 10 Medium MCQs, all generated."""
    mock_generate.return_value = {
        "success": True,
        "questions": [{"text": f"Q{i}", "type": "MCQ", "topic": "T"} for i in range(10)],
    }
    response = client.post("/api/generate-questions", json={})
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert len(body["questions"]) == 10
    params = mock_generate.call_args.args[1]
    assert params["difficulty"] == "Medium" and params["num_questions"] == 10


def test_export_markdown_with_answers(client):
    questions = [{"text": "What is 2 + 2?", "type": "Short Answer", "topic": "Arithmetic",
                  "difficulty": "Easy", "answer": "4"}]
    response = client.post("/api/export", json={"questions": questions, "format": "md",
                                                "title": "Quiz", "include_answers": True})
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "What is 2 + 2?" in text and "4" in text
