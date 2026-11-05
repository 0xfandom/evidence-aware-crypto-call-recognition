#!/bin/sh
# Predict and compare on the development set, the two probe sets and the legacy set.
# Usage: scripts/run_sets.sh [PYTHON]   (PYTHON must be 3.10 or newer)
set -eu
cd "$(dirname "$0")/.."
PYTHON="${1:-python3}"
mkdir -p runs
for name in development probes holdout legacy; do
  if [ "$name" = development ]; then
    inputs=candidate_package/development.inputs.jsonl
    references=candidate_package/development.references.jsonl
  else
    inputs=data/$name.inputs.jsonl
    references=data/$name.references.jsonl
  fi
  PYTHONPATH=src "$PYTHON" -B -m evidence_aware_crypto_call_recognition --inputs "$inputs" --output "runs/$name.predictions.jsonl" --trace "runs/$name.trace.jsonl"
  echo "[$name]"
  PYTHONPATH=src "$PYTHON" -B -m evidence_aware_crypto_call_recognition.evaluate "$inputs" "$references" "runs/$name.predictions.jsonl" | grep -E 'BAD|fully'
done
