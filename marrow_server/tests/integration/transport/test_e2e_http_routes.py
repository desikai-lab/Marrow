import httpx
import pytest
from transport.app_factory import app


@pytest.mark.asyncio
async def test_health_endpoint_get_returns_200_ok():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_oauth_endpoints_get_returns_valid_metadata():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # Userinfo
        response = await client.get("/userinfo")
        assert response.status_code == 200
        assert response.json() == {"sub": "mcp-user", "name": "MCP User"}

        # Discovery
        response = await client.get("/.well-known/mcp-server")
        assert response.status_code == 200
        assert "endpoints" in response.json()


@pytest.mark.asyncio
async def test_protected_endpoint_no_token_returns_401():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post("/mcp")
        assert response.status_code == 401
        assert response.json() == {"error": "invalid_token"}
