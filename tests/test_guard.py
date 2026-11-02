"""Evidence-integrity invariants. The guard must hold no matter what a backend proposes."""

from evidence_aware_crypto_call_recognition.contract import AssetStatus, AuthorStatus, EvidenceOrigin, Label, PostKind
from evidence_aware_crypto_call_recognition.guard import apply_guard
from evidence_aware_crypto_call_recognition.proposal import Proposal, ProposedCall
from tests.conftest import make_post

TEXT = "Loading up on $SOL here, 140 is the level."


def buy(*calls, confidence=0.95):
    return Proposal(Label.BUY, confidence, calls=tuple(calls), backend="fake")


def call(asset="$SOL", supporting="Loading up on $SOL here, 140 is the level.", origin=EvidenceOrigin.POST):
    return ProposedCall(asset, supporting, "explicit", origin)


def test_valid_buy_passes_with_source_and_author_copied_from_input():
    decision = apply_guard(make_post(TEXT, source_id="x:99", handle="@kol"), buy(call()))
    assert decision.label == Label.BUY
    assert decision.source.source_id == "x:99"
    assert decision.author.status == AuthorStatus.ATTRIBUTED and decision.author.handle == "@kol"
    assert decision.guard_corrections == ()


def test_missing_source_id_forces_abstain_even_at_full_confidence():
    decision = apply_guard(make_post(TEXT, source_id=None), buy(call(), confidence=1.0))
    assert decision.label == Label.ABSTAIN
    assert "MISSING_SOURCE_ID" in decision.reasons
    assert decision.calls == ()


def test_blank_source_id_counts_as_missing():
    assert apply_guard(make_post(TEXT, source_id="   "), buy(call())).label == Label.ABSTAIN


def test_missing_author_keeps_buy_but_marks_author_unresolved():
    decision = apply_guard(make_post(TEXT, handle=None), buy(call()))
    assert decision.label == Label.BUY
    assert decision.author.status == AuthorStatus.UNRESOLVED and decision.author.handle is None
    assert any("must not be attributed" in limitation for limitation in decision.limitations)


def test_paraphrased_supporting_text_is_rejected():
    decision = apply_guard(make_post(TEXT), buy(call(supporting="The author recommends buying Solana.")))
    assert decision.label == Label.ABSTAIN
    assert "EVIDENCE_NOT_VERIFIABLE" in decision.reasons


def test_invented_asset_is_never_accepted():
    decision = apply_guard(make_post(TEXT), buy(call(asset="$ETH")))
    assert decision.label == Label.ABSTAIN
    assert "ASSET_NOT_IN_SOURCE" in decision.reasons


def test_invented_contract_address_is_never_accepted():
    decision = apply_guard(make_post(TEXT), buy(call(asset="0x" + "7c" * 20)))
    assert decision.label == Label.ABSTAIN


def test_invented_asset_call_is_dropped_while_valid_call_survives():
    decision = apply_guard(make_post(TEXT), buy(call(), call(asset="$ETH")))
    assert decision.label == Label.BUY
    assert [c.asset.symbol for c in decision.calls] == ["SOL"]
    assert any("$ETH" in correction for correction in decision.guard_corrections)


def test_wrong_evidence_origin_is_corrected_not_trusted():
    decision = apply_guard(make_post(TEXT), buy(call(origin=EvidenceOrigin.QUOTED)))
    assert decision.calls[0].evidence_origin == EvidenceOrigin.POST
    assert decision.guard_corrections


def test_low_confidence_buy_becomes_abstain():
    decision = apply_guard(make_post(TEXT), buy(call(), confidence=0.3))
    assert decision.label == Label.ABSTAIN and "LOW_CONFIDENCE" in decision.reasons


def test_calls_attached_to_non_buy_label_are_dropped():
    proposal = Proposal(Label.NO_NEW_BUY, 0.9, calls=(call(),), backend="fake")
    decision = apply_guard(make_post(TEXT), proposal)
    assert decision.label == Label.NO_NEW_BUY and decision.calls == ()
    assert decision.guard_corrections


