// =============================================================================
// GRIDPULSE - DASHBOARD APPLICATION LOGIC
// Initialises metrics cards, configures Chart.js line chart, and handles custom legend.
// =============================================================================

document.addEventListener("DOMContentLoaded", () => {
  initMetrics();
  initDemandChart();
});

/**
 * Populates metric card values from `METRICS` object in data.js
 */
function initMetrics() {
  if (typeof METRICS !== "undefined") {
    const totalEl = document.getElementById("metricTotalPredictions");
    const liveEl = document.getElementById("metricLiveVerified");
    const accEl = document.getElementById("metricModelAccuracy");
    const horizEl = document.getElementById("metricForecastHorizon");

    if (totalEl && METRICS.totalPredictions) {
      totalEl.textContent = METRICS.totalPredictions;
    }
    if (liveEl && METRICS.liveVerified) {
      liveEl.textContent = METRICS.liveVerified;
    }
    if (accEl && METRICS.modelAccuracy) {
      accEl.textContent = METRICS.modelAccuracy;
    }
    if (METRICS.modelAccuracyLabel) {
      const accLabelEl = document.getElementById("metricModelAccuracyLabel");
      if (accLabelEl) accLabelEl.textContent = METRICS.modelAccuracyLabel;
    }
    if (horizEl && METRICS.forecastHorizon) {
      horizEl.textContent = METRICS.forecastHorizon;
    }
    if (METRICS.engineeringNote) {
      const noteEl = document.getElementById("engineeringNoteBody");
      if (noteEl) noteEl.textContent = METRICS.engineeringNote;
    }
  }
}

/**
 * Configures and renders the Actual vs. Predicted Demand line chart using Chart.js
 */
function initDemandChart() {
  const canvas = document.getElementById("demandForecastChart");
  if (!canvas) return;

  // Validate that RESULTS exists in data.js
  if (typeof RESULTS === "undefined" || !Array.isArray(RESULTS) || RESULTS.length === 0) {
    console.warn("[GridPulse] No telemetry data found in data.js");
    return;
  }

  // Extract labels and dataset series
  const labels = RESULTS.map(item => formatTimestamp(item.timestamp));
  const actualData = RESULTS.map(item => item.actual);
  const predictedData = RESULTS.map(item => item.predicted);

  const ctx = canvas.getContext("2d");

  // Create subtle vertical area gradient for predicted demand
  const predictedGradient = ctx.createLinearGradient(0, 0, 0, 400);
  predictedGradient.addColorStop(0, "rgba(0, 245, 160, 0.16)");
  predictedGradient.addColorStop(1, "rgba(0, 245, 160, 0.0)");

  const chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Actual Demand",
          data: actualData,
          borderColor: "#94A3B8",
          backgroundColor: "transparent",
          borderWidth: 2,
          borderDash: [5, 5],
          pointRadius: 3,
          pointBackgroundColor: "#94A3B8",
          pointBorderColor: "#0B101A",
          pointBorderWidth: 1.5,
          pointHoverRadius: 6,
          pointHoverBackgroundColor: "#F8FAFC",
          tension: 0.3,
          order: 2
        },
        {
          label: "QuickML Predicted",
          data: predictedData,
          borderColor: "#00F5A0",
          backgroundColor: predictedGradient,
          borderWidth: 2.5,
          fill: true,
          pointRadius: 4,
          pointBackgroundColor: "#06090E",
          pointBorderColor: "#00F5A0",
          pointBorderWidth: 2,
          pointHoverRadius: 7,
          pointHoverBackgroundColor: "#00F5A0",
          pointHoverBorderColor: "#F8FAFC",
          pointHoverBorderWidth: 2,
          tension: 0.35,
          order: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: {
          left: 24,
          right: 16,
          top: 10,
          bottom: 10
        }
      },
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: false // Using custom accessible header legend
        },
        tooltip: {
          enabled: true,
          backgroundColor: "rgba(11, 16, 26, 0.94)",
          titleColor: "#F8FAFC",
          bodyColor: "#94A3B8",
          borderColor: "rgba(255, 255, 255, 0.12)",
          borderWidth: 1,
          padding: 12,
          cornerRadius: 8,
          boxPadding: 6,
          titleFont: {
            family: "'JetBrains Mono', monospace",
            size: 12,
            weight: "600"
          },
          bodyFont: {
            family: "'Plus Jakarta Sans', sans-serif",
            size: 13
          },
          callbacks: {
            label: function(context) {
              const label = context.dataset.label || "";
              const val = context.parsed.y;
              return ` ${label}: ${val !== null ? val.toFixed(2) + " kW" : "N/A"}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: {
            color: "rgba(255, 255, 255, 0.03)",
            borderColor: "rgba(255, 255, 255, 0.08)"
          },
          ticks: {
            color: "#64748B",
            font: {
              family: "'JetBrains Mono', monospace",
              size: 11
            },
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 8
          }
        },
        y: {
          title: {
            display: true,
            text: "Demand (kW)",
            color: "#64748B",
            padding: {
              bottom: 8,
              top: 0
            },
            font: {
              family: "'Plus Jakarta Sans', sans-serif",
              size: 12,
              weight: "500"
            }
          },
          grid: {
            color: "rgba(255, 255, 255, 0.04)",
            borderColor: "rgba(255, 255, 255, 0.08)"
          },
          ticks: {
            color: "#64748B",
            padding: 8,
            font: {
              family: "'JetBrains Mono', monospace",
              size: 11
            },
            callback: function(value) {
              return value + " kW";
            }
          }
        }
      }
    }
  });

  // Attach click-to-toggle behaviour on custom legend items
  setupCustomLegend(chart);
}

/**
 * Formats ISO or standard datetime strings into compact hourly labels (e.g. "15:00" or "Jun 16, 15:00")
 */
function formatTimestamp(tsString) {
  if (!tsString) return "";
  // Check if it's "YYYY-MM-DD HH:MM:SS"
  const parts = tsString.trim().split(" ");
  if (parts.length === 2) {
    const timePart = parts[1].slice(0, 5); // "15:00"
    const datePart = parts[0].slice(5);    // "06-16"
    return `${datePart} ${timePart}`;
  }
  return tsString;
}

/**
 * Connects the custom HTML legend items with Chart.js dataset toggling
 */
function setupCustomLegend(chart) {
  const legendActual = document.getElementById("legendActual");
  const legendPredicted = document.getElementById("legendPredicted");

  if (legendActual) {
    legendActual.style.cursor = "pointer";
    legendActual.addEventListener("click", () => {
      const idx = chart.data.datasets.findIndex(d => d.label === "Actual Demand");
      if (idx !== -1) {
        const isVisible = chart.isDatasetVisible(idx);
        chart.setDatasetVisibility(idx, !isVisible);
        legendActual.style.opacity = !isVisible ? "1" : "0.35";
        chart.update();
      }
    });
  }

  if (legendPredicted) {
    legendPredicted.style.cursor = "pointer";
    legendPredicted.addEventListener("click", () => {
      const idx = chart.data.datasets.findIndex(d => d.label === "QuickML Predicted");
      if (idx !== -1) {
        const isVisible = chart.isDatasetVisible(idx);
        chart.setDatasetVisibility(idx, !isVisible);
        legendPredicted.style.opacity = !isVisible ? "1" : "0.35";
        chart.update();
      }
    });
  }
}
