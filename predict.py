#!/usr/bin/env python3
"""
GridPulse - Demand Forecasting Predictor
Phase 2: Judge Contract Implementation (predict.py)

Official interface for generating energy demand predictions from input telemetry.
Satisfies the HackSphere 3.0 judge contract:
- Validates raw input before making any API calls (columns, timestamps, numeric weather values)
- Dispatches requests through the verified shared QuickMLClient
- Returns a numpy array of floats preserving input length and row order
- Atomic CLI execution: outputs timestamp,target_demand_kw only after all rows succeed
- Fail-loud semantics: zero dummy fallbacks (sine wave removed); aborts with non-zero exit code
"""

import argparse
import math
import os
import sys
import tempfile
from typing import Any, Dict, List
import numpy as np
import pandas as pd

from quickml_client import QuickMLClient, QuickMLError

REQUIRED_COLUMNS: List[str] = [
    "timestamp",
    "ambient_temp_c",
    "humidity_pct",
    "solar_irradiance_wm2",
]


def validate_input_dataframe(df: pd.DataFrame) -> None:
    """
    Validates input DataFrame against the inference contract before any network calls.
    - Ensures all four required columns exist
    - Ensures every timestamp parses as a valid datetime
    - Ensures all weather values are numeric, finite, non-null, and NOT booleans
    - Reports row numbers on any failure
    """
    if not isinstance(df, pd.DataFrame):
        raise ValueError(f"Input must be a pandas DataFrame, got {type(df).__name__}")

    if df.empty:
        raise ValueError("Input DataFrame is empty")

    # Check required columns
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Input DataFrame is missing required column(s): {missing_cols}")

    # Validate row-by-row
    for idx, row in df.iterrows():
        # Validate timestamp
        ts_val = row["timestamp"]
        if pd.isna(ts_val) or ts_val is None:
            raise ValueError(f"Row {idx}: 'timestamp' is missing or null")
        try:
            parsed_ts = pd.to_datetime(ts_val)
            if pd.isna(parsed_ts):
                raise ValueError(f"Row {idx}: 'timestamp' '{ts_val}' cannot be parsed")
        except Exception as e:
            raise ValueError(f"Row {idx}: Invalid timestamp '{ts_val}': {e}")

        # Validate weather features
        for col in ["ambient_temp_c", "humidity_pct", "solar_irradiance_wm2"]:
            val = row[col]
            if pd.isna(val) or val is None:
                raise ValueError(f"Row {idx}: Column '{col}' is missing or null")

            # In Python, bool is a subclass of int, so reject booleans explicitly
            if isinstance(val, bool):
                raise ValueError(f"Row {idx}: Column '{col}' has boolean value '{val}', numeric required")

            # Check if numeric
            if not isinstance(val, (int, float, np.number)):
                # If it's a string, reject rather than silently coercing
                raise ValueError(f"Row {idx}: Column '{col}' has non-numeric value '{val}' (type: {type(val).__name__})")

            # Check finite
            f_val = float(val)
            if math.isnan(f_val) or math.isinf(f_val):
                raise ValueError(f"Row {idx}: Column '{col}' has NaN or Infinite value '{val}'")


def prepare_features(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Constructs feature records for QuickML inference.
    Feature construction lives in this single shared function so Phase 3's feature
    changes apply to training and inference together.
    """
    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        record = {
            "timestamp": str(row["timestamp"]),
            "ambient_temp_c": float(row["ambient_temp_c"]),
            "humidity_pct": float(row["humidity_pct"]),
            "solar_irradiance_wm2": float(row["solar_irradiance_wm2"]),
        }
        records.append(record)
    return records


def predict(input_df: pd.DataFrame, client: QuickMLClient = None) -> np.ndarray:
    """
    Generates demand predictions (target_demand_kw) for the input DataFrame.

    Parameters:
        input_df (pandas.DataFrame): DataFrame with columns
            ['timestamp', 'ambient_temp_c', 'humidity_pct', 'solar_irradiance_wm2']
        client (QuickMLClient, optional): Client instance. If None, initialized from environment.

    Returns:
        numpy.ndarray: Predicted demand (kW) as 1D float array, exactly one per input row.

    Raises:
        ValueError: On schema or data validation failure.
        QuickMLError: On endpoint communication or response validation failure.
    """
    validate_input_dataframe(input_df)

    if client is None:
        client = QuickMLClient()

    records = prepare_features(input_df)
    preds = client.predict_records(records)

    preds_array = np.array(preds, dtype=float)

    if len(preds_array) != len(input_df):
        raise QuickMLError(
            f"Prediction count mismatch: expected {len(input_df)}, got {len(preds_array)}"
        )

    return preds_array


def run_cli() -> None:
    """
    Command Line Interface:
    python predict.py --input sample_test_input.csv --output predictions.csv

    Enforces atomic file output:
    Writes to a temporary file and renames it into place only after all predictions succeed.
    On any failure, existing output files remain untouched and no partial file is created.
    """
    parser = argparse.ArgumentParser(
        description="GridPulse - QuickML Energy Demand Predictor CLI"
    )
    parser.add_argument(
        "--input",
        "-i",
        default="sample_test_input.csv",
        help="Path to input telemetry CSV file (default: sample_test_input.csv)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="predictions.csv",
        help="Path to output predictions CSV file (default: predictions.csv)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input):
        sys.stderr.write(f"ERROR: Input file not found: {args.input}\n")
        sys.exit(1)

    try:
        input_df = pd.read_csv(args.input)
    except Exception as e:
        sys.stderr.write(f"ERROR: Failed to read input CSV '{args.input}': {e}\n")
        sys.exit(1)

    temp_file_path: str = None
    try:
        # Run prediction pipeline
        predictions = predict(input_df)

        # Prepare output DataFrame adhering to the official judge schema
        out_df = pd.DataFrame({
            "timestamp": input_df["timestamp"].astype(str),
            "target_demand_kw": predictions,
        })

        # Atomic write: write to temporary file first
        output_abs = os.path.abspath(args.output)
        output_dir = os.path.dirname(output_abs) or "."
        os.makedirs(output_dir, exist_ok=True)

        temp_fd, temp_file_path = tempfile.mkstemp(
            prefix="gridpulse_pred_",
            suffix=".tmp",
            dir=output_dir,
        )
        os.close(temp_fd)

        out_df.to_csv(temp_file_path, index=False)

        # Atomically replace target file
        os.replace(temp_file_path, output_abs)
        temp_file_path = None  # Successfully replaced

        print(
            f"SUCCESS: Generated {len(predictions)} predictions. Saved atomically to '{args.output}'."
        )

    except (ValueError, QuickMLError) as e:
        sys.stderr.write(f"ERROR: {e}\n")
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"ERROR: Unexpected failure during prediction: {e}\n")
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass
        sys.exit(1)


if __name__ == "__main__":
    run_cli()