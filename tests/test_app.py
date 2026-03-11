import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_missing_file_uri(client):
    """Test /api/upload with missing file_uri"""
    response = client.post('/api/upload', data={
        'subject': 'Physics'
    })
    assert response.status_code == 400
    assert b"error" in response.data

def test_empty_generate_questions(client):
    """Test /api/generate-questions with missing fields"""
    response = client.post('/api/generate-questions', json={})
    assert response.status_code == 200
    data = json.loads(response.data)
    # The new logic will bypass pydantic and attempt generation with defaults
    assert "success" in data

