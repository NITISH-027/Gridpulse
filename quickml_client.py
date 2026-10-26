#!/usr/bin/env python3
"""
GridPulse - Shared QuickML Client Module
Phase 2: Judge Contract Implementation

Handles authenticated HTTP communication with the Catalyst QuickML endpoint.
Enforces:
- Environment-only credential loading (names documented, values never exposed)
- Verified single-row request shape: {"data": {record}}
- Rows-per-request setting fixed at 1 (extensible only if officially verified)
- Strict response validation (HTTP 200, valid JSON, list of real finite numbers)
- Safe HTTP behavior: allow_redirects=False, 10s timeout, zero retries
- Sanitized error reporting: status code + error class, no raw bodies or tokens
"""

import math
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import requests

# ------------------------------------------------------------------------------
# Configuration Contract
# ------------------------------------------------------------------------------
REQUIRED_ENV_VARS: List[str] = [
    "QUICKML_ENDPOINT_URL",
    "QUICKML_ENDPOINT_KEY",
    "QUICKML_AUTH_TOKEN",
    "CATALYST_ORG_ID",
    "ENVIRONMENT",
]

# Rows-per-request fixed at 1 as verified in Phase 1 console and probe runs.
# If Zoho documentation or support verifies multi-row batches, this is the only setting to change.
ROWS_PER_REQUEST: int = 1

# Request timeout in seconds (strict, no retries)
REQUEST_TIMEOUT_SECONDS: float = 10.0


class QuickMLError(Exception):
    """Sanitized exception for QuickML client failures."""
    pass


def load_quickml_config(env_path: Optional[str] = None) -> Dict[str, str]:
    """
    Loads QuickML endpoint configuration from environment or specified .env file.
    Does not override existing environment variables (override=False).
    Fails loudly naming ONLY the missing variable name; never leaks values.
    """
    if env_path is not None:
        if not os.path.exists(env_path):
            raise QuickMLError(f"Configuration file not found: {env_path}")
        load_dotenv(dotenv_path=env_path, override=False)
    else:
        # Load from default .env in current working directory if present
        if os.path.exists(".env"):
            load_dotenv(dotenv_path=".env", override=False)

    config: Dict[str, str] = {}
    for var in REQUIRED_ENV_VARS:
        val = os.getenv(var)
        if val is None or val.strip() == "":
            raise QuickMLError(f"Missing required configuration environment variable: {var}")
        config[var] = val.strip()

    return config


def build_quickml_headers(config: Dict[str, str]) -> Dict[str, str]:
    """
    Builds the 4 verified Catalyst QuickML request headers.
    Ensures 'Zoho-oauthtoken ' prefix is prepended exactly once.
    """
    raw_token = config["QUICKML_AUTH_TOKEN"]
    token_prefix = "Zoho-oauthtoken "
    if raw_token.startswith(token_prefix):
        clean_token = raw_token[len(token_prefix):].strip()
    else:
        clean_token = raw_token.strip()

    return {
        "X-QUICKML-ENDPOINT-KEY": config["QUICKML_ENDPOINT_KEY"],
        "Authorization": f"Zoho-oauthtoken {clean_token}",
        "CATALYST-ORG": config["CATALYST_ORG_ID"],
        "Environment": config["ENVIRONMENT"],
        "Content-Type": "application/json",
    }


class QuickMLClient:
    """
    Client for interacting with the published Zoho Catalyst QuickML endpoint.
    Designed for reuse in predict.py and AppSail backend (Phase 4).
    """

    def __init__(
        self,
        config: Optional[Dict[str, str]] = None,
        env_path: Optional[str] = None,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        session: Optional[requests.Session] = None,
    ):
        self.config = config if config is not None else load_quickml_config(env_path)
        self.endpoint_url = self.config["QUICKML_ENDPOINT_URL"]
        self.headers = build_quickml_headers(self.config)
        self.timeout = timeout
        self.session = session or requests.Session()

    def _validate_response(self, response: requests.Response, expected_count: int) -> List[float]:
        """
        Enforces strict response validation:
        - Rejects redirects (3xx)
        - Requires HTTP 200
        - Requires valid JSON object
        - Requires 'result' key containing a list of length equal to expected_count
        - Requires each element to be a real, finite number (int or float)
        - Explicitly rejects booleans, strings, nulls, NaNs, and Infinities
        """
        # Reject redirects
        if response.status_code in (301, 302, 303, 307, 308) or response.is_redirect:
            raise QuickMLError(
                f"QuickML request failed: Redirect response received (status {response.status_code})"
            )

        # Require HTTP 200
        if response.status_code != 200:
            reason = response.reason if response.reason else "Error"
            raise QuickMLError(f"QuickML request failed: HTTP {response.status_code} {reason}")

        # Parse JSON
        try:
            body = response.json()
        except Exception:
            raise QuickMLError("QuickML request failed: Response body is not valid JSON")

        if not isinstance(body, dict):
            raise QuickMLError("QuickML request failed: Response root is not a JSON object")

        if "result" not in body:
            raise QuickMLError("QuickML request failed: Response missing 'result' field")

        result_list = body["result"]
        if not isinstance(result_list, list):
            raise QuickMLError("QuickML request failed: 'result' field is not a list")

        if len(result_list) != expected_count:
            raise QuickMLError(
                f"QuickML request failed: Result length mismatch (expected {expected_count}, got {len(result_list)})"
            )

        validated_floats: List[float] = []
        for idx, val in enumerate(result_list):
            # In Python, bool is a subclass of int (isinstance(True, int) == True)
            if isinstance(val, bool):
                raise QuickMLError(
                    f"QuickML request failed: Prediction value at index {idx} is boolean, not numeric"
                )
            if not isinstance(val, (int, float)):
                raise QuickMLError(
                    f"QuickML request failed: Prediction value at index {idx} is non-numeric ({type(val).__name__})"
                )
            if math.isnan(val) or math.isinf(val):
                raise QuickMLError(
                    f"QuickML request failed: Prediction value at index {idx} is NaN or Infinite"
                )
            validated_floats.append(float(val))

        return validated_floats

    def predict_single(self, record: Dict[str, Any]) -> float:
        """
        Sends a single record using verified shape: {"data": {record}}.
        Returns single float prediction.
        """
        payload = {"data": record}
        try:
            response = self.session.post(
                self.endpoint_url,
                json=payload,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.exceptions.Timeout:
            raise QuickMLError(f"QuickML request timed out after {self.timeout}s")
        except requests.exceptions.RequestException as e:
            # Report error class only, never leaking sensitive details
            raise QuickMLError(f"QuickML network error: {type(e).__name__}")

        preds = self._validate_response(response, expected_count=1)
        return preds[0]

    def predict_records(self, records: List[Dict[str, Any]]) -> List[float]:
        """
        Predicts demand for an ordered list of input records.
        Operates row-by-row respecting ROWS_PER_REQUEST = 1.
        Preserves exact input order.
        Aborts loudly at the first error without retries or silent fallbacks.
        """
        predictions: List[float] = []
        for idx, record in enumerate(records):
            try:
                pred = self.predict_single(record)
                predictions.append(pred)
            except QuickMLError as e:
                raise QuickMLError(f"Row {idx}: {str(e)}") from e

        return predictions
