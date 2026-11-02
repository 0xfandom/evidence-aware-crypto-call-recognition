from evidence_aware_crypto_call_recognition.contract import Gold, Label, LabelledPost
from evidence_aware_crypto_call_recognition.evaluate import evaluate, wilson_interval
from evidence_aware_crypto_call_recognition.pipeline import Backend
from tests.conftest import make_post


def row(text, label, assets=(), source_id="r"):
    return LabelledPost(post=make_post(text, source_id=source_id), gold=Gold(label=label, assets=assets))


def test_wilson_interval_bounds():
    low, high = wilson_interval(9, 10)
    assert 0.5 < low < 0.9 < high <= 1.0
    assert wilson_interval(0, 0) is None


def test_report_counts_hits_misses_false_buys_and_abstentions():
    rows = [
        row("Buying $NEAR here.", Label.BUY, ("NEAR",), "a"),
        row("$NEAR 20 by 2027.", Label.BUY, ("NEAR",), "b"),
        row("Buying $OP here.", Label.NO_NEW_BUY, (), "c"),
        row("Get in now before it runs.", Label.ABSTAIN, (), "d"),
    ]
    report = evaluate(rows, Backend.RULES).report
    assert report["buy"]["correct"] == 1
    assert report["buy"]["missed_as_no_new_buy"] == 1
    assert report["buy"]["false_buy"] == 1
    assert report["abstention"]["on_gold_abstain"] == 1
    assert report["cost"]["usd_total"] == 0


def test_wrong_asset_is_counted_as_attribution_error():
    rows = [row("Buying $NEAR here.", Label.BUY, ("OP",), "a")]
    report = evaluate(rows, Backend.RULES).report
    assert report["attribution_errors_on_predicted_buy"] == {"asset_missed": 1, "asset_extra": 1}
