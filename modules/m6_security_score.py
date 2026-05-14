"""
M6 · Security Score — 51% Attack Cost Analyser
Estimates the real-time cost of a majority hash-rate attack and visualises
confirmation-depth security (Nakamoto 2008, §11).

FIX aplicado: nakamoto_double_spend_probability usaba math.factorial(k) que
desborda float64 para k grande. Ahora usa scipy.stats.poisson.pmf para el
término de Poisson, que calcula en log-espacio internamente y evita el overflow.
"""

import math
import streamlit as st
import plotly.graph_objects as go
import numpy as np
from scipy.stats import poisson as scipy_poisson

# ── constantes ────────────────────────────────────────────────────────────────
JOULES_PER_TH       = 21.5        # J/TH — Antminer S21 Pro efficiency
WATTS_PER_TH        = JOULES_PER_TH / 1e12 * 1e12   # = 21.5 W/TH
ASIC_COST_PER_TH    = 20.0        # USD/TH — mercado secundario ~2026


# ── helpers ───────────────────────────────────────────────────────────────────
def ehs_to_ths(ehs: float) -> float:
    """Exa-hashes/s → Tera-hashes/s"""
    return ehs * 1e6


def nakamoto_double_spend_probability(q: float, z: int) -> float:
    """
    Probabilidad de éxito de un double-spend con q fracción del hash rate
    y z confirmaciones (Nakamoto 2008, §11).

    FIX: en lugar de calcular sum_k poisson_pmf manualmente con math.factorial
    (que desborda para k grande), usamos scipy.stats.poisson.pmf que opera
    en log-espacio. Esto evita el OverflowError original.

    Args:
        q: fracción hash-rate del atacante (0 < q < 0.5)
        z: número de confirmaciones
    Returns:
        probabilidad de éxito ∈ [0, 1]
    """
    if q <= 0 or q >= 0.5:
        return 1.0 if q >= 0.5 else 0.0

    p = 1.0 - q
    lam = z * (q / p)          # lambda del proceso de Poisson

    # Suma hasta k = z (la víctima lleva z bloques de ventaja)
    total = 0.0
    for k in range(z + 1):
        # scipy.stats.poisson.pmf calcula P(X=k | lambda) en log-espacio → sin overflow
        pk = scipy_poisson.pmf(k, lam)
        # Probabilidad condicional de que el atacante alcance desde k bloques de retraso
        if k <= z:
            total += pk * (1.0 - (q / p) ** (z - k))
        else:
            total += pk

    prob = 1.0 - total
    return max(0.0, min(1.0, prob))


def confirmations_for_safety(q: float, target_prob: float, max_z: int = 200) -> int:
    """
    Número mínimo de confirmaciones para que la probabilidad de double-spend
    esté por debajo de target_prob.
    """
    for z in range(1, max_z + 1):
        if nakamoto_double_spend_probability(q, z) < target_prob:
            return z
    return max_z


