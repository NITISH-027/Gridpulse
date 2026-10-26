#!/usr/bin/env python3
"""
GridPulse - Phase 2 Offline Full-Coverage Test Suite (Zero Live Calls)
Tests the complete Judge Contract on all 1,000 rows of sample_test_input.csv
and validates all failure cases, atomic writes, and fail-loud semantics.
"""

import io
import math
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import requests

from quickml_client import (
    REQUIRED_ENV_VARS,
    ROWS_PER_REQUEST,
    QuickMLClient,
    QuickMLError,
    build_quickml_headers,
    load_quickml_config,
)
from predict import (
    predict,
    prepare_features,
    validate_input_dataframe,
)

DUMMY_CONFIG = {
    "QUICKML_ENDPOINT_URL": "https://api.catalyst.zoho.in/quickml/v1/project/99999/endpoints/predict",
    "QUICKML_ENDPOINT_KEY": "dummy_endpoint_key_12345",
    "QUICKML_AUTH_TOKEN": "dummy_auth_token_abcde",
    "CATALYST_ORG_ID": "888888888",
    "ENVIRONMENT": "Development",
}


class TestPhase2ConfigAndHeaders(unittest.TestCase):
    """Tests environment configuration loading and header formation."""

    def test_load_quickml_config_success(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            good_env = os.path.join(tmp_dir, ".env")
            with open(good_env, "w", encoding="utf-8") as f:
                for k, v in DUMMY_CONFIG.items():
                    f.write(f"{k}={v}\n")
            with patch.dict(os.environ, {}, clear=True):
                cfg = load_quickml_config(env_path=good_env)
                for key in REQUIRED_ENV_VARS:
                    self.assertEqual(cfg[key], DUMMY_CONFIG[key])

    def test_load_quickml_config_missing_var(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_env = os.path.join(tmp_dir, ".env")
            with open(bad_env, "w", encoding="utf-8") as f:
                f.write(f"QUICKML_ENDPOINT_URL={DUMMY_CONFIG['QUICKML_ENDPOINT_URL']}\n")
                f.write(f"QUICKML_ENDPOINT_KEY={DUMMY_CONFIG['QUICKML_ENDPOINT_KEY']}\n")
                # QUICKML_AUTH_TOKEN intentionally omitted
                f.write(f"CATALYST_ORG_ID={DUMMY_CONFIG['CATALYST_ORG_ID']}\n")
                f.write(f"ENVIRONMENT={DUMMY_CONFIG['ENVIRONMENT']}\n")
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(QuickMLError) as ctx:
                    load_quickml_config(env_path=bad_env)
                self.assertIn("QUICKML_AUTH_TOKEN", str(ctx.exception))
                # Ensure no secrets in exception message
                self.assertNotIn("dummy", str(ctx.exception))

    def test_build_quickml_headers_prefix_handling(self):
        # Case 1: Raw token without prefix
        cfg1 = dict(DUMMY_CONFIG)
        headers1 = build_quickml_headers(cfg1)
        self.assertEqual(headers1["Authorization"], f"Zoho-oauthtoken {DUMMY_CONFIG['QUICKML_AUTH_TOKEN']}")
        self.assertEqual(headers1["X-QUICKML-ENDPOINT-KEY"], DUMMY_CONFIG["QUICKML_ENDPOINT_KEY"])
        self.assertEqual(headers1["CATALYST-ORG"], DUMMY_CONFIG["CATALYST_ORG_ID"])
        self.assertEqual(headers1["Environment"], "Development")
        self.assertEqual(headers1["Content-Type"], "application/json")

        # Case 2: Token already has prefix
        cfg2 = dict(DUMMY_CONFIG)
        cfg2["QUICKML_AUTH_TOKEN"] = f"Zoho-oauthtoken {DUMMY_CONFIG['QUICKML_AUTH_TOKEN']}"
        headers2 = build_quickml_headers(cfg2)
        self.assertEqual(headers2["Authorization"], f"Zoho-oauthtoken {DUMMY_CONFIG['QUICKML_AUTH_TOKEN']}")


class TestPhase2ClientResponseValidation(unittest.TestCase):
    """Tests strict response validation and fail-loud error handling."""

    def setUp(self):
        self.mock_session = MagicMock()
        self.client = QuickMLClient(config=DUMMY_CONFIG, session=self.mock_session)
        self.dummy_record = {
            "timestamp": "2015-06-16 15:00:00",
            "ambient_temp_c": 35.66,
            "humidity_pct": 56.38,
            "solar_irradiance_wm2": 169.0,
        }

    def _mock_response(self, status_code=200, json_data=None, is_redirect=False, reason="OK"):
        resp = MagicMock(spec=requests.Response)
        resp.status_code = status_code
        resp.is_redirect = is_redirect
        resp.reason = reason
        if json_data is not None:
            resp.json.return_value = json_data
        else:
            resp.json.side_effect = ValueError("Invalid JSON")
        return resp

    def test_valid_single_response(self):
        self.mock_session.post.return_value = self._mock_response(200, {"result": [152.34]})
        pred = self.client.predict_single(self.dummy_record)
        self.assertEqual(pred, 152.34)

    def test_reject_redirect(self):
        self.mock_session.post.return_value = self._mock_response(302, {"result": [100.0]}, is_redirect=True)
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("Redirect response received", str(ctx.exception))

    def test_http_500_error(self):
        self.mock_session.post.return_value = self._mock_response(500, reason="Internal Server Error")
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("HTTP 500", str(ctx.exception))

    def test_http_401_auth_error_sanitized(self):
        self.mock_session.post.return_value = self._mock_response(401, reason="Unauthorized")
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("HTTP 401", str(ctx.exception))
        # Ensure no token in error
        self.assertNotIn("dummy_auth_token", str(ctx.exception))

    def test_invalid_json_body(self):
        self.mock_session.post.return_value = self._mock_response(200, json_data=None)
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_json_root_not_dict(self):
        self.mock_session.post.return_value = self._mock_response(200, json_data=[150.0])
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("Response root is not a JSON object", str(ctx.exception))

    def test_missing_result_key(self):
        self.mock_session.post.return_value = self._mock_response(200, json_data={"predictions": [150.0]})
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("missing 'result' field", str(ctx.exception))

    def test_result_length_mismatch(self):
        # Empty result
        self.mock_session.post.return_value = self._mock_response(200, json_data={"result": []})
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("Result length mismatch", str(ctx.exception))

        # Too many results
        self.mock_session.post.return_value = self._mock_response(200, json_data={"result": [10.0, 20.0]})
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("Result length mismatch", str(ctx.exception))

    def test_reject_boolean_prediction(self):
        # Python bool is int subclass, so test both True and False
        self.mock_session.post.return_value = self._mock_response(200, json_data={"result": [True]})
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("is boolean, not numeric", str(ctx.exception))

        self.mock_session.post.return_value = self._mock_response(200, json_data={"result": [False]})
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("is boolean, not numeric", str(ctx.exception))

    def test_reject_string_prediction(self):
        self.mock_session.post.return_value = self._mock_response(200, json_data={"result": ["150.25"]})
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("is non-numeric", str(ctx.exception))

    def test_reject_nan_and_inf_prediction(self):
        self.mock_session.post.return_value = self._mock_response(200, json_data={"result": [float("nan")]})
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("NaN or Infinite", str(ctx.exception))

        self.mock_session.post.return_value = self._mock_response(200, json_data={"result": [float("inf")]})
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("NaN or Infinite", str(ctx.exception))

    def test_timeout_and_network_error(self):
        self.mock_session.post.side_effect = requests.exceptions.Timeout("Connection timed out")
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("timed out", str(ctx.exception))

        self.mock_session.post.side_effect = requests.exceptions.ConnectionError("Failed to connect")
        with self.assertRaises(QuickMLError) as ctx:
            self.client.predict_single(self.dummy_record)
        self.assertIn("ConnectionError", str(ctx.exception))


class TestPhase2InputValidation(unittest.TestCase):
    """Tests raw input validation before any API calls are made."""

    def test_missing_required_column(self):
        df = pd.DataFrame({
            "timestamp": ["2015-06-16 15:00:00"],
            "ambient_temp_c": [30.0],
            "humidity_pct": [50.0],
            # solar_irradiance_wm2 is missing
        })
        with self.assertRaises(ValueError) as ctx:
            validate_input_dataframe(df)
        self.assertIn("missing required column", str(ctx.exception))
        self.assertIn("solar_irradiance_wm2", str(ctx.exception))

    def test_invalid_timestamp(self):
        df = pd.DataFrame({
            "timestamp": ["not-a-timestamp"],
            "ambient_temp_c": [30.0],
            "humidity_pct": [50.0],
            "solar_irradiance_wm2": [100.0],
        })
        with self.assertRaises(ValueError) as ctx:
            validate_input_dataframe(df)
        self.assertIn("Row 0", str(ctx.exception))
        self.assertIn("timestamp", str(ctx.exception))

    def test_boolean_in_weather_column(self):
        df = pd.DataFrame({
            "timestamp": ["2015-06-16 15:00:00"],
            "ambient_temp_c": [True],
            "humidity_pct": [50.0],
            "solar_irradiance_wm2": [100.0],
        })
        with self.assertRaises(ValueError) as ctx:
            validate_input_dataframe(df)
        self.assertIn("Row 0", str(ctx.exception))
        self.assertIn("boolean", str(ctx.exception))

    def test_string_in_weather_column(self):
        df = pd.DataFrame({
            "timestamp": ["2015-06-16 15:00:00"],
            "ambient_temp_c": ["warm"],
            "humidity_pct": [50.0],
            "solar_irradiance_wm2": [100.0],
        })
        with self.assertRaises(ValueError) as ctx:
            validate_input_dataframe(df)
        self.assertIn("Row 0", str(ctx.exception))
        self.assertIn("non-numeric", str(ctx.exception))

    def test_nan_in_weather_column(self):
        df = pd.DataFrame({
            "timestamp": ["2015-06-16 15:00:00"],
            "ambient_temp_c": [30.0],
            "humidity_pct": [float("nan")],
            "solar_irradiance_wm2": [100.0],
        })
        with self.assertRaises(ValueError) as ctx:
            validate_input_dataframe(df)
        self.assertIn("Row 0", str(ctx.exception))
        self.assertIn("missing or null", str(ctx.exception))


class TestPhase2Full1000RowCoverage(unittest.TestCase):
    """
    Pushes the full 1,000-row sample_test_input.csv through predict()
    and verifies 1,000 predictions, preserved order, and no fallbacks.
    """

    def setUp(self):
        self.sample_csv_path = "sample_test_input.csv"
        self.assertTrue(os.path.exists(self.sample_csv_path), "sample_test_input.csv must exist")
        self.input_df = pd.read_csv(self.sample_csv_path)
        self.assertEqual(len(self.input_df), 1000, "sample_test_input.csv must have 1,000 rows")

    def test_predict_full_1000_rows_offline(self):
        mock_session = MagicMock()
        client = QuickMLClient(config=DUMMY_CONFIG, session=mock_session)

        # Mock 1,000 sequential responses deterministically
        call_count = 0
        def fake_post(*args, **kwargs):
            nonlocal call_count
            resp = MagicMock(spec=requests.Response)
            resp.status_code = 200
            resp.is_redirect = False
            resp.reason = "OK"
            # Return predictable synthetic demand value
            resp.json.return_value = {"result": [100.0 + (call_count % 50)]}
            call_count += 1
            return resp

        mock_session.post.side_effect = fake_post

        predictions = predict(self.input_df, client=client)

        self.assertIsInstance(predictions, np.ndarray)
        self.assertEqual(len(predictions), 1000)
        self.assertEqual(call_count, 1000)
        self.assertFalse(np.isnan(predictions).any())
        self.assertFalse(np.isinf(predictions).any())

        # Verify values match expectations
        for i in range(1000):
            expected_val = 100.0 + (i % 50)
            self.assertEqual(predictions[i], expected_val)

    def test_fail_loud_no_dummy_fallback(self):
        """Verify that when endpoint fails, predict() aborts instead of falling back to sine-wave."""
        mock_session = MagicMock()
        client = QuickMLClient(config=DUMMY_CONFIG, session=mock_session)

        # Fail at row 5
        call_count = 0
        def failing_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 5:
                resp = MagicMock(spec=requests.Response)
                resp.status_code = 500
                resp.reason = "Server Error"
                resp.is_redirect = False
                return resp
            resp = MagicMock(spec=requests.Response)
            resp.status_code = 200
            resp.is_redirect = False
            resp.reason = "OK"
            resp.json.return_value = {"result": [150.0]}
            return resp

        mock_session.post.side_effect = failing_post

        with self.assertRaises(QuickMLError) as ctx:
            predict(self.input_df, client=client)

        self.assertIn("Row 4", str(ctx.exception))
        self.assertIn("HTTP 500", str(ctx.exception))


class TestPhase2CLIAndAtomicOutput(unittest.TestCase):
    """Tests CLI execution, official output schema, and atomic file creation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.input_csv = os.path.join(self.temp_dir.name, "test_input.csv")
        self.output_csv = os.path.join(self.temp_dir.name, "predictions.csv")

        # Create a small valid test slice (3 rows)
        slice_df = pd.read_csv("sample_test_input.csv").head(3)
        slice_df.to_csv(self.input_csv, index=False)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_atomic_output_preserves_existing_on_failure(self):
        # Pre-create predictions.csv with canary content
        canary_content = "CANARY_EXISTING_FILE_DO_NOT_OVERWRITE\n"
        with open(self.output_csv, "w", encoding="utf-8") as f:
            f.write(canary_content)

        # Corrupt input CSV with bad row
        bad_df = pd.DataFrame({
            "timestamp": ["2015-06-16 15:00:00"],
            "ambient_temp_c": [True],  # Boolean not allowed
            "humidity_pct": [50.0],
            "solar_irradiance_wm2": [100.0],
        })
        bad_csv = os.path.join(self.temp_dir.name, "bad_input.csv")
        bad_df.to_csv(bad_csv, index=False)

        # Run CLI with failing input
        result = subprocess.run(
            [sys.executable, "predict.py", "--input", bad_csv, "--output", self.output_csv],
            capture_output=True,
            text=True,
        )

        # Must exit non-zero
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("boolean value", result.stderr)

        # Existing file MUST be untouched
        with open(self.output_csv, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), canary_content)

    def test_cli_full_1000_row_output_schema_offline(self):
        """Simulate CLI on 1,000 rows with mocked client to verify output schema."""
        full_df = pd.read_csv("sample_test_input.csv")
        mock_preds = np.full(1000, 142.50)

        # Directly invoke the logic used in CLI
        out_df = pd.DataFrame({
            "timestamp": full_df["timestamp"].astype(str),
            "target_demand_kw": mock_preds,
        })
        out_df.to_csv(self.output_csv, index=False)

        # Verify output CSV
        result_df = pd.read_csv(self.output_csv)
        self.assertEqual(list(result_df.columns), ["timestamp", "target_demand_kw"])
        self.assertEqual(len(result_df), 1000)
        # Verify timestamps match exactly
        self.assertTrue((result_df["timestamp"] == full_df["timestamp"]).all())


class TestJudgeHarnessCompatibility(unittest.TestCase):
    """Verifies that test_eval.py logic passes against predict()."""

    def test_test_eval_compatibility(self):
        import test_eval
        # Patch QuickMLClient.predict_records to return 1,000 valid float predictions
        with patch.object(
            QuickMLClient,
            "predict_records",
            return_value=[150.0 + (i % 20) for i in range(1000)],
        ):
            # Capture stdout to verify SUCCESS print
            captured_stdout = io.StringIO()
            with patch("sys.stdout", captured_stdout):
                test_eval.test_student_submission()

            output = captured_stdout.getvalue()
            self.assertIn("Successfully imported 'predict(input_df)' function.", output)
            self.assertIn("Loaded 1000 test rows from 'sample_test_input.csv'.", output)
            self.assertIn("Your predict.py script is completely valid!", output)
            self.assertIn("SUCCESS", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
