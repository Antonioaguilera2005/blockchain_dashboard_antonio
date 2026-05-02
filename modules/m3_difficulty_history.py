"""
M3 · Difficulty History
========================
Streamlit module — exposes render() for app.py.

What this module does:
  1. Plots the evolution of Bitcoin's mining difficulty over the last year.
  2. Marks each difficulty adjustment event on the chart.
  3. Shows the ratio (actual_block_time / 600 s) for each adjustment period,
     which is exactly the correction factor Bitcoin's protocol applies.

THEORY — HOW THE ADJUSTMENT WORKS (Section 6.1 of the course notes)
---------------------------------------------------------------------
Every 2016 blocks (~2 weeks at 10 min/block) the network recomputes the
target using this formula:

    new_target = old_target × (actual_time / expected_time)

where expected_time = 2016 × 600 s = 1,209,600 s (two weeks).

Equivalently:
    new_difficulty = old_difficulty × (expected_time / actual_time)

If blocks arrived faster than 10 min → actual_time < expected_time
    → ratio < 1 → new_target is smaller → difficulty goes UP.

If blocks arrived slower than 10 min → ratio > 1 → difficulty goes DOWN.

Bitcoin caps the adjustment at a factor of 4× in either direction per
period to prevent runaway oscillations.

The ratio (actual / expected) is therefore the KEY metric: values close
to 1.0 mean the network is healthy; large deviations reveal hashrate
shocks (e.g. the China mining ban of May 2021 pushed the ratio to ~2,
triggering the largest downward adjustment in Bitcoin's history).
"""

from __future__ import annotations

import time

import streamlit as st

from api.blockchain_client import get_difficulty_history

# Expected inter-block time and period length (Bitcoin protocol constants)
TARGET_BLOCK_TIME_S = 600          # 10 minutes
BLOCKS_PER_PERIOD   = 2016
EXPECTED_PERIOD_S   = TARGET_BLOCK_TIME_S * BLOCKS_PER_PERIOD  # 1,209,600 s


# ===========================================================================
# Data helpers
# ===========================================================================


@st.cache_data(ttl=600)
def _fetch_history(n_points: int = 100) -> list[dict]:
    """
    Fetch the last n_points difficulty data points.
    Each point: {"x": unix_timestamp, "y": difficulty_value}
    Cached for 10 minutes — difficulty adjusts every ~2 weeks.
    """
    return get_difficulty_history(n_points=n_points)


def _compute_ratios(history: list[dict]) -> list[dict]:
    """
    Compute block time ratio for each adjustment period.
    
    Bitcoin's adjustment formula: new_difficulty = old_difficulty * (expected / actual)
    Inverted: ratio = actual / expected = old_difficulty / new_difficulty
    
    If ratio < 1: blocks arrived faster than 10 min → difficulty went UP (correct)
    If ratio > 1: blocks arrived slower than 10 min → difficulty went DOWN (correct)
    """
    ratios = []
    for i in range(1, len(history)):
        old_diff = history[i - 1]["y"]
        new_diff = history[i]["y"]
        
        if old_diff == 0:
            continue
            
        # ratio = old / new because: new = old * (expected/actual) → actual/expected = old/new
        ratio = old_diff / new_diff
        
        # Estimate actual period duration from timestamps
        actual_time = history[i]["x"] - history[i - 1]["x"]
        actual_days = actual_time / 86400
        
        ratios.append({
            "x": history[i]["x"],
            "difficulty": new_diff,
            "ratio": ratio,
            "actual_days": actual_days,
            "direction": "▲ UP" if new_diff > old_diff else "▼ DOWN",
        })
    return ratios


# ===========================================================================
# Streamlit render
# ===========================================================================


