# Phase 1: Catalyst QuickML Endpoint Evidence Log

> **Security Notice**: Do not paste live credentials, access tokens, endpoint keys, or raw confidential data into this log.

---

## 1. Pipeline Details

| Attribute | Specification / Observed Fact |
| :--- | :--- |
| **Pipeline / Model Status** | QuickML training succeeded, endpoint is **Published** |
| **Model Type** | LightGBM (Regression) |
| **Input Features** | `timestamp`, `ambient_temp_c`, `humidity_pct`, `solar_irradiance_wm2` |
| **Timestamp Handling** | Pipeline drops `timestamp` before LGBM. `timestamp` is retained in requests matching the successful console example. (Whether it can be omitted is untested; neither mandatory nor optional is assumed). |
| **Environment** | `Development` |
| **OAuth Scope** | `QuickML.deployment.READ` |

---

## 2. API Contract (Console-Verified Facts)

*The following contract facts were verified directly in the Catalyst QuickML console tester:*

| Contract Item | Specification |
| :--- | :--- |
| **Endpoint URL Shape** | `https://api.catalyst.zoho.in/quickml/v1/project/<PROJECT_ID>/endpoints/predict`<br>*(Exact URL copied directly from console; never constructed from IDs)* |
| **HTTP Method** | `POST` |
| **Required Header 1** | `X-QUICKML-ENDPOINT-KEY` |
| **Required Header 2** | `Authorization` (format: `Zoho-oauthtoken <token>`) |
| **Required Header 3** | `CATALYST-ORG` (Organization ID) |
| **Required Header 4** | `Environment` (`Development`) |
| **Content-Type** | `application/json` |

---

## 3. Verified JSON Schemas (Keys Only)

### Console-Verified Single-Row Request Envelope
```json
{
  "data": {
    "timestamp": "STRING",
    "ambient_temp_c": "FLOAT",
    "humidity_pct": "FLOAT",
    "solar_irradiance_wm2": "FLOAT_OR_INT"
  }
}
```

### Console-Verified Single-Row Response Envelope
```json
{
  "result": [
    "FLOAT"
  ]
}
```

### Native Multi-Row Batch Envelope
- **Status**: **UNKNOWN / UNVERIFIED**.
- Native batching is disabled pending official documentation or a verified multi-row console example.

---

## 4. External Python Test Results

> **Current Status**: External Python single-row access is **VERIFIED**.

### Single-Row Smoke Test (`quickml_smoke_test.py`)

| Metric | Target / Expectation | Observed Local Value |
| :--- | :--- | :--- |
| **HTTP Status Code** | `200` | `200` |
| **Request Latency** | Finite (< 5000 ms) | `1274.96 ms` |
| **Prediction Count** | Exactly 1 finite numeric value | `1` |
| **Validation Outcome** | PASS | `PASS` (Valid finite numeric prediction returned) |

---

### Sequential Probing vs. Native Batching

*Note: 24 sequential single-row requests validate per-request execution; they do not prove native batch support.*

| Test Run | Mode Description | Largest Size Tested | HTTP Status | Latency Summary | Outcome |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Sequential Check** | 24 sequential single-row requests | 24 | | | |
| **Native Multi-Row** | Native batch payload probe | N/A | Blocked | N/A | Disabled (contract unverified) |
| **Larger Probes** | 100 / 1,000 requests | N/A | Blocked | N/A | Blocked pending approval |

---

## 5. Security Sign-Off

- [x] `.env` is listed in `.gitignore` and verified untracked by Git.
- [x] `load_dotenv` called without `override=True`.
- [x] Code and logs redact credentials, full URLs, raw responses, and request headers.
- [x] No live credentials, endpoint keys, or tokens committed or shared.
