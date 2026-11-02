from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import anyio
from dotenv import load_dotenv

from evidence_aware_crypto_call_recognition.contract import Post
from evidence_aware_crypto_call_recognition.evaluate import evaluate, load_dataset, render_markdown, write_report
from evidence_aware_crypto_call_recognition.llm import LlmSettings
from evidence_aware_crypto_call_recognition.pipeline import Backend, classify_many


def _read_posts(source: str) -> list[Post]:
    lines = (sys.stdin if source == "-" else open(source)).read().splitlines()
    posts = []
    for line in lines:
        if not line.strip():
            continue
        record = json.loads(line)
        posts.append(Post.model_validate(record["post"] if "post" in record else record))
    return posts


def _settings(args: argparse.Namespace) -> LlmSettings:
    settings = LlmSettings.from_env()
    overrides = {}
    if args.model:
        overrides["model"] = args.model
    if args.run_budget is not None:
        overrides["run_budget_usd"] = args.run_budget
    if args.no_cache:
        overrides["cache_dir"] = None
    return LlmSettings(**{**settings.__dict__, **overrides})


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="eacr", description="Evidence-Aware Crypto Call Recognition")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--backend", type=Backend, choices=list(Backend), default=Backend.RULES)
        p.add_argument("--model", help="LLM model id (default from EACR_MODEL or claude-haiku-5-5)")
        p.add_argument("--run-budget", type=float, help="Hard USD cap for LLM spend in this run")
        p.add_argument("--no-cache", action="store_true", help="Do not reuse cached LLM decisions")
        p.add_argument("--concurrency", type=int, default=4)

    classify_parser = sub.add_parser("classify", help="Classify posts from JSONL (file or - for stdin)")
    classify_parser.add_argument("input")
    add_common(classify_parser)

    eval_parser = sub.add_parser("eval", help="Evaluate against a labelled JSONL dataset")
    eval_parser.add_argument("dataset", type=Path)
    eval_parser.add_argument("--out", type=Path, default=Path("runs"),
                             help="Report folder (default: runs/, git-ignored; committed reports live in results/)")
    add_common(eval_parser)

    serve_parser = sub.add_parser("serve", help="Run the web UI and HTTP API (localhost only by default)")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    if args.command == "serve":
        import uvicorn

        sys.stdout.write(f"Evidence-Aware Crypto Call Recognition UI: http://{args.host}:{args.port}/   API docs: http://{args.host}:{args.port}/docs\n")
        uvicorn.run("evidence_aware_crypto_call_recognition.api:app", host=args.host, port=args.port)
        return 0

    settings = _settings(args)

    if args.command == "classify":
        decisions = anyio.run(classify_many, _read_posts(args.input), args.backend, settings, args.concurrency)
        for decision in decisions:
            sys.stdout.write(decision.model_dump_json() + "\n")
        return 0

    result = evaluate(load_dataset(args.dataset), args.backend, settings, args.concurrency)
    json_path, md_path = write_report(result, args.dataset, args.out)
    sys.stdout.write(render_markdown(result.report, args.dataset.name).split("## Accuracy by tag")[0])
    sys.stdout.write(f"\nFull report: {md_path}\nJSON: {json_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
