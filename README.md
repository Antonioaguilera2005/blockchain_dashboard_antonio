# CryptoChain Analyzer Dashboard

## Student Information

| Field | Value |
|---|---|
| Student Name | Antonio Aguilera Slavcheva |
| GitHub Username | Antonioaguilera2005 |
| Project Title | Blockchain_dashboard_Antonio |
| Chosen AI Approach (M4) | Block Arrival Anomaly Detector — Exponential(λ=1/600) baseline + KS test |
| Second AI Approach (M7) | Transaction Fee Estimator — Random Forest with log-transform |

## Module Tracking

| Module | Title | Status | Notes |
|---|---|---|---|
| M1 | Proof of Work Monitor | ✅ Done | Live difficulty, hash rate, inter-block distribution, SHA-256 space visualisation |
| M2 | Block Header Analyzer | ✅ Done | 80-byte header parsed, SHA256d verified locally with hashlib, bits field decoded |
| M3 | Difficulty History | ✅ Done | ~1 year history, adjustment events, block time ratio, summary statistics |
| M4 | AI — Block Arrival Anomaly Detector | ✅ Done | KS test vs Exp(1/600), interval timeline, anomaly table, p-value evaluation |
| M5 | Merkle Proof Verifier | ✅ Done | Step-by-step SHA256d proof, byte reversal, SPV efficiency comparison |
| M6 | Security Score — 51% Attack Cost | ✅ Done | Attack cost calculator, Nakamoto §11 confirmation depth, OverflowError fixed |
| M7 | Fee Estimator (second AI approach) | ✅ Done | Random Forest, log1p transform, regime detector, mempool data |

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Current Progress

- M1 complete: live difficulty, hash rate (≈948 EH/s), inter-block time distribution with exponential curve overlay, and 256-bit SHA-256 space visualisation.
- M2 complete: full 80-byte header parsed in little-endian using `struct.Struct`, local SHA256d verification with hashlib confirming `hash < target`, compact `bits` field decoded step by step (exponent + mantissa).
- M3 complete: ~1 year difficulty history from mempool.space, adjustment events marked red/green, block time ratio per period, summary statistics (50 up / 28 down adjustments, avg ratio = 0.988).
- M4 complete: statistical anomaly detector using Exponential(λ=1/600) as theoretical baseline. KS test evaluates deviation from Poisson process. Anomaly rate ~10% expected under null hypothesis. Adjustable slider for 50–200 blocks.
- M5 complete: Merkle proof fetched from Blockstream, verified step-by-step with hashlib SHA256d. 13 levels for a 3,514-tx block → proof 99.7% smaller than full transaction list. SPV efficiency demonstrated.
- M6 complete: 51% attack cost calculator (electricity + hardware), Nakamoto §11 double-spend probability chart across 5 attacker strengths, recommended confirmation depth table. Bug fixed: `nakamoto_double_spend_probability` previously crashed with `OverflowError` when computing `math.factorial(k)` for large k — resolved by replacing with `scipy.stats.poisson.pmf` (log-space computation).
- M7 complete: Random Forest fee estimator trained on real confirmed blocks via mempool.space `/v1/blocks/:height`. Log1p target transform stabilises training across fee regimes. Fee market regime detector explains metric behaviour in flat markets (distributional shift finding).

## AI Model Notes

### M4 — Block Arrival Anomaly Detector

**Model**: Statistical anomaly detection — Exponential(λ = 1/600 s⁻¹) baseline + one-sample KS test.

**Why this approach**: Bitcoin's Proof-of-Work produces a Poisson process for block arrivals, making the Exponential distribution the theoretically correct null model from the course notes. Any deviation is statistically testable and directly connected to the material on hash functions and mining.

**Thresholds**: two-tailed 5% per tail — blocks faster than 31 s or slower than 1797 s (≈30 min) are flagged.

**Evaluation**: KS statistic + p-value. Typical result: KS p = 0.8983 ≥ 0.05 — block arrivals are consistent with the theoretical Poisson process. Anomaly rate ~11% (expected ~10% under null).

