"""Real Claude call through the Agent SDK. Skipped unless EACR_LIVE=1."""

import pytest

from evidence_aware_crypto_call_recognition.contract import Label
from evidence_aware_crypto_call_recognition.llm import LlmSettings
from evidence_aware_crypto_call_recognition.pipeline import Backend, classify_sync
from tests.conftest import make_post


@pytest.mark.live
def test_live_llm_recognises_non_english_buy_and_passes_guard():
    decision = classify_sync(make_post("$SOL abhi le lo bhai, 140 pe best entry hai"), Backend.LLM,
                             LlmSettings(cache_dir=None))
    assert decision.label == Label.BUY
    assert decision.calls[0].asset.symbol == "SOL"
    assert decision.cost.llm_calls == 1 and decision.cost.usd > 0
