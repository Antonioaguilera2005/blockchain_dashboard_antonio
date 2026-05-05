"""
M4 · AI Component — Block Arrival Anomaly Detector
=====================================================
Streamlit module — exposes render() for app.py.

MODEL CHOICE: Statistical Anomaly Detection
--------------------------------------------
We model inter-block arrival times as an Exponential distribution with
parameter λ = 1/600 s⁻¹ (one block every 600 seconds on average).

This is the THEORETICAL BASELINE from the course notes:
  - Miners attempt hashes independently and memorylessly.
  - The number of attempts follows a Poisson process.
  - Therefore, the time between events (blocks) follows Exp(λ = 1/600).

ANOMALY DEFINITION
------------------
A block is anomalous if its arrival time falls outside the 95th percentile
of the theoretical Exp(1/600) distribution:

    threshold_high = -ln(1 - 0.95) / λ = -ln(0.05) × 600 ≈ 1797 s ≈ 30 min
    threshold_low  = -ln(1 - 0.05) / λ = -ln(0.95) × 600 ≈   31 s

WHAT ANOMALIES CAN INDICATE
-----------------------------
- Very long intervals (>30 min): hashrate drop, large mining pool going
  offline, network partition, or natural statistical variance.
- Very short intervals (<31 s): possible timestamp manipulation, or
  selfish mining behaviour.

EVALUATION METRICS
------------------
- Anomaly rate: % of blocks flagged (expected ~10% under null hypothesis)
- KS test: how much the observed distribution deviates from Exp(1/600)
- Mean and std vs theoretical values (μ = σ = 600 s)
"""

from __future__ import annotations

import math
import time

import streamlit as st

from api.blockchain_client import get_block_interval_timestamps

# ---------------------------------------------------------------------------
# Theoretical Exponential(λ = 1/600) parameters
# ---------------------------------------------------------------------------
LAMBDA           = 1 / 600
MEAN_S           = 600
STD_S            = 600
THRESHOLD_HIGH_S = -math.log(1 - 0.95) / LAMBDA   # ≈ 1797 s ≈ 30 min
THRESHOLD_LOW_S  = -math.log(1 - 0.05) / LAMBDA   # ≈   31 s


def exp_cdf(x: float) -> float:
    return 1 - math.exp(-LAMBDA * x)


def exp_pdf_scaled(x: float, n: int, bin_width: float) -> float:
    """PDF scaled to histogram counts."""
    return LAMBDA * math.exp(-LAMBDA * x) * n * bin_width


def ks_test(intervals: list[float]) -> tuple[float, float]:
    """One-sample KS test against Exp(λ=1/600). Returns (statistic, p_value)."""
    sorted_x = sorted(intervals)
    n = len(sorted_x)
    ks_stat = max(
        abs((i + 1) / n - exp_cdf(x))
        for i, x in enumerate(sorted_x)
    )
    t = (n ** 0.5) * ks_stat
    p_value = 2 * sum(
        ((-1) ** (k + 1)) * math.exp(-2 * k * k * t * t)
        for k in range(1, 101)
    )
    return ks_stat, max(0.0, min(1.0, p_value))


def classify(seconds: float) -> str:
    if seconds > THRESHOLD_HIGH_S:
        return "🔴 SLOW"
    if seconds < THRESHOLD_LOW_S:
        return "🔵 FAST"
    return "🟢 NORMAL"


# ===========================================================================
# Cached fetch
# ===========================================================================

@st.cache_data(ttl=120)
def _fetch_intervals(n_blocks: int) -> list[int]:
    ts = get_block_interval_timestamps(n_blocks)
    return [abs(ts[i] - ts[i + 1]) for i in range(len(ts) - 1)]


# ===========================================================================
# Render
# ===========================================================================

