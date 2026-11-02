"""Rule-backend behaviour per policy case, through the guard (what a caller actually gets).

Sentences here are written fresh, not copied from the datasets. Cases the offline
rules are known to miss are marked xfail: they document a limitation that the
LLM backend is meant to cover, and they must not be "fixed" by adding the exact
phrase to the lexicon.
"""

import pytest

from evidence_aware_crypto_call_recognition.contract import AssetStatus, EvidenceOrigin, Label, PostKind
from evidence_aware_crypto_call_recognition.pipeline import classify_sync
from tests.conftest import make_post


def decide(text, **kwargs):
    return classify_sync(make_post(text, **kwargs))


@pytest.mark.parametrize(
    "text",
    [
        "Buying $NEAR at 4.10, adding below 4.",
        "Accumulate $OP in this range.",
        "Longing $ETH here with a tight stop.",
    ],
)
def test_explicit_buy(text):
    decision = decide(text)
    assert decision.label == Label.BUY
    assert decision.calls[0].explicitness == "explicit"


def test_implicit_buy_is_recognised_and_marked_implicit():
    decision = decide("$AVAX at 20 is a gift for anyone paying attention.")
    assert decision.label == Label.BUY
    assert decision.calls[0].explicitness == "implicit"


@pytest.mark.parametrize(
    "text, reason",
    [
        ("$ETH will hit 10k by 2027.", "FORECAST"),
        ("Still holding my $BTC, never selling.", "EXISTING_POSITION"),
        ("I called $SOL at 9 back then.", "RETROSPECTIVE"),
        ("Do not buy $XYZ, the team is anonymous.", "NEGATED"),
    ],
)
def test_non_calls_are_no_new_buy(text, reason):
    decision = decide(text)
    assert decision.label == Label.NO_NEW_BUY
    assert reason in decision.reasons


def test_question_is_not_a_call():
    assert decide("Would you buy $DOT here?").label == Label.NO_NEW_BUY


def test_hedged_intention_is_not_a_call():
    assert decide("Maybe adding $ATOM at some point, not sure.").label == Label.NO_NEW_BUY


def test_conditional_call_keeps_condition_text():
    decision = decide("Buy $LINK if it closes above 20 this week.")
    assert decision.label == Label.BUY
    call = decision.calls[0]
    assert call.conditional and "closes above 20" in call.condition_text


def test_referral_is_not_a_call():
    decision = decide("Use my referral code on the exchange for a trading bonus!")
    assert decision.label == Label.NO_NEW_BUY


def test_promotion_with_buy_wording_abstains():
    decision = decide("Sponsored post: buy $NEWCOIN before it lists.")
    assert decision.label == Label.ABSTAIN
    assert "PROMOTIONAL_CONTENT" in decision.reasons


def test_clear_sarcasm_is_not_a_call():
    assert decide("Great idea, buy $SCAMX with your savings.").label == Label.NO_NEW_BUY


def test_possible_joke_abstains():
    decision = decide("buying $MEMEZ because the logo is funny lol")
    assert decision.label == Label.ABSTAIN


def test_rotation_only_buys_the_destination_asset():
    decision = decide("Rotated out of $ADA into $DOT this morning.")
    assert decision.label == Label.BUY
    assert [c.asset.symbol for c in decision.calls] == ["DOT"]


def test_multiple_assets_each_get_a_call():
    decision = decide("Buying $BTC and $SOL on this dip.")
    assert sorted(c.asset.symbol for c in decision.calls) == ["BTC", "SOL"]


def test_repost_is_not_the_authors_call():
    decision = decide("Buy $ARB now", kind=PostKind.REPOST, quoted="Buy $ARB now")
    assert decision.label == Label.NO_NEW_BUY


def test_endorsed_quote_takes_evidence_from_quoted_post():
    decision = decide("Agree, same.", kind=PostKind.QUOTE, quoted="Accumulating $INJ under 20")
    assert decision.label == Label.BUY
    assert decision.calls[0].evidence_origin == EvidenceOrigin.QUOTED


def test_quote_with_unclear_stance_abstains():
    decision = decide("hmm", kind=PostKind.QUOTE, quoted="Loading $INJ here")
    assert decision.label == Label.ABSTAIN


def test_reply_answering_a_pick_request_is_a_call():
    decision = decide("$TIA for sure", kind=PostKind.REPLY, parent="Which coin would you buy right now?")
    assert decision.label == Label.BUY
    assert "REPLY_ANSWERS_BUY_REQUEST" in decision.reasons


def test_buy_wording_without_asset_abstains():
    decision = decide("Get in now, this one is about to run.")
    assert decision.label == Label.ABSTAIN


def test_generic_advice_is_not_a_call():
    assert decide("Buy the dip and stay patient.").label == Label.NO_NEW_BUY


def test_long_post_uses_only_the_sentence_that_carries_the_call():
    filler = "Markets were choppy this week and volume stayed low across most venues. " * 10
    decision = decide(filler + "I'm accumulating $SEI below 0.30 for the next month. " + filler)
    assert decision.label == Label.BUY
    assert decision.calls[0].supporting_text == "I'm accumulating $SEI below 0.30 for the next month."
    assert any("Long post" in limitation for limitation in decision.limitations)


def test_contract_address_call_is_never_verified():
    address = "0x" + "5a" * 20
    decision = decide(f"Get in early. CA: {address} buy before it lists")
    assert decision.label == Label.BUY
    asset = decision.calls[0].asset
    assert asset.status == AssetStatus.ADDRESS and asset.verified is False


def test_post_with_no_asset_and_no_action():
    decision = decide("gm, coffee first")
    assert decision.label == Label.NO_NEW_BUY
    assert decision.confidence >= 0.8


@pytest.mark.xfail(reason="Known rules limitation: misspelled buy verbs are not in the lexicon", strict=True)
def test_misspelled_buy_verb():
    assert decide("im acumulating $OP evry red day").label == Label.BUY


@pytest.mark.xfail(reason="Known rules limitation: non-English buy instructions are not understood", strict=True)
def test_non_english_buy_instruction():
    assert decide("$OP kharid lo abhi").label == Label.BUY


def test_warning_anywhere_in_post_blocks_a_rules_buy():
    address = "0x" + "6b" * 20
    decision = decide(f"Honeypot alert: {address}. You can buy it. You cannot sell it.")
    assert decision.label == Label.ABSTAIN
    assert "WARNING_CONTEXT" in decision.reasons


def test_asset_only_in_parent_is_a_weak_spot_not_a_confident_no():
    decision = decide("same, picked up a bag myself", kind=PostKind.REPLY, parent="Accumulating $NEAR under 5")
    assert decision.confidence <= 0.7
    assert "WEAK_SPOT_CONTEXT_ASSET" in decision.reasons


def test_several_assets_lower_rule_confidence_but_keep_the_call():
    decision = decide("Sold some $ETH this week. Adding more $OP here.")
    assert decision.label == Label.BUY
    assert decision.confidence <= 0.7
    assert "WEAK_SPOT_MULTIPLE_ASSETS" in decision.reasons


def test_single_asset_clean_call_keeps_full_confidence():
    decision = decide("Buying $NEAR here.")
    assert decision.confidence >= 0.8
    assert not any(r.startswith("WEAK_SPOT") for r in decision.reasons)


def test_evidence_is_the_sentence_that_names_the_asset():
    address = "0x" + "5a" * 20
    decision = decide(f"Get in early. CA: {address} buy before it lists")
    assert decision.calls[0].supporting_text == f"CA: {address} buy before it lists"