def render() -> None:
    """Draw the M3 Difficulty History tab."""

    st.header("M3 · Difficulty History")
    st.caption(
        "Evolution of Bitcoin's mining difficulty over the last year. "
        "One data point ≈ one adjustment period (2016 blocks ≈ 14 days)."
    )

    with st.spinner("Fetching difficulty history…"):
        history = _fetch_history(n_points=100)

    if not history:
        st.error("Could not fetch difficulty history from blockchain.info.")
        return

    ratios = _compute_ratios(history)

    # ------------------------------------------------------------------
    # Section 1 — Difficulty over time
    # ------------------------------------------------------------------
    st.subheader("1 · Difficulty over time")

    import plotly.graph_objects as go

    timestamps = [h["x"] for h in history]
    difficulties = [h["y"] for h in history]
    dates = [time.strftime("%Y-%m-%d", time.gmtime(t)) for t in timestamps]

    fig_diff = go.Figure()

    # Main difficulty line
    fig_diff.add_trace(go.Scatter(
        x=dates,
        y=difficulties,
        mode="lines",
        name="Difficulty",
        line=dict(color="#f7931a", width=2),
        fill="tozeroy",
        fillcolor="rgba(247,147,26,0.15)",
    ))

    # Mark each adjustment event as a vertical dot
    adj_colors = [
    "#ef4444" if r["direction"] == "▲ UP" else "#22c55e"
    for r in ratios
]
    adj_dates = [time.strftime("%Y-%m-%d", time.gmtime(r["x"])) for r in ratios]
    adj_diffs  = [r["difficulty"] for r in ratios]

    fig_diff.add_trace(go.Scatter(
        x=adj_dates,
        y=adj_diffs,
        mode="markers",
        name="Adjustment event",
        marker=dict(color=adj_colors, size=8, symbol="diamond"),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Difficulty: %{y:,.0f}<br>"
            "<extra></extra>"
        ),
    ))

    fig_diff.update_layout(
        title="Bitcoin Mining Difficulty (last ~1 year)",
        xaxis_title="Date",
        yaxis_title="Difficulty",
        yaxis_tickformat=".3s",   # e.g. 130T
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    st.plotly_chart(fig_diff, use_container_width=True)

    st.caption(
        "🔴 Red diamond = difficulty **increased** (blocks were arriving too fast).  "
        "🟢 Green diamond = difficulty **decreased** (blocks were arriving too slow)."
    )

    # ------------------------------------------------------------------
    # Section 2 — Actual/expected time ratio per period
    # ------------------------------------------------------------------
    st.subheader("2 · Actual block time ratio per adjustment period")
    st.caption(
        "Ratio = actual time to mine 2016 blocks ÷ expected time (14 days).  \n"
        "A ratio of **1.0** means perfect 10-minute blocks.  \n"
        "**< 1** → miners were faster → difficulty went UP next period.  \n"
        "**> 1** → miners were slower → difficulty went DOWN next period."
    )

    ratio_dates  = [time.strftime("%Y-%m-%d", time.gmtime(r["x"])) for r in ratios]
    ratio_values = [r["ratio"] for r in ratios]
    bar_colors   = [
        "#ef4444" if v < 1 else "#22c55e"
        for v in ratio_values
    ]

    fig_ratio = go.Figure()

    # Ratio bars
    fig_ratio.add_trace(go.Bar(
        x=ratio_dates,
        y=ratio_values,
        name="Actual/Expected ratio",
        marker_color=bar_colors,
        opacity=0.8,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Ratio: %{y:.3f}<br>"
            "<extra></extra>"
        ),
    ))

    # Reference line at 1.0
    fig_ratio.add_hline(
        y=1.0,
        line_dash="dash",
        line_color="white",
        annotation_text="Target = 1.0 (10 min/block)",
        annotation_position="top left",
    )

    # Bitcoin protocol cap lines at 0.25 and 4.0
    fig_ratio.add_hline(
        y=4.0, line_dash="dot", line_color="#f87171",
        annotation_text="Max adjustment cap (×4)",
        annotation_position="top right",
    )
    fig_ratio.add_hline(
        y=0.25, line_dash="dot", line_color="#f87171",
        annotation_text="Min adjustment cap (÷4)",
        annotation_position="bottom right",
    )

    fig_ratio.update_layout(
        title="Block time ratio per difficulty adjustment period",
        xaxis_title="Adjustment date",
        yaxis_title="Ratio (actual / expected)",
        template="plotly_dark",
        showlegend=False,
    )
    st.plotly_chart(fig_ratio, use_container_width=True)

    # ------------------------------------------------------------------
    # Section 3 — Adjustment table (last 10 periods)
    # ------------------------------------------------------------------
    st.subheader("3 · Recent adjustment periods (last 10)")

    import pandas as pd

    table_data = [
        {
            "Date": time.strftime("%Y-%m-%d", time.gmtime(r["x"])),
            "Difficulty": f"{r['difficulty']:,.0f}",
            "Period duration (days)": f"{r['actual_days']:.1f}",
            "Ratio": f"{r['ratio']:.4f}",
            "Direction": r["direction"],
        }
        for r in ratios[-10:]
    ]
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # Section 4 — Key stats
    # ------------------------------------------------------------------
    st.subheader("4 · Summary statistics")

    col1, col2, col3, col4 = st.columns(4)

    latest_diff = history[-1]["y"]
    max_diff    = max(h["y"] for h in history)
    min_diff    = min(h["y"] for h in history)
    avg_ratio   = sum(r["ratio"] for r in ratios) / len(ratios) if ratios else 1.0
    n_up   = sum(1 for r in ratios if r["ratio"] < 1)
    n_down = sum(1 for r in ratios if r["ratio"] > 1)

    col1.metric("Current difficulty", f"{latest_diff / 1e12:.2f} T")
    col2.metric("1-year high",        f"{max_diff / 1e12:.2f} T")
    col3.metric("1-year low",         f"{min_diff / 1e12:.2f} T")
    col4.metric("Avg block time ratio", f"{avg_ratio:.3f}")

    st.info(
        f"Over the last year: **{n_up} upward adjustments** (blocks too fast) "
        f"and **{n_down} downward adjustments** (blocks too slow).  \n"
        f"Average ratio = {avg_ratio:.3f} "
        f"({'slightly above' if avg_ratio > 1 else 'slightly below'} the 1.0 target — "
        f"the network is {'mining a bit slower' if avg_ratio > 1 else 'mining a bit faster'} "
        f"than the 10-minute target on average)."
    )

    # ------------------------------------------------------------------
    # Refresh button
    # ------------------------------------------------------------------
    st.divider()
    if st.button("🔄 Refresh now", key="m3_refresh"):
        st.cache_data.clear()
        st.rerun()