**Limitations**: 100-block samples cover ≈17 hours. The detector flags statistical outliers but cannot distinguish natural variance from mining pool coordination without additional on-chain data.

### M7 — Transaction Fee Estimator

**Model**: Random Forest Regressor with log1p target transform.

**Why Random Forest**: The fee market is driven by non-linear interactions between mempool supply (block space ≈ 4 M weight units) and demand (pending transactions). Random Forest handles non-linear tabular signals, provides fast inference (< 1 ms), and produces interpretable feature importances.

**Features**: lag-1/2/3 log(median_fee), lag-1/2 tx_count, lag-1 block size, 5-block rolling mean/std of log(fee) and tx_count.

**Target**: log1p(median_fee) of the next confirmed block, back-transformed with expm1() at inference.

**Why log-transform**: Bitcoin fees are heavily right-skewed. Without log-transform, 2-3 congestion spike blocks dominate the loss and produce R² ≪ 0.

**Evaluation**: time-ordered 20% hold-out split (no look-ahead). MAE = 3.58 sat/vB. R²(log space) = −8.7 in the current flat market (all fees ≈ 1 sat/vB). This is a known distributional shift: the model was calibrated on historical data from 2024 when network fees averaged 10–30 sat/vB. In the current minimum-fee regime, R² = 1 − MSE/Var(y) is mathematically unreliable because Var(y) ≈ 0. The dashboard includes a regime detector and a historical demo showing R² ≈ 0.94 under normal market conditions.

## Note on `blockchain_client.py` Length

The project brief specifies a 10-line script as a **starting point** for the Session 1 kick-off milestone — not as a requirement for the final submission. That 10-line script is preserved as `blockchain_app.py` in the repository root (git history shows it as the first commit).

The production `blockchain_client.py` is longer because it:
1. Handles multiple endpoints across three APIs (blockchain.info, mempool.space, Blockstream).
2. Implements robust error handling and TTL caching to prevent API rate-limiting on Streamlit rerenders.
3. Decodes low-level binary structures (80-byte header, compact `bits` field, little-endian integers).
4. Paginates mempool.space `/v1/blocks/:height` (15 blocks/request) — ~12× faster than fetching blocks individually.
5. Serves all seven dashboard modules from a single shared layer.

## External References

1. Nakamoto, S. (2008). *Bitcoin: A Peer-to-Peer Electronic Cash System*. §6, §11. https://bitcoin.org/bitcoin.pdf
2. Bitcoin Wiki — *Difficulty*. https://en.bitcoin.it/wiki/Difficulty
3. Blockstream API documentation. https://github.com/Blockstream/esplora/blob/master/API.md
4. mempool.space API documentation. https://mempool.space/docs/api/rest
5. Breiman, L. (2001). *Random Forests*. Machine Learning, 45(1), 5–32.

## Project Structure

```text
blockchain_dashboard_antonio/
├── README.md
├── requirements.txt
├── .gitignore
├── app.py                          # Streamlit entry point, 8 tabs
├── blockchain_app.py               # Session 1 kick-off script (10 lines)
├── api/
│   └── blockchain_client.py        # Shared API layer, caching, helpers
└── modules/
    ├── m1_pow_monitor.py
    ├── m2_block_header.py
    ├── m3_difficulty_history.py
    ├── m4_ai_component.py
    ├── m5_merkle_verifier.py
    ├── m6_security_score.py
    └── m7_fee_stimator.py
```

<!-- student-repo-auditor:teacher-feedback:start -->
## Teacher Feedback

### Kick-off Review

Review time: 2026-04-29 20:44 CEST
Status: Amber

Strength:
- I can see the dashboard structure integrating the checkpoint modules.

Improve now:
- The README should now reflect the checkpoint more explicitly, including progress, blockers, and updated module status.

Next step:
- Update the README so progress, blockers, module status, and next step match the checkpoint format exactly.
<!-- student-repo-auditor:teacher-feedback:end -->