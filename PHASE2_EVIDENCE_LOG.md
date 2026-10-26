# Phase 2 Evidence Log: Judge Contract Implementation

> **Status**: Implementation Ready, Live Full Validation Pending  
> **Authority**: GridPulse_Final_Implementation_Plan_v1_1.md (Stage 1) / Phase 2 Plan (25 Oct 2026)  
> **Security Notice**: No secrets, raw credentials, tokens, full URLs, or raw API response bodies are logged here or in the repository.

---

## 1. Locked Contract Facts (from Phase 1 Live Endpoint)

| Item | Verified Specification |
| :--- | :--- |
| **Model / Pipeline** | Trained and published in QuickML. Target: `target_demand_kw`. Features: `ambient_temp_c`, `humidity_pct`, `solar_irradiance_wm2` (timestamp dropped before LGBM). |
| **Environment** | `Development` |
| **URL Host** | `api.catalyst.zoho.in` (Path: `/quickml/v1/project/<project-id>/endpoints/predict` from `.env` only) |
| **Required Header Names** | `X-QUICKML-ENDPOINT-KEY`, `Authorization`, `CATALYST-ORG`, `Environment`, `Content-Type` |
| **Authorization Format** | `Zoho-oauthtoken <token>` (Scope: `QuickML.deployment.READ`) |
| **Verified Request Shape** | `{"data": {record}}` — single record object with `timestamp`, `ambient_temp_c`, `humidity_pct`, `solar_irradiance_wm2` |
| **Verified Response Shape** | `{"result": [number]}` — single finite float prediction in list |
| **Rows-per-Request** | Fixed at `1` in code configuration (`ROWS_PER_REQUEST = 1`) |
| **Native Batching** | Unverified / Unknown. Probing disabled; documented as open research question |
| **Live Endpoint Baseline** | Single-row HTTP 200 (~1275 ms); 24 sequential single-row requests (HTTP 200, 679–1267 ms) |
| **Token Lifetime** | ~1 hour; renewal via Zoho Self Client authorization-code flow |

---

## 2. Implementation Summary

### `quickml_client.py` (Shared Client Module)
- **Environment loading**: Reads `QUICKML_ENDPOINT_URL`, `QUICKML_ENDPOINT_KEY`, `QUICKML_AUTH_TOKEN`, `CATALYST_ORG_ID`, `ENVIRONMENT` via `load_dotenv(override=False)`.
- **Fail-loud config**: Fails clearly citing the exact missing variable name without exposing values.
- **Safe HTTP semantics**: `allow_redirects=False`, strict 10.0s timeout, zero retries.
- **Strict response validation**: Validates HTTP 200, valid JSON dictionary, presence of `"result"` key, list length matching sent rows, and numeric finite real values (explicitly rejecting booleans, strings, nulls, NaNs, and Infs).
- **Sanitized error reporting**: Reports status code and error class only. Never logs headers, tokens, or response bodies.

### `predict.py` (Judge Contract Interface & CLI)
- **Raw input validation**: Enforces presence of `timestamp`, `ambient_temp_c`, `humidity_pct`, `solar_irradiance_wm2`; validates timestamp parseability; rejects booleans and non-numeric weather values; reports exact row numbers on failure.
- **Feature construction**: Encapsulated in single `prepare_features()` function for shared consistency across training and inference (ready for Phase 3).
- **Inference function**: `predict(input_df)` returns a 1D `numpy.ndarray` of floats, exactly one per input row, preserving input row order.
- **Official CLI**: `python predict.py --input <input.csv> --output <output.csv>`. Header is exactly `timestamp,target_demand_kw`.
- **Atomic write**: Writes to a temporary file (`.tmp`) first and replaces the target file atomically via `os.replace()`. On any failure, no partial file is created and any existing output file is preserved untouched.
- **Zero fallbacks**: Starter's sine-wave dummy fallback is completely removed.

---

## 3. Offline Full-Coverage Mocked Test Suite (`test_phase2.py`)

All 25 tests passed offline with zero live calls:

