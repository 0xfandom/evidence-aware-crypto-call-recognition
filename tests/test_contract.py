import pytest
from pydantic import ValidationError

from evidence_aware_crypto_call_recognition.contract import Asset, AssetStatus, Post
from tests.conftest import make_post


def test_content_hash_is_stable_and_sensitive_to_text():
    assert make_post("buy $SOL").content_hash() == make_post("buy $SOL").content_hash()
    assert make_post("buy $SOL").content_hash() != make_post("buy $ETH").content_hash()


def test_unknown_input_fields_are_rejected():
    with pytest.raises(ValidationError):
        Post.model_validate({"source_id": "1", "text": "hi", "sentiment": "bullish"})


def test_asset_can_never_be_marked_verified():
    with pytest.raises(ValidationError):
        Asset(status=AssetStatus.SYMBOL, symbol="SOL", verified=True)
