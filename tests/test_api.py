from asgi_lifespan import LifespanManager
import httpx
import pytest
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Yield an HTTP client with FastAPI lifespan context executed."""
    async with LifespanManager(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac


@pytest.mark.anyio
async def test_health_endpoint(client: httpx.AsyncClient):
    """Verify healthcheck response."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "TheraOverlap"}


@pytest.mark.anyio
async def test_empty_drug_payload(client: httpx.AsyncClient):
    """Verify validation error on empty payload."""
    response = await client.post("/api/v1/check", json={"drugs": []})
    assert response.status_code in (400, 422)


@pytest.mark.anyio
async def test_scenario_safe(client: httpx.AsyncClient):
    """Test scenario 'Safe': distinct ATC classes."""
    payload = {"drugs": ["Synthroid", "Metformin", "Paracetamol"]}
    response = await client.post("/api/v1/check", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["report"]["status"] == "Safe"
    assert data["report"]["total_alerts"] == 0
    assert len(data["resolved_drugs"]) == 3
    assert "disclaimer" in data["report"]


@pytest.mark.anyio
async def test_scenario_danger(client: httpx.AsyncClient):
    """Test scenario 'Danger': therapeutic overlap with NSAIDs."""
    payload = {"drugs": ["Advil", "Ketoprofen", "Metformin"]}
    response = await client.post("/api/v1/check", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["report"]["status"] == "Danger"
    assert data["report"]["total_alerts"] > 0
    assert any("M01AE" in item["description"] for item in data["report"]["interactions"])