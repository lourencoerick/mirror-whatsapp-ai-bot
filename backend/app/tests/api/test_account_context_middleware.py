import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from app.middleware.account_context import AccountContextMiddleware, get_account_id

app = FastAPI()
app.add_middleware(AccountContextMiddleware)


@app.get("/protected")
def protected():
    account_id = get_account_id()
    return {"account_id": account_id}


client = TestClient(app)


@pytest.mark.integration
def test_account_id_header_present():
    response = client.get(
        "/protected", headers={"X-Account-ID": "123e4567-e89b-12d3-a456-426614174000"}
    )
    assert response.status_code == 200
    assert response.json() == {"account_id": "123e4567-e89b-12d3-a456-426614174000"}


@pytest.mark.integration
def test_missing_account_id_header():
    response = client.get("/protected")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing X-Account-ID header"


@pytest.mark.integration
def test_invalid_account_id_header():
    response = client.get("/protected", headers={"X-Account-ID": "abc"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid X-Account-ID format"
