import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence_aware_crypto_call_recognition import api, llm
from evidence_aware_crypto_call_recognition.contract import Cost
from evidence_aware_crypto_call_recognition.llm import LlmSettings

client = TestClient(api.app)


def test_health_reports_versions():
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["policy"] and body["prompt"].startswith("classify_v1@")


def test_pasted_text_without_source_is_marked_as_manual_input():
    body = client.post("/api/classify/text", json={"text": "Buying $SOL here."}).json()
    assert body["label"] == "BUY"
    assert body["source"]["source_id"].startswith("manual:") and body["source"]["is_manual_input"] is True
    assert "MANUAL_INPUT" in body["reasons"]
    assert any("must not be used for scoring" in text for text in body["limitations"])


def test_pasted_text_with_real_source_is_not_manual():
    body = client.post("/api/classify/text", json={"text": "Buying $SOL here.", "source_id": "x:42",
                                                   "author_handle": "@kol"}).json()
    assert body["source"] == {"source_id": "x:42", "platform": "other", "url": None, "posted_at": None,
                              "is_manual_input": False}
    assert body["author"]["handle"] == "@kol"


def test_json_post_without_source_still_abstains():
    body = client.post("/api/classify", json={"post": {"text": "Buying $SOL here."}}).json()
    assert body["label"] == "ABSTAIN" and "MISSING_SOURCE_ID" in body["reasons"]


def test_batch_with_gold_labels_returns_metrics():
    items = [json.loads(line) for line in Path("data/dev.jsonl").read_text().splitlines()[:10]]
    body = client.post("/api/classify/batch", json={"items": items}).json()
    assert body["summary"]["posts"] == 10 and len(body["decisions"]) == 10
    assert body["evaluation"]["n"] == 10


def test_batch_of_bare_posts_has_no_metrics():
    body = client.post("/api/classify/batch", json={"items": [{"source_id": "a", "text": "gm"}]}).json()
    assert body["evaluation"] is None and body["decisions"][0]["label"] == "NO_NEW_BUY"


def test_batch_rejects_invalid_items_and_oversized_requests():
    assert client.post("/api/classify/batch", json={"items": [{"text": 1}]}).status_code == 422
    too_many = [{"source_id": str(i), "text": "gm"} for i in range(api.MAX_BATCH_POSTS + 1)]
    assert client.post("/api/classify/batch", json={"items": too_many}).status_code == 413


def test_unknown_request_fields_are_rejected():
    assert client.post("/api/classify/text", json={"text": "gm", "sentiment": "bullish"}).status_code == 422


def test_llm_backend_through_api_uses_guard_and_reports_cost(monkeypatch, tmp_path):
    output = {"label": "BUY", "confidence": 0.9, "reasons": [], "limitations": [],
              "calls": [{"asset_as_written": "$OP", "supporting_text": "Buying $OP here", "evidence_origin": "post",
                         "explicitness": "explicit", "conditional": False, "condition_text": None}]}

    async def fake(post, settings):
        return output, Cost(usd=0.001, input_tokens=10, output_tokens=5, latency_ms=3, llm_calls=1)

    monkeypatch.setattr(llm, "_call_agent_sdk", fake)
    monkeypatch.setattr(api, "_settings", lambda request: LlmSettings(model="test", cache_dir=tmp_path))
    body = client.post("/api/classify/text", json={"text": "Buying $OP here", "source_id": "x:1",
                                                   "backend": "llm"}).json()
    assert body["label"] == "BUY" and body["cost"]["llm_calls"] == 1 and body["versions"]["backend"] == "llm"


def test_ui_is_served():
    response = client.get("/")
    if "UI not built" in response.text:
        pytest.skip("frontend not built")
    assert response.status_code == 200 and '<div id="root">' in response.text
