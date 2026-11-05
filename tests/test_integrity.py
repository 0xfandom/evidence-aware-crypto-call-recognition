import copy
import unittest

from helpers import PACKAGE, load_jsonl, make_case

from evidence_aware_crypto_call_recognition.contract import text_sha256, utf16_length, utf16_slice
from evidence_aware_crypto_call_recognition.integrity import capacity_errors, expected_catalogue, input_errors


class DevelopmentInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_jsonl(PACKAGE / "development.inputs.jsonl")
        cls.references = {r["case_id"]: r for r in load_jsonl(PACKAGE / "development.references.jsonl")}

    def test_invalid_controls_report_every_expected_error(self):
        for case in self.inputs:
            reference = self.references[case["case_id"]]
            errors = input_errors(case)
            if reference["expected_status"] == "INPUT_INVALID":
                self.assertTrue(set(reference["expected_errors"]) <= set(errors), case["case_id"])
            else:
                self.assertEqual(errors, [], case["case_id"])

    def test_supplied_catalogue_is_rebuilt_exactly(self):
        for case in self.inputs:
            if not input_errors(case):
                self.assertEqual(case["evidence_catalogue"], expected_catalogue(case))


class Tampering(unittest.TestCase):
    def setUp(self):
        self.case = make_case("I am starting a small $TESTA position today.", context=["Earlier note on $TESTA."])

    def test_clean_case_is_valid(self):
        self.assertEqual(input_errors(self.case), [])

    def test_text_change_breaks_hash(self):
        self.case["primary"]["text"] += " changed"
        self.assertIn("TEXT_HASH_MISMATCH", input_errors(self.case))

    def test_missing_author_is_technical(self):
        self.case["primary"]["author_id"] = None
        self.assertIn("MISSING_AUTHOR_ID", input_errors(self.case))

    def test_context_after_primary_is_future_context(self):
        self.case["context"][0]["published_at_utc"] = "2035-01-01T00:00:00Z"
        errors = input_errors(self.case)
        self.assertIn("FUTURE_CONTEXT", errors)
        self.assertIn("AFTER_INPUT_CUTOFF", errors)

    def test_catalogue_substitution(self):
        self.case["evidence_catalogue"][0]["end_utf16"] -= 1
        self.assertIn("EVIDENCE_CATALOGUE_MISMATCH", input_errors(self.case))

    def test_missing_field_is_malformed_not_a_crash(self):
        del self.case["primary"]["text"]
        self.assertIn("MALFORMED_INPUT", input_errors(self.case))

    def test_external_asset_evidence_is_rejected(self):
        self.case["asset_identity_evidence"] = [{"chain": "x"}]
        self.assertIn("UNEXPECTED_EXTERNAL_ASSET_EVIDENCE", input_errors(self.case))


class Utf16(unittest.TestCase):
    def test_spans_reconstruct_text_with_astral_characters_and_crlf(self):
        text = "🧭 A\r\n é\n\nAn allocation to $VEKRA today."
        case = make_case(text)
        self.assertEqual(input_errors(case), [])
        self.assertNotEqual(len(text), utf16_length(text))
        for span in case["evidence_catalogue"]:
            piece = utf16_slice(text, span["start_utf16"], span["end_utf16"])
            self.assertIn(piece, text)
        full = next(s for s in case["evidence_catalogue"] if s["start_utf16"] == 0 and s["end_utf16"] == utf16_length(text))
        self.assertEqual(utf16_slice(text, full["start_utf16"], full["end_utf16"]), text)
        self.assertEqual(text_sha256(text), case["primary"]["text_sha256"])


class Capacity(unittest.TestCase):
    def test_oversized_case_is_a_capacity_limit(self):
        case = make_case("x" * 10)
        big = copy.deepcopy(case)
        big["primary"]["text"] = "word " * 500_000
        self.assertEqual(capacity_errors(big), ["LOCAL_INPUT_CAPACITY"])
        self.assertEqual(capacity_errors(case), [])


if __name__ == "__main__":
    unittest.main()
