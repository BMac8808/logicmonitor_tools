import logging

import pytest
from fastapi.testclient import TestClient

from se_pov_builder.app import create_app
from se_pov_builder.config import Settings


def test_secure_defaults(monkeypatch):
    for key in ("SEPB_HOST", "SEPB_LLM_PROVIDER", "SEPB_ADAPTER_MODE", "SEPB_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    s = Settings.from_env()
    assert s.host == "127.0.0.1"
    assert s.llm_provider == "none"
    assert s.adapter_mode == "mock"
    assert all("127.0.0.1" in o or "localhost" in o for o in s.cors_origins)


def test_adapter_modes(monkeypatch):
    monkeypatch.setenv("SEPB_ADAPTER_MODE", "live")
    with pytest.raises(ValueError, match="mock, mcp"):
        Settings.from_env()
    monkeypatch.setenv("SEPB_ADAPTER_MODE", "mcp")
    assert Settings.from_env().mcp_url == "http://127.0.0.1:3000/mcp"
    monkeypatch.setenv("SEPB_MCP_URL", "file:///etc/passwd")
    with pytest.raises(ValueError, match="http"):
        Settings.from_env()


def test_api_token_enforced(settings):
    settings.api_token = "s3cret-token"
    with TestClient(create_app(settings)) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/deals").status_code == 401
        assert c.get("/api/deals", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert c.get("/api/deals", headers={"Authorization": "Bearer s3cret-token"}).status_code == 200


def test_request_bodies_not_logged(client, caplog):
    secret = "body-content-that-must-not-be-logged"
    with caplog.at_level(logging.INFO, logger="se_pov_builder"):
        client.post("/api/accounts", json={"name": secret})
    assert "POST /api/accounts 201" in caplog.text
    assert secret not in caplog.text


def test_spa_does_not_serve_files_outside_dist(settings, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>app</html>")
    (tmp_path / "secret.txt").write_text("nope")
    settings.frontend_dist = dist
    with TestClient(create_app(settings)) as c:
        assert c.get("/").text == "<html>app</html>"
        assert "nope" not in c.get("/../secret.txt").text
        assert "nope" not in c.get("/%2e%2e/secret.txt").text
        assert c.get("/api/unknown").status_code == 404
