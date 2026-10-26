# GridPulse ⚡

> **Electricity Demand Forecasting Engine & Smart Microgrid Analytics**  
> *Built for HackSphere 3.0 on Zoho Catalyst QuickML*

---

## 🌟 Overview

**GridPulse** is an end-to-end demand forecasting and grid intelligence engine designed for modern smart microgrids. Powered by an automated regression pipeline published on **Zoho Catalyst QuickML**, GridPulse forecasts hourly energy demand across a 24-hour horizon using environmental telemetry (`ambient_temp_c`, `humidity_pct`, `solar_irradiance_wm2`) to enable automated microgrid power-source switching.

---

## 🏗️ Architecture

```
Telemetry Dataset ──► Zoho Catalyst QuickML ──► predict.py (Live Endpoint) ──► Static Analytics Dashboard
(Weather & Load)      (Automated Regression)    (Strict Judge Contract CLI)     (Chart.js + Metrics)
```

1. **QuickML Training**: Regression pipeline trained on historical telemetry and published to an authenticated Zoho Catalyst endpoint.
2. **Inference Client (`quickml_client.py`)**: Zero-fallback client enforcing OAuth authentication (`Zoho-oauthtoken`), strict response validation, and fail-loud error handling.
3. **Judge Contract CLI (`predict.py`)**: Command-line interface taking `--input <csv>` and outputting `--output <csv>` with atomic file writes and input validation.
4. **Cinematic Web Dashboard (`dashboard/`)**: Static, lightweight, zero-framework analytics interface visualizing hourly load predictions, Model MAPE (20.88%), and engineering disclosures.

---

## 🚀 Quick Start

### 1. Environment Setup

Clone the repository and install requirements:

```bash
git clone https://github.com/NITISH-027/Gridpulse.git
cd Gridpulse
pip install -r requirements.txt
```

### 2. Configure Credentials

Copy the template to `.env` (never commit real tokens or credentials):

```bash
cp .env.example .env
```

Set the following variables in `.env`:
- `QUICKML_ENDPOINT_URL`: Your published Catalyst QuickML endpoint URL
- `QUICKML_ENDPOINT_KEY`: Your QuickML endpoint key
- `QUICKML_AUTH_TOKEN`: OAuth access token
- `CATALYST_ORG_ID`: Zoho Catalyst Organization ID
- `ENVIRONMENT`: `Development`

*(A helper script `get_quickml_token.ps1` is provided to exchange Zoho Self Client authorization codes for access tokens.)*

### 3. Run Inference

Generate predictions for any input CSV file:

```bash
python predict.py --input sample_test_input.csv --output predictions.csv
```

### 4. Run the Test Suite

Run offline unit and mocked evaluation tests:

```bash
python -m unittest test_phase1.py
python -m unittest test_phase2.py
```

### 5. Launch the Dashboard

Open `dashboard/index.html` in your browser, or serve locally:

```bash
cd dashboard
python -m http.server 8000
```

---

## 📊 Live Verification Status

- **Phase 1 Verification**: 24/24 sequential single-row endpoint calls verified on live QuickML endpoint (HTTP 200, 100% pass).
- **Model Evaluation**: Model MAPE of **20.88%** on held-out evaluation data.
- **Judge Harness Compatibility**: Passes `test_eval.py` pre-submission validation.

---

## 🛡️ Security

- Credentials and tokens are managed exclusively through local `.env` variables and are never checked into version control.
- Git tracking strictly excludes `.env`, secrets, and proprietary telemetry datasets via `.gitignore`.