| Test Class | Test Case | Target Checked | Status |
| :--- | :--- | :--- | :---: |
| `TestPhase2ConfigAndHeaders` | `test_load_quickml_config_success` | Environment variables loading | **PASS** |
| | `test_load_quickml_config_missing_var` | Missing var fails loudly without leak | **PASS** |
| | `test_build_quickml_headers_prefix_handling` | `Zoho-oauthtoken` prefixed exactly once | **PASS** |
| `TestPhase2ClientResponseValidation` | `test_valid_single_response` | HTTP 200 with valid float result | **PASS** |
| | `test_reject_redirect` | HTTP 302 redirect rejected | **PASS** |
| | `test_http_500_error` | HTTP 500 fails loudly | **PASS** |
| | `test_http_401_auth_error_sanitized` | HTTP 401 reports error class without token leak | **PASS** |
| | `test_invalid_json_body` | Non-JSON response fails | **PASS** |
| | `test_json_root_not_dict` | Non-object JSON root fails | **PASS** |
| | `test_missing_result_key` | JSON missing `result` key fails | **PASS** |
| | `test_result_length_mismatch` | Empty list or multiple items in single-row mode fails | **PASS** |
| | `test_reject_boolean_prediction` | `[True]` or `[False]` rejected | **PASS** |
| | `test_reject_string_prediction` | String prediction `["150.0"]` rejected | **PASS** |
| | `test_reject_nan_and_inf_prediction` | NaN or Infinite prediction rejected | **PASS** |
| | `test_timeout_and_network_error` | Timeout / ConnectionError reported as sanitized error class | **PASS** |
| `TestPhase2InputValidation` | `test_missing_required_column` | Missing feature column fails with column name | **PASS** |
| | `test_invalid_timestamp` | Unparseable timestamp fails with row index | **PASS** |
| | `test_boolean_in_weather_column` | Boolean in weather features fails with row index | **PASS** |
| | `test_string_in_weather_column` | String in weather features fails with row index | **PASS** |
| | `test_nan_in_weather_column` | NaN in weather features fails with row index | **PASS** |
| `TestPhase2Full1000RowCoverage` | `test_predict_full_1000_rows_offline` | 1,000-row `sample_test_input.csv` returns 1,000 predictions | **PASS** |
| | `test_fail_loud_no_dummy_fallback` | Failure at row aborts loudly; no sine fallback | **PASS** |
| `TestPhase2CLIAndAtomicOutput` | `test_cli_atomic_output_preserves_existing_on_failure` | Failure preserves pre-existing predictions file | **PASS** |
| | `test_cli_full_1000_row_output_schema_offline` | Output CSV schema matches `timestamp,target_demand_kw` | **PASS** |
| `TestJudgeHarnessCompatibility` | `test_test_eval_compatibility` | `test_eval.py` execution succeeds against `predict()` | **PASS** |

---

## 4. Bounded Live Verification Protocol (Step 5)

*Prepared for Nitish to execute in project terminal with valid access token:*

### Step 5.1: 1-Row Live Check
```bash
python predict.py --input sample_1row.csv --output pred_1row.csv
```
- **Expectation**: HTTP 200, exactly 1 prediction returned, atomic write to `pred_1row.csv`.

### Step 5.2: 24-Row Live Check
```bash
python predict.py --input sample_24row.csv --output pred_24row.csv
```
- **Expectation**: 24 sequential single-row requests, HTTP 200 each, 24 predictions in order, atomic write to `pred_24row.csv`.

### Stop Rule
Stop immediately on the first error of any kind (non-200, HTTP 429, auth challenge, 5xx, or network timeout).
If token has expired, renew via Self Client authorization code helper script before re-running.

### Live Results Table (Fill In)
| Step | Input Slice | Status Code / Outcome | Latency (est.) | Prediction Count | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **5.1 Single Row** | `sample_1row.csv` | *Pending Nitish Run* | | | |
| **5.2 24 Rows** | `sample_24row.csv` | *Pending Nitish Run* | | | |

---

## 5. Full-Size Live Run Status (Step 6)

- **Status**: **Implementation ready, live full validation pending**.
- **Gate 1 (Facts first)**: Quota, rate limits, invocation allowances, and cost limits must be officially gathered before 1,000 live sequential calls are initiated.
- **Gate 2 (Decision)**: Nitish's explicit decision based on verified limits.
- Estimated execution time for 1,000 single-row calls: ~12–22 minutes (~1.0s/call average).

---

## 6. Open Items Carried Forward

1. **Judge Credential Provisioning**: Awaiting response / instructions on how credentials will be supplied to evaluators.
2. **Rate & Invocation Limits**: Official Zoho documentation / support inquiry on rate limits.
3. **Native Multi-Row Batch Support**: Documented inquiry on whether QuickML endpoints support batch payloads.
4. **Token Lifetime vs. Full 1,000-Row Run**: Verification that access token does not expire during a ~20 minute continuous run.
