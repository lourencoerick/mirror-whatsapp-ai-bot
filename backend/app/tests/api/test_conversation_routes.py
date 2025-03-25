import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.mark.integration
def test_get_conversations_success():
    response = client.get(
        "/inboxes/1/conversations?limit=5&offset=0",
        headers={"X-Account-ID": "1"},
    )
    print(response.json())
    assert response.status_code == 200
    assert isinstance(response.json(), list)
