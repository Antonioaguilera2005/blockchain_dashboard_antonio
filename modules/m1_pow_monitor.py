"""
M1 · Proof of Work Monitor
===========================
Streamlit module — exposes a single  render()  function that draws the
complete M1 tab inside the dashboard.

Displays:
  1. Current difficulty + visual threshold in the 256-bit SHA-256 space.
  2. Inter-block time distribution (expected: Exponential(λ=1/600 s)).
  3. Estimated network hash rate.

Run standalone (for quick testing from the project root):
    python -m modules.m1_pow_monitor
"""

from __future__ import annotations

import math
import time

import streamlit as st

# ---------------------------------------------------------------------------
# Import from the api package.
# Always run from the project root so Python finds the 'api' package:
#     streamlit run app.py              ← correct
#     python -m modules.m1_pow_monitor  ← correct
# Never run as:  python modules/m1_pow_monitor.py  (breaks relative imports)
# ---------------------------------------------------------------------------
from api.blockchain_client import (
    get_block,
    get_block_interval_timestamps,
    get_difficulty_history,
    get_latest_block,
)


# ===========================================================================
# Pure cryptographic helpers (no Streamlit dependency)
# ===========================================================================


def bits_to_target(bits: int) -> int:
    """
    Decode the compact 'bits' field from a block header into the full
    256-bit target integer.

        target = mantissa × 256^(exponent − 3)

    where the top byte of `bits` is the exponent and the lower 3 bytes
    are the mantissa.
    """
    exponent = (bits >> 24) & 0xFF
    mantissa = bits & 0x007FFFFF
    return mantissa * (256 ** (exponent - 3))


def target_to_leading_zero_bits(target: int) -> float:
    """
    Return the approximate number of leading zero *bits* required by target.

    Derivation: if the target is T, then on average 2^256 / T hashes are
    needed — equivalent to log2(2^256 / T) leading zero bits.
    """
    if target <= 0:
        return 256.0
    max256 = (1 << 256) - 1
    return math.log2(max256 / target)


def estimate_hashrate(difficulty: float) -> float:
    """
    Network hash rate in hashes/second.

    Formula: H = difficulty × 2^32 / 600
    (Bitcoin targets one block per 600 s; expected hashes = difficulty × 2^32)
    """
    return difficulty * (2**32) / 600.0


def format_hashrate(h: float) -> str:
    """Return a human-readable hash rate string."""
    if h >= 1e18:
        return f"{h / 1e18:.2f} EH/s"
    if h >= 1e15:
        return f"{h / 1e15:.2f} PH/s"
    if h >= 1e12:
        return f"{h / 1e12:.2f} TH/s"
    return f"{h:.2e} H/s"


# ===========================================================================
# Data-fetching helpers (cached so Streamlit reruns don't hit the API)
# ===========================================================================


@st.cache_data(ttl=30)
def _fetch_latest_stats() -> dict:
    """Fetch latest block and return a flat dict of the metrics we need."""
    latest = get_latest_block()
    block = get_block(latest["hash"])

    bits = block["bits"]
    difficulty = block["difficulty"]
    target = bits_to_target(bits)

    return {
        "height": block["height"],
        "hash": block["hash"],
        "bits": bits,
        "difficulty": difficulty,
        "n_tx": block["n_tx"],
        "timestamp": block["time"],
        "target": target,
        "leading_zero_bits": target_to_leading_zero_bits(target),
        "hash_rate": estimate_hashrate(difficulty),
    }


@st.cache_data(ttl=120)
def _fetch_intervals(n_blocks: int = 50) -> list[int]:
    """
    Return the list of inter-block intervals (seconds) for the last n_blocks.
    Cached for 2 minutes — this is the slow call (n_blocks+1 HTTP requests).
    """
    timestamps = get_block_interval_timestamps(n_blocks)
    return [abs(timestamps[i] - timestamps[i + 1]) for i in range(len(timestamps) - 1)]


@st.cache_data(ttl=600)
def _fetch_difficulty_history() -> list[dict]:
    return get_difficulty_history(n_points=100)


# ===========================================================================
# Streamlit render function — called by app.py
# ===========================================================================