def render() -> None:
    import numpy as np
    import pandas as pd
    import plotly.graph_objects as go

    st.header("M4 · AI Component — Block Arrival Anomaly Detector")
    st.caption(
        "Detects statistically abnormal inter-block times using the "
        "theoretical Exponential(λ = 1/600 s⁻¹) baseline from Proof-of-Work theory."
    )

    with st.expander("ℹ️ Model & theory", expanded=False):
        st.markdown(f"""
**Theoretical baseline**: Under Bitcoin's Proof-of-Work, hash attempts are
independent and memoryless → blocks arrive via a **Poisson process** →
inter-block times follow **Exp(λ = 1/600 s⁻¹)** with μ = σ = 600 s.

**Anomaly thresholds** (two-tailed, 5% per tail):
- 🔵 **Suspiciously fast**: interval < **{THRESHOLD_LOW_S:.0f} s ({THRESHOLD_LOW_S/60:.1f} min)** — bottom 5%
- 🔴 **Suspiciously slow**: interval > **{THRESHOLD_HIGH_S:.0f} s ({THRESHOLD_HIGH_S/60:.0f} min)** — top 5%
- 🟢 **Normal**: central 90%

**What anomalies indicate**:
- Long gaps: hashrate drop, large pool offline, network partition, or natural variance.
- Short gaps: timestamp manipulation or selfish mining (pool withholds blocks strategically).

**Evaluation**: anomaly rate should be ~10% under null hypothesis.
KS test measures deviation from Exp(1/600) — p < 0.05 means significant departure.
        """)

    # ------------------------------------------------------------------
    # Controls & fetch
    # ------------------------------------------------------------------
    n_blocks = st.slider(
        "Blocks to analyse", 50, 200, 100, 10, key="m4_slider"
    )

    with st.spinner(f"Fetching last {n_blocks} block timestamps…"):
        try:
            intervals = _fetch_intervals(n_blocks)
        except Exception as exc:
            st.error(f"Could not fetch data: {exc}")
            return

    ivf    = [float(iv) for iv in intervals]
    n      = len(ivf)
    labels = [classify(iv) for iv in ivf]

    n_slow  = labels.count("🔴 SLOW")
    n_fast  = labels.count("🔵 FAST")
    n_anom  = n_slow + n_fast
    anom_pct = n_anom / n * 100

    mean_obs = sum(ivf) / n
    std_obs  = (sum((x - mean_obs) ** 2 for x in ivf) / n) ** 0.5
    ks_stat, ks_pval = ks_test(ivf)

    # ------------------------------------------------------------------
    # Section 1 — Metrics
    # ------------------------------------------------------------------
    st.subheader("1 · Statistical summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Blocks analysed", n)
    c2.metric("Anomaly rate", f"{anom_pct:.1f}%", help="~10% expected under Poisson")
    c3.metric("🔴 Slow", n_slow)
    c4.metric("🔵 Fast", n_fast)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Observed mean",  f"{mean_obs:.0f} s",
              delta=f"{mean_obs - MEAN_S:+.0f} s vs 600 s")
    c6.metric("Observed std",   f"{std_obs:.0f} s",
              delta=f"{std_obs - STD_S:+.0f} s vs 600 s")
    c7.metric("KS statistic",   f"{ks_stat:.4f}")
    c8.metric("KS p-value",     f"{ks_pval:.4f}")

    if ks_pval < 0.05:
        st.warning(
            f"⚠️ **KS p-value = {ks_pval:.4f} < 0.05** — the observed distribution "
            f"significantly deviates from Exp(1/600). Possible mining pool coordination "
            f"or recent hashrate event."
        )
    else:
        st.success(
            f"✅ **KS p-value = {ks_pval:.4f} ≥ 0.05** — block arrivals are consistent "
            f"with the theoretical Poisson process."
        )

    # ------------------------------------------------------------------
    # Section 2 — Timeline
    # ------------------------------------------------------------------
    st.subheader("2 · Interval timeline")
    st.caption("Red = slow anomaly  |  Blue = fast anomaly  |  Green = normal")

    color_map = {"🔴 SLOW": "#ef4444", "🔵 FAST": "#3b82f6", "🟢 NORMAL": "#22c55e"}
    colors = [color_map[l] for l in labels]

    fig_t = go.Figure()
    fig_t.add_trace(go.Bar(
        x=list(range(n)),
        y=[iv / 60 for iv in ivf],
        marker_color=colors,
        hovertemplate="Block %{x}<br>%{y:.1f} min<extra></extra>",
    ))
    fig_t.add_hline(y=THRESHOLD_HIGH_S / 60, line_dash="dash",
                    line_color="#ef4444",
                    annotation_text=f"Slow threshold ({THRESHOLD_HIGH_S/60:.0f} min)")
    fig_t.add_hline(y=THRESHOLD_LOW_S / 60, line_dash="dash",
                    line_color="#3b82f6",
                    annotation_text=f"Fast threshold ({THRESHOLD_LOW_S/60:.1f} min)")
    fig_t.add_hline(y=10, line_dash="dot", line_color="gray",
                    annotation_text="Target 10 min")
    fig_t.update_layout(
        xaxis_title="Block index (0 = most recent)",
        yaxis_title="Interval (minutes)",
        template="plotly_white", showlegend=False,
    )
    st.plotly_chart(fig_t, use_container_width=True)

    # ------------------------------------------------------------------
    # Section 3 — Distribution vs theoretical
    # ------------------------------------------------------------------
    st.subheader("3 · Observed distribution vs Exp(1/600)")

    max_iv   = max(ivf)
    bin_w    = max_iv / 25
    x_range  = np.linspace(0, max_iv * 1.05, 300)
    pdf_vals = [exp_pdf_scaled(x, n, bin_w) for x in x_range]

    fig_d = go.Figure()
    fig_d.add_trace(go.Histogram(
        x=[iv / 60 for iv in ivf], nbinsx=25,
        name="Observed", marker_color="#f7931a", opacity=0.75,
    ))
    fig_d.add_trace(go.Scatter(
        x=[x / 60 for x in x_range], y=pdf_vals,
        mode="lines", name="Exp(λ=1/10 min) theoretical",
        line=dict(color="#6366f1", width=2, dash="dash"),
    ))
    fig_d.add_vline(x=THRESHOLD_HIGH_S / 60, line_dash="dash",
                    line_color="#ef4444", annotation_text="Slow threshold")
    fig_d.add_vline(x=THRESHOLD_LOW_S / 60, line_dash="dash",
                    line_color="#3b82f6", annotation_text="Fast threshold")
    fig_d.update_layout(
        xaxis_title="Time between blocks (minutes)",
        yaxis_title="Count",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_d, use_container_width=True)

    # ------------------------------------------------------------------
    # Section 4 — Anomaly table
    # ------------------------------------------------------------------
    st.subheader("4 · Detected anomalies")

    anom_rows = [
        {
            "Block index":    i,
            "Interval (s)":   f"{iv:.0f}",
            "Interval (min)": f"{iv/60:.1f}",
            "Type":           lbl,
            "Percentile":     f"{exp_cdf(iv)*100:.1f}%",
        }
        for i, (iv, lbl) in enumerate(zip(ivf, labels))
        if lbl != "🟢 NORMAL"
    ]

    if anom_rows:
        st.dataframe(pd.DataFrame(anom_rows),
                     use_container_width=True, hide_index=True)
        st.caption(
            f"{len(anom_rows)} anomalies in {n} intervals ({anom_pct:.1f}%). "
            f"Under a pure Poisson process, ~10% is expected by chance."
        )
    else:
        st.success("No anomalies detected in this sample.")

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    st.divider()
    if st.button("🔄 Refresh now", key="m4_refresh"):
        st.cache_data.clear()
        st.rerun()