# ── render principal ──────────────────────────────────────────────────────────
def render(network_data: dict | None = None):
    """
    Renderiza M6 en Streamlit.
    network_data: dict con claves 'hash_rate_ehs', 'difficulty', 'height'
    Si es None usa valores de ejemplo.
    """
    st.header("M6 · Security Score — 51% Attack Cost Analyser")
    st.caption(
        "Estimates the real-time cost of a majority hash rate attack and visualises "
        "confirmation depth security (Nakamoto 2008, §11)."
    )

    # ── expandable theory ────────────────────────────────────────────────────
    with st.expander("ℹ️ Theory & methodology"):
        st.markdown("""
**51% attack**: An attacker who controls more than 50% of the network hash rate
can, with probability approaching 1, rewrite recent history and double-spend coins.

**Attack cost** is estimated as:
- **Electricity cost**: `attacker_hash_rate (TH/s) × efficiency (W/TH) × electricity_price ($/kWh)`
- **Hardware cost**: `attacker_hash_rate (TH/s) × ASIC_price ($/TH)`

**Nakamoto (2008) §11** gives the probability that an attacker starting z blocks
behind can catch up, as a function of the attacker's hash-rate fraction q:

$$P(z, q) = 1 - \\sum_{k=0}^{z} \\frac{e^{-\\lambda} \\lambda^k}{k!} \\left(1 - \\left(\\frac{q}{1-q}\\right)^{z-k}\\right), \\quad \\lambda = z\\frac{q}{1-q}$$

The Poisson sum is computed via `scipy.stats.poisson.pmf` (log-space) to avoid
numerical overflow for large confirmation depths.
        """)

    # ── live data ────────────────────────────────────────────────────────────
    if network_data:
        hash_rate_ehs = network_data.get("hash_rate_ehs", 948.0)
        difficulty    = network_data.get("difficulty", 132_472_011_079_031)
        height        = network_data.get("height", 949_408)
    else:
        hash_rate_ehs = 948.0
        difficulty    = 132_472_011_079_031
        height        = 949_408

    hash_rate_ths = ehs_to_ths(hash_rate_ehs)

    col1, col2, col3 = st.columns(3)
    col1.metric("Block height",       f"{height:,}")
    col2.metric("Network hash rate",  f"{hash_rate_ehs:.1f} EH/s")
    col3.metric("Difficulty",         f"{difficulty / 1e12:.1f} T")

    # ── 1 · Attack cost calculator ───────────────────────────────────────────
    st.subheader("1 · Attack cost calculator")

    c1, c2, c3 = st.columns(3)
    with c1:
        attacker_pct = st.slider(
            "Attacker hash rate (%)", min_value=10, max_value=51,
            value=30, step=1
        )
    with c2:
        electricity_price = st.number_input(
            "Electricity price (USD/kWh)", min_value=0.01, max_value=0.50,
            value=0.05, step=0.01, format="%.2f"
        )
    with c3:
        btc_price = st.number_input(
            "BTC price (USD)", min_value=10_000, max_value=500_000,
            value=95_000, step=1_000
        )

    attack_ths        = hash_rate_ths * (attacker_pct / 100)
    power_w           = attack_ths * WATTS_PER_TH          # Watts
    power_gw          = power_w / 1e9
    cost_per_hour_usd = power_w / 1000 * electricity_price # kWh × $/kWh
    cost_per_day_usd  = cost_per_hour_usd * 24
    hardware_cost_usd = attack_ths * ASIC_COST_PER_TH

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Attack hash rate", f"{attack_ths / 1e6:.1f} EH/s")
    mc2.metric("Power required",   f"{power_gw:.1f} GW")
    mc3.metric("Cost per hour",    f"${cost_per_hour_usd:,.0f}")
    mc4.metric("Cost per day",     f"${cost_per_day_usd:,.0f}")

    total_barrier_usd = hardware_cost_usd + cost_per_day_usd * 365
    if attacker_pct >= 40:
        security_assessment = "an extremely well-funded state-level actor could theoretically attempt this attack."
    elif attacker_pct >= 30:
        security_assessment = "only the most well-funded state-level attackers could sustain this."
    else:
        security_assessment = "this is economically out of reach for virtually any attacker."

    st.info(
        f"**Hardware cost** (buying ASICs at ~${ASIC_COST_PER_TH}/TH): "
        f"**${hardware_cost_usd / 1e9:.2f}B** one-time capital expense. "
        f"Combined with ${cost_per_day_usd:,.0f}/day in electricity, "
        f"the total annual cost of a {attacker_pct}% attack exceeds "
        f"**${total_barrier_usd / 1e9:.1f}B** — {security_assessment}"
    )

    # Break-even
    st.markdown("**Break-even analysis**")
    st.caption("How much BTC would an attacker need to steal per day to cover costs?")
    daily_blocks        = 144          # 6 blocks/hour × 24h
    block_reward_btc    = 3.125        # post-4th halving
    daily_block_rewards = daily_blocks * block_reward_btc

    btc_to_breakeven = cost_per_day_usd / btc_price if btc_price > 0 else 0

    bc1, bc2, bc3 = st.columns(3)
    bc1.metric("Daily electricity cost",         f"${cost_per_day_usd:,.0f}")
    bc2.metric("BTC needed to break even",       f"{btc_to_breakeven:.2f} BTC/day")
    bc3.metric("Daily block rewards (total net.)",f"{daily_block_rewards:.1f} BTC")

    if btc_to_breakeven > daily_block_rewards:
        st.warning(
            f"With ${electricity_price:.2f}/kWh electricity, stealing all daily "
            f"block rewards ({daily_block_rewards:.0f} BTC) is still not enough to "
            f"break even — the attack is economically irrational."
        )
    else:
        st.warning(
            f"With cheap electricity (${electricity_price:.2f}/kWh), the economics "
            f"are marginal — this underscores the importance of high electricity "
            f"prices as a security parameter."
        )

    # ── 2 · Attack cost vs attacker fraction ────────────────────────────────
    st.subheader("2 · Attack cost vs attacker fraction")
    fractions = np.arange(10, 52, 1)
    hourly_costs = [
        ehs_to_ths(hash_rate_ehs) * (f / 100) * WATTS_PER_TH / 1000 * electricity_price
        for f in fractions
    ]

    fig_cost = go.Figure()
    fig_cost.add_trace(go.Scatter(
        x=fractions, y=hourly_costs,
        mode="lines", fill="tozeroy",
        line=dict(color="crimson", width=2),
        fillcolor="rgba(220,20,60,0.12)",
        name="Hourly electricity cost"
    ))
    fig_cost.add_vline(
        x=attacker_pct, line_dash="dot", line_color="orange",
        annotation_text=f"Selected: {attacker_pct}%",
        annotation_position="top left"
    )
    fig_cost.add_vline(
        x=51, line_dash="dash", line_color="red",
        annotation_text="51% threshold", annotation_position="top right"
    )
    fig_cost.update_layout(
        title="Hourly cost to control X% of Bitcoin's hash rate",
        xaxis_title="Attacker's hash rate fraction (%)",
        yaxis_title="Cost (USD/hour)",
        height=380
    )
    st.plotly_chart(fig_cost, use_container_width=True)

    # ── 3 · Confirmation depth security ─────────────────────────────────────
    st.subheader("3 · Confirmation depth security (Nakamoto 2008, §11)")
    st.caption(
        "Probability of a successful double-spend attack as a function of "
        "the number of confirmations the merchant waits for."
    )

    attacker_qs = [0.10, 0.20, 0.30, 0.40, 0.49]
    colors      = ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#8e44ad"]
    z_values    = list(range(0, 31))

    fig_conf = go.Figure()
    for q_val, color in zip(attacker_qs, colors):
        probs = [nakamoto_double_spend_probability(q_val, z) * 100 for z in z_values]
        fig_conf.add_trace(go.Scatter(
            x=z_values, y=probs,
            mode="lines+markers",
            name=f"q = {int(q_val*100)}% attacker",
            line=dict(color=color, width=2),
            marker=dict(size=5)
        ))

    fig_conf.add_hline(
        y=0.01, line_dash="dash", line_color="gray",
        annotation_text="0.1% risk threshold",
        annotation_position="right"
    )
    fig_conf.add_vline(
        x=6, line_dash="dot", line_color="orange",
        annotation_text="6 conf. (standard)",
        annotation_position="top left"
    )
    fig_conf.update_layout(
        title="Double-spend success probability vs confirmation depth",
        xaxis_title="Number of confirmations (z)",
        yaxis_title="Attack success probability (%)",
        yaxis_type="log",
        yaxis=dict(
            type="log",
            tickformat=".1e",
        ),
        height=420,
        legend=dict(orientation="h", y=1.12)
    )
    st.plotly_chart(fig_conf, use_container_width=True)

    # ── 4 · Recommended confirmations table ─────────────────────────────────
    st.subheader("4 · Recommended confirmations per attacker strength")

    target_probs = {
        "< 1%":    0.01,
        "< 0.1%":  0.001,
        "< 0.01%": 0.0001,
    }

    rows = []
    for q_val in [0.10, 0.20, 0.30, 0.40, 0.49]:
        row = {"Attacker (%)": f"{int(q_val*100)}%"}
        for label, tp in target_probs.items():
            row[label] = confirmations_for_safety(q_val, tp)
        rows.append(row)

    import pandas as pd
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if st.button("🔄 Refresh now", key="m6_refresh"):
        st.rerun()