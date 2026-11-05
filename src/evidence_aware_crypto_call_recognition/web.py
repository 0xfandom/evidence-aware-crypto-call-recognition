"""Local web page for reading decisions: one post, many posts, or one package case.

Usage: python3 -m evidence_aware_crypto_call_recognition.web [--port 8000]

Serves on 127.0.0.1 only, with the standard library. Pasted text is wrapped into a valid
package case (synthetic IDs, current timestamps, the rebuilt evidence catalogue) and goes
through the same path as the CLI, contract self-check included.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from evidence_aware_crypto_call_recognition import __version__
from evidence_aware_crypto_call_recognition.cli import InputFileError, parse_case, run_case
from evidence_aware_crypto_call_recognition.contract import text_sha256
from evidence_aware_crypto_call_recognition.evaluate import compare
from evidence_aware_crypto_call_recognition.integrity import expected_catalogue

PAGE = Path(__file__).with_name("web") / "index.html"
ROOT = Path(__file__).resolve().parents[2]
SETS = {
    "development": ROOT / "candidate_package" / "development",
    "probes": ROOT / "data" / "probes",
    "holdout": ROOT / "data" / "holdout",
    "legacy": ROOT / "data" / "legacy",
}
MAX_BODY = 4_000_000


def _hex(seed: str, length: int) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:length]


def _utc(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def case_from_post(text: str, context: list[dict], fragment: bool, image: bool) -> dict:
    """A valid package case around pasted text. Context items are {"text", "same_author"}, oldest last."""
    seed = json.dumps([text, context, fragment, image])
    now = datetime.now(timezone.utc).replace(microsecond=0)
    author = f"sim_author_{_hex('author:' + seed, 12)}"
    primary = {"source_id": f"sim_post_{_hex('primary:' + seed, 12)}p", "author_id": author,
               "published_at_utc": _utc(now - timedelta(minutes=1)), "text": text, "text_sha256": text_sha256(text),
               "capture_scope": "FRAGMENT" if fragment else "FULL_TEXT"}
    sources = []
    for index, item in enumerate(context):
        sources.append({"source_id": f"sim_post_{_hex(f'context:{index}:' + seed, 12)}q",
                        "author_id": author if item["same_author"] else f"sim_author_{_hex(f'other:{index}:' + seed, 12)}",
                        "published_at_utc": _utc(now - timedelta(minutes=2 + index)), "text": item["text"],
                        "text_sha256": text_sha256(item["text"]), "capture_scope": "FULL_TEXT"})
    unavailable = []
    if fragment:
        unavailable.append({"kind": "MISSING_PREFIX", "reference": "https://example.invalid/prefix"})
    if image:
        unavailable.append({"kind": "IMAGE", "reference": "https://example.invalid/image"})
    case = {"case_id": f"dev-{_hex('case:' + seed, 10)}", "synthetic": True, "available_at_utc": _utc(now),
            "primary": primary, "context": sources, "unavailable_context": unavailable,
            "asset_identity_evidence": [], "evidence_catalogue": []}
    case["evidence_catalogue"] = expected_catalogue(case)
    return case


def decide_case(case: dict) -> dict:
    started = time.perf_counter()
    output, trace, problems = run_case(case)
    return {"case": case, "output": output, "trace": trace, "self_check": problems,
            "ms": round((time.perf_counter() - started) * 1000, 2)}


def _set_file(name: str, kind: str) -> Path:
    base = SETS[name]
    return base.with_name(f"{base.name}.{kind}.jsonl")


def available_sets() -> list[str]:
    return [name for name in SETS if _set_file(name, "inputs").exists()]


def run_batch(inputs_text: str, set_name: str | None) -> dict:
    """Decide every case in JSONL text; compare with the named set's references where its case IDs match."""
    cases = []
    for number, line in enumerate(inputs_text.splitlines(), 1):
        if line.strip():
            try:
                cases.append(parse_case(line))
            except InputFileError as error:
                raise InputFileError(f"line {number}: {error}") from error
    if not cases:
        raise ValueError("no cases to classify")
    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case IDs cannot be bound to results")
    started = time.perf_counter()
    results = [decide_case(case) for case in cases]
    response = {"results": results, "ms_per_case": round((time.perf_counter() - started) * 1000 / len(cases), 2)}
    if set_name:
        lines = _set_file(set_name, "references").read_text(encoding="utf-8").splitlines()
        references = {r["case_id"]: r for r in map(json.loads, filter(str.strip, lines)) if r["case_id"] in set(ids)}
        if references:
            outputs = {r["output"]["case_id"]: r["output"] for r in results}
            response.update(compare({c["case_id"]: c for c in cases}, references, outputs))
    return response


class Handler(BaseHTTPRequestHandler):
    server_version = "eacr"

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/":
            self._send(HTTPStatus.OK, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/api/health":
            self._json({"version": __version__, "reader": "rules", "sets": available_sets()})
        elif url.path == "/api/set":
            name = parse_qs(url.query).get("name", [""])[0]
            if name not in available_sets():
                self._json({"error": "unknown dataset"}, HTTPStatus.NOT_FOUND)
                return
            self._json({"name": name, "inputs": _set_file(name, "inputs").read_text(encoding="utf-8")})
        else:
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._json({"error": f"request larger than {MAX_BODY} bytes"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        path = urlsplit(self.path).path
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/post":
                text = body["text"]
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("the post text is empty")
                context = [{"text": c["text"], "same_author": bool(c["same_author"])} for c in body.get("context", [])
                           if isinstance(c.get("text"), str) and c["text"].strip()]
                self._json(decide_case(case_from_post(text, context, bool(body.get("fragment")), bool(body.get("image")))))
            elif path == "/api/case":
                self._json(decide_case(parse_case(body["case_json"])))
            elif path == "/api/batch":
                set_name = body.get("set")
                if set_name is not None and set_name not in available_sets():
                    raise ValueError("unknown dataset")
                self._json(run_batch(body["inputs"], set_name))
            else:
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except (InputFileError, ValueError, KeyError, TypeError, AttributeError) as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eacr-web", description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"eacr: serving on http://127.0.0.1:{args.port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
