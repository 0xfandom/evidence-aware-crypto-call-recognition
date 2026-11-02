"""LLM wrapper logic, offline. The SDK call is replaced; what is tested is our handling around it."""

import json

import anyio
import pytest

from evidence_aware_crypto_call_recognition import llm, pipeline
from evidence_aware_crypto_call_recognition.contract import Cost, Label, PostKind
from evidence_aware_crypto_call_recognition.llm import LlmSettings, RunBudget, classify_with_llm
from evidence_aware_crypto_call_recognition.pipeline import Backend, classify
from tests.conftest import make_post

GOOD_OUTPUT = {
    "label": "BUY",
    "confidence": 0.9,
    "calls": [{"asset_as_written": "$OP", "supporting_text": "Buying $OP here", "evidence_origin": "post",
               "explicitness": "explicit", "conditional": False, "condition_text": None}],
    "reasons": ["EXPLICIT"],
    "limitations": [],
}


@pytest.fixture
def settings(tmp_path):
    return LlmSettings(model="test-model", cache_dir=tmp_path / "cache", run_budget_usd=1.0)


def fake_sdk(output=GOOD_OUTPUT, usd=0.02, calls=None):
    async def _fake(post, settings):
        if calls is not None:
            calls.append(post.source_id)
        return output, Cost(usd=usd, input_tokens=100, output_tokens=20, latency_ms=5, llm_calls=1)
    return _fake


def run(coro_fn, *args):
    return anyio.run(coro_fn, *args)


def test_successful_call_is_cached_and_reused(monkeypatch, settings):
    calls = []
    monkeypatch.setattr(llm, "_call_agent_sdk", fake_sdk(calls=calls))
    post = make_post("Buying $OP here")
    first = run(classify_with_llm, post, settings, RunBudget(1.0))
    second = run(classify_with_llm, post, settings, RunBudget(1.0))
    assert first.label == second.label == Label.BUY
    assert calls == ["t-1"]
    assert second.cost.cache_hits == 1 and second.cost.usd == 0


def test_changed_post_is_not_served_from_cache(monkeypatch, settings):
    calls = []
    monkeypatch.setattr(llm, "_call_agent_sdk", fake_sdk(calls=calls))
    run(classify_with_llm, make_post("Buying $OP here"), settings, RunBudget(1.0))
    run(classify_with_llm, make_post("Buying $OP here!"), settings, RunBudget(1.0))
    assert len(calls) == 2


def test_cache_key_depends_on_model_and_prompt_version():
    post = make_post("x")
    assert llm._cache_key(post, "model-a") != llm._cache_key(post, "model-b")


def test_exhausted_budget_abstains_without_calling(monkeypatch, settings):
    calls = []
    monkeypatch.setattr(llm, "_call_agent_sdk", fake_sdk(calls=calls))
    budget = RunBudget(limit_usd=0.01, spent_usd=0.01)
    proposal = run(classify_with_llm, make_post("Buying $OP here"), settings, budget)
    assert proposal.label == Label.ABSTAIN and proposal.reasons == ("BUDGET_EXHAUSTED",)
    assert calls == []


def test_spend_accumulates_until_budget_stops_calls(monkeypatch, settings):
    calls = []
    monkeypatch.setattr(llm, "_call_agent_sdk", fake_sdk(usd=0.4, calls=calls))
    budget = RunBudget(limit_usd=0.75)
    for i in range(4):
        run(classify_with_llm, make_post(f"Buying $OP here {i}", source_id=f"p{i}"), settings, budget)
    assert len(calls) == 2


def test_sdk_failure_becomes_abstain_with_cause(monkeypatch, settings):
    async def broken(post, settings):
        raise RuntimeError("auth failed")
    monkeypatch.setattr(llm, "_call_agent_sdk", broken)
    proposal = run(classify_with_llm, make_post("Buying $OP here"), settings, RunBudget(1.0))
    assert proposal.label == Label.ABSTAIN and proposal.reasons == ("LLM_ERROR",)
    assert "auth failed" in proposal.limitations[0]


def test_malformed_output_becomes_abstain_and_is_not_cached(monkeypatch, settings):
    monkeypatch.setattr(llm, "_call_agent_sdk", fake_sdk(output={"label": "STRONG_BUY"}))
    proposal = run(classify_with_llm, make_post("Buying $OP here"), settings, RunBudget(1.0))
    assert proposal.label == Label.ABSTAIN and proposal.reasons == ("LLM_OUTPUT_INVALID",)
    assert not list(settings.cache_dir.glob("*.json")) if settings.cache_dir.exists() else True


def test_model_never_receives_author_or_source_id():
    prompt = llm._user_prompt(make_post("Buying $OP here", source_id="secret-id", handle="@secret_handle"))
    assert "secret-id" not in prompt and "secret_handle" not in prompt
    assert json.loads(prompt.removeprefix("<post>\n").removesuffix("\n</post>"))["text"] == "Buying $OP here"


def test_hallucinated_llm_asset_is_blocked_by_guard(monkeypatch, settings):
    invented = {**GOOD_OUTPUT, "calls": [{**GOOD_OUTPUT["calls"][0], "asset_as_written": "$ARB"}]}
    monkeypatch.setattr(llm, "_call_agent_sdk", fake_sdk(output=invented))
    decision = run(classify, make_post("Buying $OP here"), Backend.LLM, settings, RunBudget(1.0))
    assert decision.label == Label.ABSTAIN


