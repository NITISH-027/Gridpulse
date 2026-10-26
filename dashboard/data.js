// =============================================================================
// GRIDPULSE - FORECAST RESULTS DATA STORE
//
// HOW TO EDIT THIS FILE:
// 1. EDIT LINES 14-38: Paste or extend your real telemetry rows into the `RESULTS` array below.
// 2. Each entry requires:
//      timestamp: "YYYY-MM-DD HH:MM:SS" (or any standard date string)
//      actual:    number (Actual demand in kW)
//      predicted: number (QuickML demand prediction in kW from predict.py)
// 3. EDIT LINES 47-56: Set your summary metrics (Total Predictions, Model Accuracy).
// =============================================================================

const RESULTS = [
  {
    timestamp: "2015-06-16 15:00:00",
    actual: null,
    predicted: 246.5601050824599
  },
  {
    timestamp: "2015-06-16 16:00:00",
    actual: null,
    predicted: 238.07221004868555
  },
  {
    timestamp: "2015-06-16 17:00:00",
    actual: null,
    predicted: 231.86139106280447
  },
  {
    timestamp: "2015-06-16 18:00:00",
    actual: null,
    predicted: 284.2008685625239
  },
  {
    timestamp: "2015-06-16 19:00:00",
    actual: null,
    predicted: 274.70645075081785
  },
  {
    timestamp: "2015-06-16 20:00:00",
    actual: null,
    predicted: 228.5929489955445
  },
  {
    timestamp: "2015-06-16 21:00:00",
    actual: null,
    predicted: 238.6835122278434
  },
  {
    timestamp: "2015-06-16 22:00:00",
    actual: null,
    predicted: 144.50186085431972
  },
  {
    timestamp: "2015-06-16 23:00:00",
    actual: null,
    predicted: 213.420754613177
  },
  {
    timestamp: "2015-06-17 00:00:00",
    actual: null,
    predicted: 155.96201068555362
  },
  {
    timestamp: "2015-06-17 01:00:00",
    actual: null,
    predicted: 160.71907612047394
  },
  {
    timestamp: "2015-06-17 02:00:00",
    actual: null,
    predicted: 144.15234752631847
  },
  {
    timestamp: "2015-06-17 03:00:00",
    actual: null,
    predicted: 99.91444056052312
  },
  {
    timestamp: "2015-06-17 04:00:00",
    actual: null,
    predicted: 96.77463497094463
  },
  {
    timestamp: "2015-06-17 05:00:00",
    actual: null,
    predicted: 137.96600430832117
  },
  {
    timestamp: "2015-06-17 06:00:00",
    actual: null,
    predicted: 139.92014431142465
  },
  {
    timestamp: "2015-06-17 07:00:00",
    actual: null,
    predicted: 174.1184917748269
  },
  {
    timestamp: "2015-06-17 08:00:00",
    actual: null,
    predicted: 209.6653696732271
  },
  {
    timestamp: "2015-06-17 09:00:00",
    actual: null,
    predicted: 210.45626391292456
  },
  {
    timestamp: "2015-06-17 10:00:00",
    actual: null,
    predicted: 213.95693700070174
  },
  {
    timestamp: "2015-06-17 11:00:00",
    actual: null,
    predicted: 214.78015194390562
  },
  {
    timestamp: "2015-06-17 12:00:00",
    actual: null,
    predicted: 238.9941510859728
  },
  {
    timestamp: "2015-06-17 13:00:00",
    actual: null,
    predicted: 247.66277568450707
  },
  {
    timestamp: "2015-06-17 14:00:00",
    actual: null,
    predicted: 248.35405265862673
  }
];

// =============================================================================
// METRICS CONFIGURATION (CARD VALUES)
// EDIT LINES 60-63 with your real performance numbers:
// =============================================================================
const METRICS = {
  // Line 47: Total predictions made across your runs (e.g., "24" or your total)
  totalPredictions: "24",

  // Line 50: Verified against live endpoint (Keep as "24/24" per Phase 2 audit)
  liveVerified: "24/24",

  // Model MAPE metric from QuickML model GridPulse_SmokeModel
  modelAccuracy: "20.88%",
  modelAccuracyLabel: "Model MAPE (lower is better)",

  // Forecast horizon duration
  forecastHorizon: "24 Hours",

  // Engineering disclosure note
  engineeringNote: "Live endpoint verified 24/24 on Oct 26. Free tier caps live calls at 500/month; the full 1000-row run completes after the monthly reset. Model MAPE: 20.88% on held-out evaluation data."
};
