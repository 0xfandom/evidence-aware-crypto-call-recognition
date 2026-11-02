from evidence_aware_crypto_call_recognition.assets import find_asset_mentions
from evidence_aware_crypto_call_recognition.contract import AssetStatus


def keys(text):
    return [m.key for m in find_asset_mentions(text)]


def test_cashtags_are_found_and_uppercased():
    assert keys("loving $sol and $Jup today") == ["SOL", "JUP"]


def test_dollar_amounts_are_not_assets():
    assert keys("won $50 and $1.2k last night") == []


def test_bare_ticker_only_for_known_majors():
    assert keys("BTC and ETH are fine, CT and ETF are not tickers") == ["BTC", "ETH"]


def test_known_names_map_to_symbols_but_keep_written_form():
    mention = find_asset_mentions("Solana is fast")[0]
    assert (mention.key, mention.as_written) == ("SOL", "Solana")


def test_evm_address_is_an_address_not_a_symbol():
    address = "0x" + "4f" * 20
    mention = find_asset_mentions(f"CA {address}")[0]
    assert mention.is_address and mention.to_asset().status == AssetStatus.ADDRESS
    assert mention.to_asset().verified is False


def test_solana_style_address_detected():
    address = "7Qp9zXkVt3mWcR8bN2hLfJd5sGy4eA6uTnK1oP3iHvMw"
    assert keys(f"ca: {address}") == [address]


def test_plain_long_word_is_not_a_solana_address():
    assert keys("supercalifragilisticexpialidociousword") == []