def test_guard_never_upgrades_an_abstain():
    proposal = Proposal(Label.ABSTAIN, 0.99, calls=(call(),), backend="fake")
    assert apply_guard(make_post(TEXT), proposal).label == Label.ABSTAIN


def test_name_is_kept_as_written_and_flagged_unverified():
    text = "Solana under 150 is a gift."
    decision = apply_guard(make_post(text), buy(call(asset="Solana", supporting=text)))
    asset = decision.calls[0].asset
    assert (asset.status, asset.symbol, asset.as_written, asset.verified) == (AssetStatus.SYMBOL, "SOL", "Solana", False)
    assert any("not matched to a contract" in limitation for limitation in decision.limitations)


def test_buy_with_unresolved_asset_is_capped_and_explained():
    text = "This one is about to send, get in."
    decision = apply_guard(make_post(text), buy(call(asset=None, supporting=text)))
    assert decision.label == Label.BUY
    assert decision.calls[0].asset.status == AssetStatus.UNRESOLVED
    assert decision.confidence <= 0.6


def test_every_decision_carries_versions_and_input_hash():
    post = make_post(TEXT)
    decision = apply_guard(post, buy(call()))
    assert decision.input_hash == post.content_hash()
    assert decision.versions.policy and decision.versions.code and decision.versions.backend == "fake"


def test_verbatim_but_irrelevant_evidence_is_rejected():
    text = "gm everyone. Buying $SOL here."
    decision = apply_guard(make_post(text), buy(call(supporting="gm everyone.")))
    assert decision.label == Label.ABSTAIN
    assert "EVIDENCE_NOT_ABOUT_ASSET" in decision.reasons


def test_asset_named_in_the_previous_sentence_is_accepted():
    text = "$BTC 150k by Q2. Keep stacking every dip."
    decision = apply_guard(make_post(text), buy(call(asset="$BTC", supporting="Keep stacking every dip.")))
    assert decision.label == Label.BUY


def test_asset_far_from_the_evidence_is_rejected():
    text = "$BTC looks strong. Markets are quiet today. Keep stacking every dip."
    decision = apply_guard(make_post(text), buy(call(asset="$BTC", supporting="Keep stacking every dip.")))
    assert decision.label == Label.ABSTAIN


def test_reply_endorsing_an_asset_named_only_in_the_parent_is_accepted():
    post = make_post("same, in too", kind=PostKind.REPLY, parent="Buying $OP here")
    decision = apply_guard(post, buy(call(asset="$OP", supporting="same, in too")))
    assert decision.label == Label.BUY


def test_irrelevant_call_is_dropped_while_relevant_call_survives():
    text = "gm everyone. Buying $SOL here."
    decision = apply_guard(make_post(text), buy(call(supporting="Buying $SOL here."), call(supporting="gm everyone.")))
    assert decision.label == Label.BUY
    assert [c.supporting_text for c in decision.calls] == ["Buying $SOL here."]


def test_clause_evidence_with_asset_earlier_in_the_sentence_is_accepted():
    text = "yall sleepin on $GLORP lol. 400k mcap, im loading up every dip"
    decision = apply_guard(make_post(text), buy(call(asset="$GLORP", supporting="im loading up every dip")))
    assert decision.label == Label.BUY


def test_symbol_without_dollar_sign_counts_as_a_mention():
    text = "rotating out of $DOGE. jup is the play now, buying $JUP"
    decision = apply_guard(make_post(text), buy(call(asset="$JUP", supporting="jup is the play now")))
    assert decision.label == Label.BUY


def test_symbol_inside_another_word_is_not_a_mention():
    text = "Solid setup. Keep adding. Markets are quiet. Also holding $SOL."
    decision = apply_guard(make_post(text), buy(call(asset="$SOL", supporting="Keep adding.")))
    assert decision.label == Label.ABSTAIN
