import json
from pathlib import Path

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from ai.llm_client import LLMClient
from app.ingestion import get_llm_client
from app.main import app
from app.settings import get_settings
from engine.pack_loader import FORBIDDEN_TERMS


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Same reasoning as test_campaigns_api.py's own fixture: an env var +
    # cache clear, since get_settings() isn't always reached via Depends.
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _mock_client(handler) -> LLMClient:
    return LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )


def test_extract_text_endpoint_returns_normalised_text():
    with TestClient(app) as client:
        response = client.post(
            "/api/ingestion/extract-text",
            files={"file": ("notes.txt", b"line one\r\n\r\n\r\nline two\r\n", "text/plain")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "notes.txt"
    assert body["text"] == "line one\n\nline two"
    assert body["char_count"] == len(body["text"])


def test_extract_text_endpoint_400s_for_an_unsupported_extension():
    with TestClient(app) as client:
        response = client.post(
            "/api/ingestion/extract-text",
            files={"file": ("book.docx", b"whatever", "application/octet-stream")},
        )

    assert response.status_code == 400
    assert "unsupported file type" in response.json()["detail"]


def test_extract_module_endpoint_returns_a_draft():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {"items": [{"id": "grapple_gun", "name": "Grapple Gun"}]}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": json.dumps(payload)}}]},
        )

    app.dependency_overrides[get_llm_client] = lambda: _mock_client(handler)

    with TestClient(app) as client:
        response = client.post("/api/ingestion/extract-module", json={"text": "some rulebook"})

    assert response.status_code == 200
    body = response.json()
    assert body["truncated"] is False
    assert body["draft"]["items"][0]["name"] == "Grapple Gun"
    assert body["draft"]["playbooks"] == []


def test_extract_module_endpoint_503s_when_the_llm_is_not_configured():
    with TestClient(app) as client:
        response = client.post("/api/ingestion/extract-module", json={"text": "some rulebook"})

    assert response.status_code == 503


def _finalize_body(**draft_overrides) -> dict:
    return {
        "id": "my-hack",
        "name": "My Hack",
        "description": "A homebrew FitD hack",
        "version": "0.1.0",
        "draft": {"items": [{"id": "grapple_gun", "name": "Grapple Gun"}], **draft_overrides},
    }


def test_finalize_module_endpoint_returns_a_content_pack():
    with TestClient(app) as client:
        response = client.post("/api/ingestion/finalize-module", json=_finalize_body())

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "my-hack"
    assert body["items"][0]["name"] == "Grapple Gun"
    assert body["playbooks"] == []


def test_finalize_module_endpoint_allows_core_book_terms_in_a_private_module():
    # NOTICE.md/C6: owners may ingest core-book content they own - the
    # firewall guards distribution, not private modules. Term drawn from
    # FORBIDDEN_TERMS rather than hardcoded (licensing-grep), same
    # reasoning as test_pack_loader.py's own test.
    forbidden_term = FORBIDDEN_TERMS[0]
    body = _finalize_body(
        items=[{"id": "lantern", "name": f"A lantern from {forbidden_term}'s docks"}]
    )

    with TestClient(app) as client:
        response = client.post("/api/ingestion/finalize-module", json=body)

    assert response.status_code == 200
    assert forbidden_term in response.json()["items"][0]["name"]


def test_finalize_module_endpoint_422s_for_a_draft_that_fails_schema_validation():
    body = _finalize_body(items=[{"id": "grapple_gun"}])  # missing required "name"

    with TestClient(app) as client:
        response = client.post("/api/ingestion/finalize-module", json=body)

    assert response.status_code == 422


def _content_pack(**overrides) -> dict:
    body = {
        "id": "my-hack",
        "name": "My Hack",
        "description": "A homebrew hack",
        "version": "0.1.0",
    }
    body.update(overrides)
    return body


def _save_module_body(**pack_overrides) -> dict:
    return {"pack": _content_pack(**pack_overrides)}


def test_save_module_endpoint_persists_and_echoes_the_pack():
    with TestClient(app) as client:
        response = client.post("/api/ingestion/modules", json=_save_module_body())

    assert response.status_code == 200
    assert response.json()["id"] == "my-hack"


def test_save_module_endpoint_400s_for_an_unsafe_module_id():
    with TestClient(app) as client:
        response = client.post("/api/ingestion/modules", json=_save_module_body(id="../escape"))

    assert response.status_code == 400


def test_module_with_core_book_terms_saves_and_loads_privately():
    # NOTICE.md/C6: the whole private round trip works for a module built
    # from a core book the user owns - saved, listed, and fetched again
    # (module_store loads with private=True, so `load_pack`'s
    # distribution firewall doesn't apply). Term drawn from
    # FORBIDDEN_TERMS rather than hardcoded (licensing-grep).
    forbidden_term = FORBIDDEN_TERMS[0]
    with TestClient(app) as client:
        saved = client.post(
            "/api/ingestion/modules",
            json=_save_module_body(name=f"Nights in {forbidden_term}"),
        )
        assert saved.status_code == 200

        listing = client.get("/api/ingestion/modules")
        fetched = client.get("/api/ingestion/modules/my-hack")

    assert listing.status_code == 200
    assert listing.json()[0]["name"] == f"Nights in {forbidden_term}"
    assert fetched.status_code == 200
    assert fetched.json()["name"] == f"Nights in {forbidden_term}"


def test_list_modules_endpoint_returns_summaries_of_every_saved_module():
    with TestClient(app) as client:
        client.post("/api/ingestion/modules", json=_save_module_body(id="hack-a", name="Hack A"))
        client.post("/api/ingestion/modules", json=_save_module_body(id="hack-b", name="Hack B"))

        response = client.get("/api/ingestion/modules")

    assert response.status_code == 200
    ids = {summary["id"] for summary in response.json()}
    assert ids == {"hack-a", "hack-b"}


def test_get_module_endpoint_returns_the_full_pack():
    with TestClient(app) as client:
        client.post("/api/ingestion/modules", json=_save_module_body())

        response = client.get("/api/ingestion/modules/my-hack")

    assert response.status_code == 200
    assert response.json()["name"] == "My Hack"


def test_get_module_endpoint_404s_for_an_unknown_module():
    with TestClient(app) as client:
        response = client.get("/api/ingestion/modules/nope")

    assert response.status_code == 404
