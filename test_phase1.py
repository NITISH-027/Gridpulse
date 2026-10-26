#!/usr/bin/env python3
"""
Offline Mocked Test Suite for GridPulse Phase 1
Tests configuration loading, contract headers, payload envelopes,
strict response validation, CSV parsing, fail-fast behavior, and safe logging.
No network calls are made.
"""

import io
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import requests

from quickml_smoke_test import (
    load_config,
    build_headers,
    build_single_row_payload,
    validate_quickml_response,
    execute_smoke_test,
)
from quickml_batch_probe import (
    load_and_validate_csv,
    run_sequential_check,
)

DUMMY_URL = "https://api.catalyst.zoho.in/quickml/v1/project/12345/endpoints/predict"
DUMMY_KEY = "dummy-endpoint-key-abcdef123456"
DUMMY_TOKEN = "dummy_token_xyz"
DUMMY_ORG = "00000000000"
DUMMY_ENV = "Development"

class TestPhase1Offline(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for dummy .env and test CSVs
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = os.path.join(self.temp_dir.name, ".env")
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.write(f"QUICKML_ENDPOINT_URL={DUMMY_URL}\n")
            f.write(f"QUICKML_ENDPOINT_KEY={DUMMY_KEY}\n")
            f.write(f"QUICKML_AUTH_TOKEN={DUMMY_TOKEN}\n")
            f.write(f"CATALYST_ORG_ID={DUMMY_ORG}\n")
            f.write(f"ENVIRONMENT={DUMMY_ENV}\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    # --------------------------------------------------------------------------
    # 1. Configuration & Headers Tests
    # --------------------------------------------------------------------------
    def test_load_config_success(self):
        config = load_config(self.env_path)
        self.assertEqual(config["QUICKML_ENDPOINT_URL"], DUMMY_URL)
        self.assertEqual(config["QUICKML_ENDPOINT_KEY"], DUMMY_KEY)
        self.assertEqual(config["QUICKML_AUTH_TOKEN"], DUMMY_TOKEN)
        self.assertEqual(config["CATALYST_ORG_ID"], DUMMY_ORG)
        self.assertEqual(config["ENVIRONMENT"], DUMMY_ENV)

    def test_load_config_missing_variable(self):
        # Create .env with missing token
        bad_env = os.path.join(self.temp_dir.name, ".bad_env")
        with open(bad_env, "w", encoding="utf-8") as f:
            f.write(f"QUICKML_ENDPOINT_URL={DUMMY_URL}\n")
            f.write(f"QUICKML_ENDPOINT_KEY={DUMMY_KEY}\n")
            # QUICKML_AUTH_TOKEN is missing
            f.write(f"CATALYST_ORG_ID={DUMMY_ORG}\n")
            f.write(f"ENVIRONMENT={DUMMY_ENV}\n")

        # Clear process env to avoid fallback to host environment
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                load_config(bad_env)
            self.assertIn("QUICKML_AUTH_TOKEN", str(ctx.exception))

    def test_build_headers_prepends_token_exactly_once(self):
        config = {
            "QUICKML_ENDPOINT_URL": DUMMY_URL,
            "QUICKML_ENDPOINT_KEY": DUMMY_KEY,
            "QUICKML_AUTH_TOKEN": DUMMY_TOKEN,
            "CATALYST_ORG_ID": DUMMY_ORG,
            "ENVIRONMENT": DUMMY_ENV,
        }
        headers = build_headers(config)
        self.assertEqual(headers["Authorization"], f"Zoho-oauthtoken {DUMMY_TOKEN}")
        self.assertEqual(headers["X-QUICKML-ENDPOINT-KEY"], DUMMY_KEY)
        self.assertEqual(headers["CATALYST-ORG"], DUMMY_ORG)
        self.assertEqual(headers["Environment"], DUMMY_ENV)

        # Prepending test when token already had "Zoho-oauthtoken " prefix in .env
        config_with_prefix = dict(config)
        config_with_prefix["QUICKML_AUTH_TOKEN"] = f"Zoho-oauthtoken {DUMMY_TOKEN}"
        headers_prefix = build_headers(config_with_prefix)
        self.assertEqual(headers_prefix["Authorization"], f"Zoho-oauthtoken {DUMMY_TOKEN}")

    def test_single_row_payload_envelope(self):
        payload = build_single_row_payload()
        self.assertIn("data", payload)
        data = payload["data"]
        self.assertIn("timestamp", data)
        self.assertIn("ambient_temp_c", data)
        self.assertIn("humidity_pct", data)
        self.assertIn("solar_irradiance_wm2", data)

    # --------------------------------------------------------------------------
    # 2. Strict Response Validation Tests
    # --------------------------------------------------------------------------
    def test_validate_response_success(self):
        # Valid response matching verified console example
        resp_json = json.dumps({"result": [100.99989092123273]})
        valid, count, msg = validate_quickml_response(200, resp_json)
        self.assertTrue(valid)
        self.assertEqual(count, 1)

    def test_validate_response_integer_success(self):
        resp_json = json.dumps({"result": [42]})
        valid, count, msg = validate_quickml_response(200, resp_json)
        self.assertTrue(valid)
        self.assertEqual(count, 1)

    def test_validate_response_non_200(self):
        for status in [400, 401, 403, 429, 500, 502]:
            valid, count, msg = validate_quickml_response(status, json.dumps({"result": [100.0]}))
            self.assertFalse(valid)
            self.assertIn(f"Status {status}", msg)

    def test_validate_response_non_json(self):
        valid, count, msg = validate_quickml_response(200, "<html>Bad Gateway</html>")
        self.assertFalse(valid)
        self.assertIn("not valid JSON", msg)

    def test_validate_response_not_an_object(self):
        valid, count, msg = validate_quickml_response(200, json.dumps([100.0]))
        self.assertFalse(valid)
        self.assertIn("not an object", msg)

    def test_validate_response_missing_result_key(self):
        valid, count, msg = validate_quickml_response(200, json.dumps({"predictions": [100.0]}))
        self.assertFalse(valid)
        self.assertIn("Missing required key 'result'", msg)

    def test_validate_response_result_not_a_list(self):
        valid, count, msg = validate_quickml_response(200, json.dumps({"result": 100.0}))
        self.assertFalse(valid)
        self.assertIn("not a list", msg)

    def test_validate_response_empty_result_list(self):
        valid, count, msg = validate_quickml_response(200, json.dumps({"result": []}))
        self.assertFalse(valid)
        self.assertEqual(count, 0)
        self.assertIn("exactly 1 prediction", msg)

    def test_validate_response_multiple_predictions(self):
        valid, count, msg = validate_quickml_response(200, json.dumps({"result": [10.0, 20.0]}))
        self.assertFalse(valid)
        self.assertEqual(count, 2)
        self.assertIn("exactly 1 prediction", msg)

    def test_validate_response_rejects_boolean(self):
        valid, count, msg = validate_quickml_response(200, json.dumps({"result": [True]}))
        self.assertFalse(valid)
        self.assertIn("boolean", msg)

    def test_validate_response_rejects_string(self):
        valid, count, msg = validate_quickml_response(200, json.dumps({"result": ["100.0"]}))
        self.assertFalse(valid)
        self.assertIn("non-numeric", msg)

    def test_validate_response_rejects_null(self):
        valid, count, msg = validate_quickml_response(200, json.dumps({"result": [None]}))
        self.assertFalse(valid)
        self.assertIn("non-numeric", msg)

    def test_validate_response_rejects_nan_and_inf(self):
        # Python json can serialize nan / inf
        valid, count, msg = validate_quickml_response(200, '{"result": [NaN]}')
        self.assertFalse(valid)
        self.assertIn("non-finite", msg)

        valid, count, msg = validate_quickml_response(200, '{"result": [Infinity]}')
        self.assertFalse(valid)
        self.assertIn("non-finite", msg)

    # --------------------------------------------------------------------------
    # 3. CSV Parsing & Validation Tests
    # --------------------------------------------------------------------------
    def _create_sample_csv(self, filename: str, rows_data: list, header: list = None):
        if header is None:
            header = ["timestamp", "ambient_temp_c", "humidity_pct", "solar_irradiance_wm2"]
        path = os.path.join(self.temp_dir.name, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(",".join(header) + "\n")
            for r in rows_data:
                f.write(",".join(str(x) for x in r) + "\n")
        return path

    def test_csv_validation_success(self):
        valid_rows = [["2026-10-24 00:00:00", 25.0, 60.0, 100.0] for _ in range(24)]
        csv_file = self._create_sample_csv("valid.csv", valid_rows)
        parsed = load_and_validate_csv(csv_file, count=24)
        self.assertEqual(len(parsed), 24)
        self.assertEqual(parsed[0]["ambient_temp_c"], 25.0)

    def test_csv_missing_file(self):
        with self.assertRaises(ValueError) as ctx:
            load_and_validate_csv("non_existent_file.csv", count=24)
        self.assertIn("Input CSV file not found", str(ctx.exception))

    def test_csv_missing_columns(self):
        bad_header = ["timestamp", "ambient_temp_c", "humidity_pct"]  # missing solar_irradiance_wm2
        csv_file = self._create_sample_csv("bad_header.csv", [[1, 2, 3]], header=bad_header)
        with self.assertRaises(ValueError) as ctx:
            load_and_validate_csv(csv_file, count=24)
        self.assertIn("missing required columns", str(ctx.exception).lower())

    def test_csv_insufficient_rows(self):
        short_rows = [["2026-10-24 00:00:00", 25.0, 60.0, 100.0] for _ in range(10)]
        csv_file = self._create_sample_csv("short.csv", short_rows)
        with self.assertRaises(ValueError) as ctx:
            load_and_validate_csv(csv_file, count=24)
        self.assertIn("Insufficient rows in CSV: required 24, found 10", str(ctx.exception))

    def test_csv_malformed_numeric_field(self):
        rows = [["2026-10-24 00:00:00", 25.0, 60.0, 100.0] for _ in range(24)]
        rows[4][1] = "INVALID_TEMP"  # Row 5 in 1-based indexing
        csv_file = self._create_sample_csv("malformed.csv", rows)
        with self.assertRaises(ValueError) as ctx:
            load_and_validate_csv(csv_file, count=24)
        self.assertIn("Row 5: field 'ambient_temp_c' is not a valid finite number", str(ctx.exception))
        # Ensure raw value is not dumped
        self.assertNotIn("INVALID_TEMP", str(ctx.exception))

    def test_csv_missing_timestamp(self):
        rows = [["2026-10-24 00:00:00", 25.0, 60.0, 100.0] for _ in range(24)]
        rows[2][0] = ""  # Row 3 in 1-based indexing
        csv_file = self._create_sample_csv("empty_ts.csv", rows)
        with self.assertRaises(ValueError) as ctx:
            load_and_validate_csv(csv_file, count=24)
        self.assertIn("Row 3: field 'timestamp' is missing or empty", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 4. Mocked Execution & Safe Logging Tests
    # --------------------------------------------------------------------------
    @patch("requests.post")
    def test_smoke_test_mocked_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"result": [100.99989092123273]})
        mock_post.return_value = mock_response

        captured_stdout = io.StringIO()
        with patch("sys.stdout", captured_stdout):
            exit_code = execute_smoke_test(self.env_path)

        self.assertEqual(exit_code, 0)
        output = captured_stdout.getvalue()
        self.assertIn("HTTP Status: 200", output)
        self.assertIn("Prediction Count: 1", output)
        self.assertIn("Validation Outcome: PASS", output)

        # Safe logging checks: verify credentials, full URLs, and raw payloads are NEVER printed
        self.assertNotIn(DUMMY_KEY, output)
        self.assertNotIn(DUMMY_TOKEN, output)
        self.assertNotIn(DUMMY_URL, output)
        self.assertNotIn("100.99989092123273", output)

    @patch("requests.post")
    def test_smoke_test_mocked_non_200(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"error": "Unauthorized"}'
        mock_post.return_value = mock_response

        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        with patch("sys.stdout", captured_stdout), patch("sys.stderr", captured_stderr):
            exit_code = execute_smoke_test(self.env_path)

        self.assertEqual(exit_code, 1)
        err_output = captured_stderr.getvalue()
        self.assertIn("Status 401", err_output)
        self.assertNotIn("Unauthorized", err_output)  # Raw body is suppressed

    @patch("requests.post")
    def test_sequential_check_circuit_breaker(self, mock_post):
        valid_rows = [["2026-10-24 00:00:00", 25.0, 60.0, 100.0] for _ in range(24)]
        csv_file = self._create_sample_csv("seq_test.csv", valid_rows)

        # Mock responses: 1st and 2nd succeed, 3rd fails with 429
        resp_success = MagicMock(status_code=200, text=json.dumps({"result": [50.0]}))
        resp_429 = MagicMock(status_code=429, text='{"error": "Rate limit exceeded"}')

        mock_post.side_effect = [resp_success, resp_success, resp_429]

        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        with patch("sys.stdout", captured_stdout), patch("sys.stderr", captured_stderr):
            exit_code = run_sequential_check(csv_path=csv_file, env_path=self.env_path)

        self.assertEqual(exit_code, 1)
        # Exactly 3 network calls should have been made before the circuit breaker tripped
        self.assertEqual(mock_post.call_count, 3)
        self.assertIn("CIRCUIT BREAKER", captured_stderr.getvalue())

    # --------------------------------------------------------------------------
    # 5. Git & Security Ignore Check
    # --------------------------------------------------------------------------
    def test_env_is_ignored_by_git(self):
        result = subprocess.run(
            ["git", "check-ignore", "-v", ".env"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, ".env is not properly ignored by .gitignore!")
        self.assertIn(".env", result.stdout)

if __name__ == "__main__":
    unittest.main()
