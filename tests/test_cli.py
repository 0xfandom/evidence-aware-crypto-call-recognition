import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import PACKAGE, make_case

from evidence_aware_crypto_call_recognition import cli


def run_cli(*args):
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        code = cli.main(list(args))
    return code, stderr.getvalue()


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_writes_one_result_per_case(self):
        output = self.tmp / "predictions.jsonl"
        code, _ = run_cli("--inputs", str(PACKAGE / "development.inputs.jsonl"), "--output", str(output))
        self.assertEqual(code, 0)
        rows = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(len(rows), 24)
        self.assertEqual(len({r["case_id"] for r in rows}), 24)

    def test_duplicate_case_ids_are_not_aligned(self):
        line = json.dumps(make_case("I am starting $AAAA today."))
        source = self.tmp / "in.jsonl"
        source.write_text(line + "\n" + line + "\n")
        code, err = run_cli("--inputs", str(source), "--output", str(self.tmp / "out.jsonl"))
        self.assertEqual(code, 2)
        self.assertIn("duplicate case IDs", err)
        self.assertFalse((self.tmp / "out.jsonl").exists())

    def test_malformed_json_and_nan_are_rejected(self):
        for text in ['{"case_id": "dev-0123456789",\n', '{"case_id": "dev-0123456789", "x": NaN}\n',
                     '{"case_id": "a", "case_id": "b"}\n']:
            source = self.tmp / "in.jsonl"
            source.write_text(text)
            code, _ = run_cli("--inputs", str(source), "--output", str(self.tmp / "out.jsonl"))
            self.assertEqual(code, 2, text)

    def test_reader_failure_is_reported_without_a_label(self):
        source = self.tmp / "in.jsonl"
        source.write_text(json.dumps(make_case("I am starting $AAAA today.")) + "\n")
        output = self.tmp / "out.jsonl"
        with mock.patch.object(cli, "decide", side_effect=RuntimeError("boom")):
            code, err = run_cli("--inputs", str(source), "--output", str(output))
        self.assertEqual(code, 0)
        row = json.loads(output.read_text())
        self.assertEqual(row["status"], "CAPACITY_LIMIT")
        self.assertEqual(row["error_codes"], ["PROCESSING_FAILURE"])
        self.assertIn("RuntimeError", err)


if __name__ == "__main__":
    unittest.main()
