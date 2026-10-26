#!/usr/bin/env python3
"""
GridPulse - Phase 1: QuickML Smoke Test
Performs a single-row POST request against the published QuickML endpoint.
Enforces strict schema validation, fail-loud semantics, and safe credential handling.
"""

import json
import math
import os
import sys
import time
from typing import Any, Dict, Tuple
from dotenv import load_dotenv
import requests

REQUIRED_ENV_VARS = [
    "QUICKML_ENDPOINT_URL",
    "QUICKML_ENDPOINT_KEY",
    "QUICKML_AUTH_TOKEN",
    "CATALYST_ORG_ID",
    "ENVIRONMENT",
]

def load_config(env_path: str = ".env") -> Dict[str, str]:
    """
    Loads configuration from .env without overriding existing environment variables.
    Fails clearly if any required configuration is missing, naming ONLY the missing variable.
    """
    if not os.path.exists(env_path):
        raise ValueError(f"Environment file not found: {env_path}")

    # Load without override=True
    load_dotenv(dotenv_path=env_path, override=False)

    config: Dict[str, str] = {}
    for var in REQUIRED_ENV_VARS:
        val = os.getenv(var)
        if val is None or val.strip() == "":
            raise ValueError(f"Missing required configuration variable: {var}")
        config[var] = val.strip()

    return config

def build_headers(config: Dict[str, str]) -> Dict[str, str]:
    """
    Constructs the 4 required headers for Catalyst QuickML.
    Prepends 'Zoho-oauthtoken ' exactly once to the token.
    """
    raw_token = config["QUICKML_AUTH_TOKEN"]
    prefix = "Zoho-oauthtoken "
    if raw_token.startswith(prefix):
        clean_token = raw_token[len(prefix):].strip()
    else:
        clean_token = raw_token

    auth_header = f"Zoho-oauthtoken {clean_token}"

    return {
        "X-QUICKML-ENDPOINT-KEY": config["QUICKML_ENDPOINT_KEY"],
        "Authorization": auth_header,
        "CATALYST-ORG": config["CATALYST_ORG_ID"],
        "Environment": config["ENVIRONMENT"],
        "Content-Type": "application/json",
    }

def build_single_row_payload() -> Dict[str, Any]:
    """
    Returns the verified single-row envelope from the QuickML console tester.
    """
    return {
        "data": {
            "timestamp": "2015-01-25 04:00:00",
            "ambient_temp_c": 2.26,
            "humidity_pct": 88.8,
            "solar_irradiance_wm2": 0.0,
        }
    }

def validate_quickml_response(status_code: int, response_text: str) -> Tuple[bool, int, str]:
    """
    Validates QuickML response against contract:
    - HTTP 200
    - Valid JSON object
    - Key 'result' is a list containing EXACTLY ONE finite numeric prediction.
    - Rejects booleans, strings, null, NaN, infinity, missing keys, and extra items.
    Returns: (is_valid, prediction_count, sanitized_message)
    """
    if status_code != 200:
        return False, 0, f"Non-200 HTTP response received (Status {status_code})"

    try:
        data = json.loads(response_text)
    except (ValueError, TypeError):
        return False, 0, "Response body is not valid JSON"

    if not isinstance(data, dict):
        return False, 0, "Response JSON root is not an object"

    if "result" not in data:
        return False, 0, "Missing required key 'result' in response JSON"

    result_list = data["result"]
    if not isinstance(result_list, list):
        return False, 0, "'result' field in response is not a list"

    count = len(result_list)
    if count != 1:
        return False, count, f"'result' list must contain exactly 1 prediction, found {count}"

    prediction = result_list[0]

    # In Python, isinstance(True, int) is True; explicitly reject booleans
    if isinstance(prediction, bool):
        return False, count, "Prediction value is boolean; expected finite numeric prediction"

    if not isinstance(prediction, (int, float)):
        return False, count, f"Prediction value is non-numeric ({type(prediction).__name__})"

    if not math.isfinite(prediction):
        return False, count, "Prediction value is non-finite (NaN or Infinity)"

    return True, 1, "Valid finite numeric prediction returned"

def execute_smoke_test(env_path: str = ".env") -> int:
    """
    Executes smoke test, printing only sanitized status, latency, prediction count, and outcome.
    Never prints credentials, full URLs, raw responses, request headers, or unsanitized errors.
    Returns 0 on success, 1 on failure.
    """
    try:
        config = load_config(env_path)
    except ValueError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        return 1

    headers = build_headers(config)
    payload = build_single_row_payload()
    endpoint_url = config["QUICKML_ENDPOINT_URL"]

    start_time = time.perf_counter()
    try:
        response = requests.post(
            url=endpoint_url,
            headers=headers,
            json=payload,
            timeout=15.0,
            verify=True,
            allow_redirects=False,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        status_code = response.status_code
        response_text = response.text
    except requests.exceptions.Timeout:
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        print("HTTP Status: N/A")
        print(f"Latency: {latency_ms:.2f} ms")
        print("Prediction Count: 0")
        print("Validation Outcome: FAIL (Request timed out)")
        return 1
    except requests.exceptions.SSLError:
        print("HTTP Status: N/A")
        print("Latency: N/A")
        print("Prediction Count: 0")
        print("Validation Outcome: FAIL (TLS/SSL verification error)")
        return 1
    except requests.exceptions.RequestException as e:
        print("HTTP Status: N/A")
        print("Latency: N/A")
        print("Prediction Count: 0")
        print(f"Validation Outcome: FAIL (Network transport error: {type(e).__name__})")
        return 1

    is_valid, pred_count, message = validate_quickml_response(status_code, response_text)

    # Output strictly limited to required fields
    print(f"HTTP Status: {status_code}")
    print(f"Latency: {latency_ms:.2f} ms")
    print(f"Prediction Count: {pred_count}")

    if is_valid:
        print(f"Validation Outcome: PASS ({message})")
        return 0
    else:
        print(f"Validation Outcome: FAIL ({message})", file=sys.stderr)
        return 1

def main():
    sys.exit(execute_smoke_test(".env"))

if __name__ == "__main__":
    main()
