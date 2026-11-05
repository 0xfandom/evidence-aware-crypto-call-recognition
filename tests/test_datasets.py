"""Regression checks on the disclosed development set and our own probe set.

These are not accuracy estimates. The rules were written with the development cases
and the first probe set in view.
"""
import unittest

from helpers import DATA, PACKAGE, load_jsonl

from evidence_aware_crypto_call_recognition.cli import process_case
from evidence_aware_crypto_call_recognition.contract import CONFIDENCE_GATE
from evidence_aware_crypto_call_recognition.selfcheck import output_errors


def outputs_for(inputs):
    return {case["case_id"]: process_case(case)[0] for case in inputs}


class DevelopmentSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_jsonl(PACKAGE / "development.inputs.jsonl")
        cls.references = {r["case_id"]: r for r in load_jsonl(PACKAGE / "development.references.jsonl")}
        cls.outputs = outputs_for(cls.inputs)

    def test_every_output_passes_the_contract(self):
        for case in self.inputs:
            self.assertEqual(output_errors(case, self.outputs[case["case_id"]]), [], case["case_id"])

    def test_labels_and_asset_sets_match_the_references(self):
        for case_id, reference in self.references.items():
            output = self.outputs[case_id]
            if reference["expected_status"] == "INPUT_INVALID":
                self.assertEqual(output["status"], "INPUT_INVALID", case_id)
                continue
            self.assertEqual(output["label"], reference["label"], case_id)
            self.assertEqual(sorted(b["asset_mention"] for b in output["current_buys"]), sorted(reference["buy_assets"]), case_id)
            self.assertGreaterEqual(output["confidence"], CONFIDENCE_GATE, case_id)


class ProbeSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_jsonl(DATA / "probes.inputs.jsonl")
        cls.references = {r["case_id"]: r for r in load_jsonl(DATA / "probes.references.jsonl")}
        cls.outputs = outputs_for(cls.inputs)

    def test_every_output_passes_the_contract(self):
        for case in self.inputs:
            self.assertEqual(output_errors(case, self.outputs[case["case_id"]]), [], case["case_id"])

    def test_no_accepted_false_buy(self):
        for case_id, reference in self.references.items():
            output = self.outputs[case_id]
            if reference["label"] != "BUY" and output["label"] == "BUY":
                self.assertLess(output["confidence"], CONFIDENCE_GATE, reference["probe_name"])

    def test_undisputed_probes_match(self):
        for case_id, reference in self.references.items():
            if "debatable" in reference["boundary_tags"]:
                continue
            output = self.outputs[case_id]
            self.assertEqual(output["label"], reference["label"], reference["probe_name"])
            self.assertEqual(sorted(b["asset_mention"] for b in output["current_buys"]), sorted(reference["buy_assets"]),
                             reference["probe_name"])


class LegacySet(unittest.TestCase):
    """The first prototype's three labelled sets, converted by scripts/import_legacy.py.

    Their labels follow the first prototype's policy, so only two properties are held
    fixed: every output is contract-valid, and no undisputed row gets an accepted false BUY.
    """

    @classmethod
    def setUpClass(cls):
        cls.inputs = load_jsonl(DATA / "legacy.inputs.jsonl")
        cls.references = {r["case_id"]: r for r in load_jsonl(DATA / "legacy.references.jsonl")}
        cls.outputs = outputs_for(cls.inputs)

    def test_every_output_passes_the_contract(self):
        for case in self.inputs:
            self.assertEqual(output_errors(case, self.outputs[case["case_id"]]), [], case["case_id"])

    def test_no_accepted_false_buy_on_undisputed_rows(self):
        for case_id, reference in self.references.items():
            output = self.outputs[case_id]
            if "debatable" in reference["boundary_tags"] or reference["label"] == "BUY" or output["label"] != "BUY":
                continue
            self.assertLess(output["confidence"], CONFIDENCE_GATE, reference["probe_name"])


class CombinedTexts(unittest.TestCase):
    """Odd shapes the datasets do not contain: two posts glued together, on one line or two."""

    def test_outputs_stay_valid(self):
        from helpers import make_case

        texts = [c["primary"]["text"] for c in load_jsonl(DATA / "probes.inputs.jsonl")
                 + load_jsonl(DATA / "holdout.inputs.jsonl")]
        for left in texts[::3]:
            for right in texts[1::4]:
                for joiner in (" ", "\n", "\n\n"):
                    case = make_case(left + joiner + right)
                    output = process_case(case)[0]
                    self.assertEqual(output_errors(case, output), [], (left[:40], right[:40]))


if __name__ == "__main__":
    unittest.main()
