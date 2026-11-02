import io
import json
import sys

from evidence_aware_crypto_call_recognition.cli import main


def test_classify_reads_jsonl_from_stdin_and_writes_decisions(monkeypatch, capsys):
    lines = [json.dumps({"source_id": "a", "text": "Buying $SOL here."}),
             json.dumps({"post": {"source_id": "b", "text": "gm"}, "gold": {"label": "NO_NEW_BUY"}})]
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n".join(lines)))
    assert main(["classify", "-"]) == 0
    decisions = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [(d["source"]["source_id"], d["label"]) for d in decisions] == [("a", "BUY"), ("b", "NO_NEW_BUY")]
