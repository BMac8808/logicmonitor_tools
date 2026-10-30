from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from se_pov_builder.app import create_app
from se_pov_builder.config import TOOL_ROOT, Settings
from se_pov_builder.knowledge import KnowledgeBase


@pytest.fixture(scope="session")
def kb() -> KnowledgeBase:
    return KnowledgeBase.load(TOOL_ROOT)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", content_dir=TOOL_ROOT,
                    cors_origins=["http://127.0.0.1:5173"], log_level="WARNING")


@pytest.fixture
def client(settings: Settings) -> TestClient:
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def deal(client: TestClient) -> dict:
    account = client.post("/api/accounts", json={"name": "Test Account (fictional)"}).json()
    return client.post("/api/deals", json={
        "account_id": account["id"], "name": "Test deal", "technical_context": ["network"],
    }).json()