def render() -> None:
    """Draw the M1 Proof of Work Monitor tab."""

    st.header("M1 · Proof of Work Monitor")
    st.caption("Live data from blockchain.info — refreshes every 30 s")

    # ------------------------------------------------------------------
    # Section 1 — Latest block overview
    # ------------------------------------------------------------------
    with st.spinner("Fetching latest block…"):
        stats = _fetch_latest_stats()

    col1, col2, col3 = st.columns(3)
    col1.metric("Block height", f"{stats['height']:,}")
    col2.metric("Transactions", f"{stats['n_tx']:,}")
    col3.metric(
        "Mined at",
        time.strftime("%H:%M:%S UTC", time.gmtime(stats["timestamp"])),
    )

    st.subheader("Block hash")
    st.code(stats["hash"], language=None)

    # Observation box — connects hash to theory
    leading_hex = len(stats["hash"]) - len(stats["hash"].lstrip("0"))
    st.info(
        f"**Leading hex zeros in this hash: {leading_hex}** "
        f"(= {leading_hex * 4} zero bits).  "
        f"The current target requires ≈ **{stats['leading_zero_bits']:.1f} leading zero bits**, "
        f"meaning miners had to try on average **2^{stats['leading_zero_bits']:.1f}** hashes "
        f"to find a valid block."
    )

    # ------------------------------------------------------------------
    # Section 2 — Difficulty & target threshold
    # ------------------------------------------------------------------
    st.subheader("Difficulty & 256-bit target threshold")

    col_a, col_b = st.columns(2)
    col_a.metric("Difficulty", f"{stats['difficulty']:,.0f}")
    col_b.metric("bits field", f"0x{stats['bits']:08x}")

    target_hex = f"{stats['target']:064x}"
    st.markdown("**Decoded 256-bit target (hex):**")
    st.code(f"{target_hex[:32]}\n{target_hex[32:]}", language=None)

    # Visual bar: 64 hex chars = 256 bits
    zero_hex_chars = int(stats["leading_zero_bits"] / 4)
    bar = "0" * zero_hex_chars + "·" * (64 - zero_hex_chars)
    st.markdown("**SHA-256 space visualisation** (64 hex chars = 256 bits)")
    st.markdown(
        f"`{bar}`  \n"
        f"Legend: `0` = must be zero &nbsp;|&nbsp; `·` = any value  \n"
        f"Required leading zeros ≈ {stats['leading_zero_bits']:.1f} bits "
        f"({zero_hex_chars} hex chars)"
    )

    # ------------------------------------------------------------------
    # Section 3 — Estimated hash rate
    # ------------------------------------------------------------------
    st.subheader("Estimated network hash rate")
    st.metric("Hash rate", format_hashrate(stats["hash_rate"]))
    st.caption("Formula: difficulty × 2³² ÷ 600 s")

    # ------------------------------------------------------------------
    # Section 4 — Inter-block time distribution
    # ------------------------------------------------------------------
    st.subheader("Inter-block time distribution (last 50 blocks)")
    st.caption(
        "Expected distribution: Exponential(λ = 1/600 s⁻¹) — "
        "blocks arrive via a memoryless Poisson process, "
        "so intervals are exponentially distributed with mean 600 s."
    )

    with st.spinner("Fetching last 50 block timestamps… (may take ~30 s on first load)"):
        try:
            intervals = _fetch_intervals(n_blocks=50)
        except Exception as exc:
            st.error(f"Could not fetch interval data: {exc}")
            intervals = []

    if intervals:
        import numpy as np
        import plotly.graph_objects as go

        intervals_min = [iv / 60 for iv in intervals]
        mean_min = sum(intervals_min) / len(intervals_min)

        fig = go.Figure()

        # Histogram of observed intervals
        fig.add_trace(
            go.Histogram(
                x=intervals_min,
                nbinsx=20,
                name="Observed intervals",
                marker_color="#f7931a",  # Bitcoin orange
                opacity=0.75,
            )
        )

        # Theoretical exponential PDF overlay (scaled to histogram counts)
        x_range = np.linspace(0, max(intervals_min) * 1.1, 200)
        lambda_ = 1 / 10  # per minute
        bin_width = max(intervals_min) / 20
        pdf_scaled = lambda_ * np.exp(-lambda_ * x_range) * len(intervals) * bin_width
        fig.add_trace(
            go.Scatter(
                x=x_range,
                y=pdf_scaled,
                mode="lines",
                name="Exp(λ=1/10 min) theoretical",
                line=dict(color="#ffffff", dash="dash", width=2),
            )
        )

        fig.update_layout(
            title=f"Inter-block intervals — mean = {mean_min:.1f} min (target: 10 min)",
            xaxis_title="Time between blocks (minutes)",
            yaxis_title="Count",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Mean interval", f"{mean_min:.1f} min")
        col2.metric("Min interval", f"{min(intervals_min):.1f} min")
        col3.metric("Max interval", f"{max(intervals_min):.1f} min")

    # ------------------------------------------------------------------
    # Manual refresh button
    # ------------------------------------------------------------------
    st.divider()
    if st.button("🔄 Refresh now", key="m1_refresh"):
        st.cache_data.clear()
        st.rerun()


# ===========================================================================
# Standalone entry point — run as:  python -m modules.m1_pow_monitor
# ===========================================================================

def main() -> None:
    """Quick console output — useful for debugging without launching Streamlit."""
    print("Fetching latest block stats…")
    stats = _fetch_latest_stats()
    target_hex = f"{stats['target']:064x}"

    print(f"\n  Height     : {stats['height']:,}")
    print(f"  Hash       : {stats['hash']}")
    print(f"  Difficulty : {stats['difficulty']:,.0f}")
    print(f"  bits       : 0x{stats['bits']:08x}")
    print(f"  Target     : {target_hex}")
    print(f"  Zero bits  : {stats['leading_zero_bits']:.1f}")
    print(f"  Hash rate  : {format_hashrate(stats['hash_rate'])}")

    print("\nFetching intervals (slow — ~30 s)…")
    intervals = _fetch_intervals(30)
    mean_s = sum(intervals) / len(intervals)
    print(f"  Mean inter-block time: {mean_s:.1f} s ({mean_s/60:.2f} min)")
    print("Done.")


if __name__ == "__main__":
    main()