def test_hybrid_skips_llm_when_rules_are_confident(monkeypatch, settings):
    calls = []
    monkeypatch.setattr(llm, "_call_agent_sdk", fake_sdk(calls=calls))
    monkeypatch.setattr(pipeline, "classify_with_llm", llm.classify_with_llm)
    decision = run(classify, make_post("gm everyone"), Backend.HYBRID, settings, RunBudget(1.0))
    assert decision.versions.backend == "hybrid:rules" and calls == []


def test_hybrid_escalates_when_rules_are_unsure(monkeypatch, settings):
    calls = []
    monkeypatch.setattr(llm, "_call_agent_sdk", fake_sdk(calls=calls))
    decision = run(classify, make_post("Buying $OP here lol"), Backend.HYBRID, settings, RunBudget(1.0))
    assert decision.versions.backend == "hybrid:llm" and calls == ["t-1"]


NOT_A_BUY_OUTPUT = {"label": "NO_NEW_BUY", "confidence": 0.9, "calls": [], "reasons": ["NOT_OWN_VOICE"],
                    "limitations": []}

# Posts the rules read as a confident BUY although they are not one (see test_rules.py).
RULES_FALSE_BUYS = [
    "Whales are buying $OP like crazy right now.",
    "Everyone is buying $OP, I'm staying out.",
    "Buying $OP at 2 was the best trade of my life.",
    "My friend keeps telling me to buy $OP.",
    "Buy $OP here. Just kidding, I hate it.",
]


@pytest.mark.parametrize("text", ["Buying $OP here", *RULES_FALSE_BUYS])
def test_hybrid_never_accepts_a_rules_buy_without_the_llm(monkeypatch, settings, text):
    calls = []
    monkeypatch.setattr(llm, "_call_agent_sdk", fake_sdk(output=NOT_A_BUY_OUTPUT, calls=calls))
    decision = run(classify, make_post(text), Backend.HYBRID, settings, RunBudget(1.0))
    assert decision.versions.backend == "hybrid:llm" and len(calls) == 1
    assert decision.label == Label.NO_NEW_BUY
    assert "ESCALATED_FROM_RULES:BUY" in decision.reasons


def test_hybrid_rules_buy_abstains_when_the_llm_fails(monkeypatch, settings):
    async def broken(post, settings):
        raise ConnectionError("network down")
    monkeypatch.setattr(llm, "_call_agent_sdk", broken)
    decision = run(classify, make_post("Buying $OP here"), Backend.HYBRID, settings, RunBudget(1.0))
    assert decision.label == Label.ABSTAIN and "LLM_ERROR" in decision.reasons


@pytest.mark.parametrize(
    "post",
    [
        make_post("same, in too", kind=PostKind.REPLY, parent="Buying $OP here"),
        make_post("Paid 2 $SOL for $OP, buying more $OP here"),
        make_post("Exploit on the bridge. Buying $OP here anyway"),
    ],
    ids=["context_asset", "payment_currency", "warning"],
)
def test_hybrid_escalates_weak_spots_even_when_rules_look_confident(monkeypatch, settings, post):
    calls = []
    monkeypatch.setattr(llm, "_call_agent_sdk", fake_sdk(calls=calls))
    decision = run(classify, post, Backend.HYBRID, settings, RunBudget(1.0))
    assert decision.versions.backend == "hybrid:llm" and len(calls) == 1


def test_model_written_text_never_reaches_the_output(monkeypatch, settings):
    claims = {**GOOD_OUTPUT, "reasons": ["EXPLICIT", "token is verified!"],
              "limitations": ["Token verified as the official mint."]}
    monkeypatch.setattr(llm, "_call_agent_sdk", fake_sdk(output=claims))
    decision = run(classify, make_post("Buying $OP here"), Backend.LLM, settings, RunBudget(1.0))
    assert decision.label == Label.BUY
    assert not any("verified as" in text for text in decision.limitations)
    assert "MODEL:EXPLICIT" in decision.reasons and not any("verified" in r for r in decision.reasons)


def test_hybrid_sends_market_talk_with_an_unknown_coin_to_the_llm(monkeypatch, settings):
    calls = []
    monkeypatch.setattr(llm, "_call_agent_sdk", fake_sdk(output=NOT_A_BUY_OUTPUT, calls=calls))
    post = make_post("Kaspa looks like a gift at these levels, sizing up.")
    decision = run(classify, post, Backend.HYBRID, settings, RunBudget(1.0))
    assert decision.versions.backend == "hybrid:llm" and len(calls) == 1


def test_parallel_calls_cannot_overspend_the_run_budget(monkeypatch, settings):
    calls = []

    async def slow_sdk(post, settings):
        calls.append(post.source_id)
        await anyio.sleep(0.01)
        return GOOD_OUTPUT, Cost(usd=0.05, llm_calls=1)

    monkeypatch.setattr(llm, "_call_agent_sdk", slow_sdk)
    budget = RunBudget(limit_usd=0.10)

    async def run_all():
        async with anyio.create_task_group() as group:
            for i in range(6):
                group.start_soon(classify_with_llm, make_post(f"Buying $OP here {i}", source_id=f"p{i}"),
                                 settings, budget)

    anyio.run(run_all)
    assert len(calls) == 2 and budget.spent_usd <= budget.limit_usd and budget.in_flight == 0
