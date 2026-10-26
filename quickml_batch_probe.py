#!/usr/bin/env python3
"""
GridPulse - Phase 1: QuickML Sequential Single-Row Probe
Executes 24 sequential single-row requests using validated CSV inputs.
Circuit breaker: Stops immediately on the first HTTP, network, or schema failure.
Native multi-row batching is disabled pending an official verified contract.
"""

import argparse
import csv
import math
import os
import sys
import time
from typing import Any, Dict, List
import requests

from quickml_smoke_test import (
    load_config,
    build_headers,
    validate_quickml_response,
)

CSV_DEFAULT_PATH = "sample_test_input.csv"
REQUIRED_COLUMNS = ["timestamp", "ambient_temp_c", "humidity_pct", "solar_irradiance_wm2"]
SEQUENTIAL_COUNT = 24

def load_and_validate_csv(csv_path: str, count: int = SEQUENTIAL_COUNT) -> List[Dict[str, Any]]:
    """
    Validates CSV existence and schema before any network requests are initiated.
    Fails if row count is insufficient or any field is malformed.
    Names the row and field without dumping confidential data.
    Preserves input order without skipping, repeating, or synthesizing rows.
    """
    if not os.path.exists(csv_path):
        raise ValueError(f"Input CSV file not found: {csv_path}")

    rows: List[Dict[str, Any]] = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV file is empty or missing headers: {csv_path}")

        missing_cols = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing_cols:
            raise ValueError(f"CSV missing required columns: {missing_cols}")

        for raw_row in reader:
            rows.append(raw_row)

    if len(rows) < count:
        raise ValueError(f"Insufficient rows in CSV: required {count}, found {len(rows)}")

    validated_rows: List[Dict[str, Any]] = []
    for i in range(count):
        row_num = i + 1  # 1-indexed for clear human-readable error reporting
        row = rows[i]

        timestamp = row.get("timestamp")
        if not timestamp or not timestamp.strip():
            raise ValueError(f"Row {row_num}: field 'timestamp' is missing or empty")

        parsed_row: Dict[str, Any] = {"timestamp": timestamp.strip()}
        for numeric_field in ["ambient_temp_c", "humidity_pct", "solar_irradiance_wm2"]:
            raw_val = row.get(numeric_field)
            if raw_val is None or str(raw_val).strip() == "":
                raise ValueError(f"Row {row_num}: field '{numeric_field}' is missing or empty")
            try:
                val = float(raw_val)
                if not math.isfinite(val):
                    raise ValueError(f"Row {row_num}: field '{numeric_field}' is not finite")
                parsed_row[numeric_field] = val
            except ValueError:
                raise ValueError(f"Row {row_num}: field '{numeric_field}' is not a valid finite number")

        validated_rows.append(parsed_row)

    return validated_rows

def run_sequential_check(csv_path: str = CSV_DEFAULT_PATH, env_path: str = ".env") -> int:
    """
    Executes exactly 24 sequential single-row requests.
    Stops immediately on the first failure (circuit breaker).
    Never prints credentials, full URLs, raw responses, or unsanitized exceptions.
    """
    print("=" * 72)
    print("GridPulse Phase 1 - 24 Sequential Single-Row Requests")
    print("NOTICE: Validates 24 sequential requests; does NOT prove native batch support.")
    print("=" * 72)

    # 1. Pre-network validation
    try:
        config = load_config(env_path)
    except ValueError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        return 1

    try:
        validated_rows = load_and_validate_csv(csv_path, count=SEQUENTIAL_COUNT)
    except ValueError as e:
        print(f"Data Validation Error: {e}", file=sys.stderr)
        return 1

    headers = build_headers(config)
    endpoint_url = config["QUICKML_ENDPOINT_URL"]

    print(f"Pre-flight validation passed for {len(validated_rows)} rows.")
    print("-" * 72)
    print(f"{'Req #':<8} | {'HTTP Status':<12} | {'Latency (ms)':<14} | {'Predictions':<13} | {'Outcome':<10}")
    print("-" * 72)

    # 2. Sequential execution
    for idx, row in enumerate(validated_rows, start=1):
        payload = {
            "data": {
                "timestamp": row["timestamp"],
                "ambient_temp_c": row["ambient_temp_c"],
                "humidity_pct": row["humidity_pct"],
                "solar_irradiance_wm2": row["solar_irradiance_wm2"],
            }
        }

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
            print(f"{idx:<8} | {'N/A':<12} | {latency_ms:<14.2f} | {'0':<13} | TIMEOUT")
            print(f"\n[CIRCUIT BREAKER] Request {idx} timed out. Aborting immediately.", file=sys.stderr)
            return 1
        except requests.exceptions.RequestException as e:
            print(f"{idx:<8} | {'N/A':<12} | {'N/A':<14} | {'0':<13} | NET_ERR")
            print(f"\n[CIRCUIT BREAKER] Network transport error on request {idx}: {type(e).__name__}. Aborting.", file=sys.stderr)
            return 1

        is_valid, pred_count, message = validate_quickml_response(status_code, response_text)

        if not is_valid:
            outcome = "FAIL"
            if status_code in (401, 403):
                outcome = "AUTH_FAIL"
            elif status_code == 429:
                outcome = "RATE_LIMIT"
            elif 500 <= status_code < 600:
                outcome = "SERVER_ERR"

            print(f"{idx:<8} | {status_code:<12} | {latency_ms:<14.2f} | {pred_count:<13} | {outcome}")
            print(f"\n[CIRCUIT BREAKER] Request {idx} failed: {message}. Aborting sequential run.", file=sys.stderr)
            return 1

        print(f"{idx:<8} | {status_code:<12} | {latency_ms:<14.2f} | {pred_count:<13} | PASS")

    print("-" * 72)
    print("Execution Summary: 24/24 sequential single-row requests completed successfully.")
    print("=" * 72)
    return 0

def main():
    parser = argparse.ArgumentParser(description="GridPulse Phase 1: Sequential Single-Row Probe")
    parser.add_argument("--csv", default=CSV_DEFAULT_PATH, help="Path to input CSV file (default: sample_test_input.csv)")
    parser.add_argument("--mode", default="sequential-24", choices=["sequential-24", "batch-probe"],
                        help="Execution mode (default: sequential-24)")
    parser.add_argument("--env", default=".env", help="Path to .env file (default: .env)")

    args = parser.parse_args()

    if args.mode == "batch-probe":
        print("[BLOCKED] Native multi-row batch probing is disabled: multi-row contract is unknown.", file=sys.stderr)
        print("[BLOCKED] Larger probes (100, 1000) are blocked pending verified support and separate approval.", file=sys.stderr)
        sys.exit(1)

    sys.exit(run_sequential_check(csv_path=args.csv, env_path=args.env))

if __name__ == "__main__":
    main()
