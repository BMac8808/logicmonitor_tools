import json

import httpx
import pytest
from fastapi.testclient import TestClient

from se_pov_builder.app import create_app
from se_pov_builder.config import Settings
from se_pov_builder.llm import LLMUnavailable, OllamaProvider, OpenAICompatibleProvider, build_provider


def transport(capture, response):
    def handler(request):
        capture.append(request)
        return httpx.Response(200, json=response)
    return httpx.MockTransport(handler)


def test_disabled_by_default(client):
    status = client.get("/api/llm/status").json()
    assert status["enabled"] is False
    account = client.post("/api/accounts", json={"name": "A"}).json()
    deal = client.post("/api/deals", json={"account_id": account["id"], "name": "D"}).json()
    assert client.post(f"/api/deals/{deal['id']}/llm/discovery-summary").status_code == 409


def test_disabled_provider_raises():
    with pytest.raises(LLMUnavailable):
        build_provider(Settings()).complete("hi")


def test_ollama_request_format():
    seen = []
    p = OllamaProvider("http://localhost:11434/", "llama3", transport=transport(
        seen, {"message": {"role": "assistant", "content": "hello"}}))
    assert p.complete("prompt", system="sys") == "hello"
    body = json.loads(seen[0].content)
    assert str(seen[0].url) == "http://localhost:11434/api/chat"
    assert body["stream"] is False and body["messages"][0] == {"role": "system", "content": "sys"}


def test_openai_compatible_request_format():
    seen = []
    p = OpenAICompatibleProvider("http://localhost:8001/v1", "m", api_key="k", transport=transport(
        seen, {"choices": [{"message": {"content": "draft"}}]}))
    assert p.complete("prompt") == "draft"
    assert str(seen[0].url) == "http://localhost:8001/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer k"


def test_bad_response_raises():
    p = OpenAICompatibleProvider("http://x/v1", "m", transport=transport([], {"unexpected": True}))
    with pytest.raises(LLMUnavailable):
        p.complete("prompt")


def test_settings_require_url_and_model():
    with pytest.raises(ValueError):
        Settings(llm_provider="ollama").validate()


def test_summary_endpoint_labels_output(settings):
    class Fake:
        name = "fake"
        enabled = True

        def complete(self, prompt, system=""):
            assert "Use only the facts provided" in system
            return "summary text"

    with TestClient(create_app(settings, llm=Fake())) as c:
        account = c.post("/api/accounts", json={"name": "A"}).json()
        deal = c.post("/api/deals", json={"account_id": account["id"], "name": "D"}).json()
        r = c.post(f"/api/deals/{deal['id']}/llm/discovery-summary").json()
        assert r["draft"] == "summary text" and "AI-generated draft" in r["label"]
