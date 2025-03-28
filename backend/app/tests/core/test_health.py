from uuid import uuid4
import httpx
import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_check():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/health", headers={"X-Account-ID": str(uuid4())}
        )
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
