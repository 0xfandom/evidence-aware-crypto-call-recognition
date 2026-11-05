import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import helpers  # noqa: F401  (puts src on the path)

from evidence_aware_crypto_call_recognition.integrity import input_errors
from evidence_aware_crypto_call_recognition.web import Handler, case_from_post


class CaseBuilder(unittest.TestCase):
    def test_pasted_text_becomes_a_valid_package_case(self):
        case = case_from_post("I am starting $AAAA today.", [{"text": "Earlier note on $BBBB.", "same_author": True}],
                              fragment=True, image=True)
        self.assertEqual(input_errors(case), [])
        self.assertEqual(case["context"][0]["author_id"], case["primary"]["author_id"])
        self.assertEqual({item["kind"] for item in case["unavailable_context"]}, {"MISSING_PREFIX", "IMAGE"})


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def test_page_is_served(self):
        for path in ("/", "/?example=joke&mode=case"):
            status, body = self.call(path)
            self.assertEqual(status, 200, path)
            self.assertIn(b"Evidence-Aware Crypto Call Recognition", body)

    def test_post_is_decided_and_self_checked(self):
        status, body = self.call("/api/post", {"text": "I am starting $AAAA today.", "context": []})
        result = json.loads(body)
        self.assertEqual((status, result["output"]["label"], result["self_check"]), (200, "BUY", []))

    def test_tampered_case_is_rejected_before_reading(self):
        case = case_from_post("I am starting $AAAA today.", [], fragment=False, image=False)
        case["primary"]["text"] = "I am starting $BBBB today."
        status, body = self.call("/api/case", {"case_json": json.dumps(case)})
        output = json.loads(body)["output"]
        self.assertEqual((status, output["status"]), (200, "INPUT_INVALID"))
        self.assertIn("TEXT_HASH_MISMATCH", output["error_codes"])

    def test_duplicate_field_in_a_case_is_a_bad_request(self):
        status, _ = self.call("/api/case", {"case_json": '{"case_id": "dev-0123456789", "case_id": "dev-0123456789"}'})
        self.assertEqual(status, 400)

    def test_health_lists_the_datasets(self):
        status, body = self.call("/api/health")
        health = json.loads(body)
        self.assertEqual(status, 200)
        self.assertIn("development", health["sets"])

    def test_development_set_runs_with_the_comparison(self):
        inputs = json.loads(self.call("/api/set?name=development")[1])["inputs"]
        status, body = self.call("/api/batch", {"inputs": inputs, "set": "development"})
        result = json.loads(body)
        summary = result["summary"]
        self.assertEqual((status, len(result["results"])), (200, 24))
        self.assertEqual((summary["cases"], summary["correct"], summary["accepted_false_buys"]), (24, 24, 0))

    def test_pasted_cases_run_without_references(self):
        lines = json.loads(self.call("/api/set?name=development")[1])["inputs"].splitlines()[:3]
        status, body = self.call("/api/batch", {"inputs": "\n".join(lines), "set": None})
        result = json.loads(body)
        self.assertEqual((status, len(result["results"]), "summary" in result), (200, 3, False))

    def test_bad_batch_lines_are_named(self):
        status, body = self.call("/api/batch", {"inputs": '{"case_id": "dev-0123456789"}\nnot json', "set": None})
        self.assertEqual(status, 400)
        self.assertIn("line 2", json.loads(body)["error"])

    def test_unknown_routes_and_sets(self):
        self.assertEqual(self.call("/api/batch", {"inputs": "x", "set": "../secrets"})[0], 400)
        self.assertEqual(self.call("/api/set?name=../secrets")[0], 404)
        self.assertEqual(self.call("/nothing")[0], 404)
