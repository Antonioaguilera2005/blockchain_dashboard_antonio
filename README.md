# Blockchain Dashboard Project

## Student Information

| Field | Value |
|---|---|
| Student Name | Antonio Aguilera Slavcheva |
| GitHub Username | Antonioaguilera2005 |
| Project Title | Blockchain_dashboard_Antonio |
| Chosen AI Approach | Block Arrival Anomaly Detector (Exponential baseline + KS test) |

## Module Tracking

| Module | What it includes | Status |
|---|---|---|
| M1 | Proof of Work Monitor | Done |
| M2 | Block Header Analyzer | Done |
| M3 | Difficulty History | Done |
| M4 | AI Component — Block Arrival Anomaly Detector | Done |
| M5 | Merkle Proof Verifier | Done |
| M6 | Security Score — 51% attack cost | In progress |
| M7 | Fee Estimator (second AI approach) | Not started |
| M8 | On-chain conversational agent (Anthropic API) | Not started |

## Current Progress

- M1 complete: live difficulty, hash rate (948 EH/s), inter-block time distribution with exponential curve overlay, and 256-bit SHA-256 space visualisation.
- M2 complete: full 80-byte header parsed in little-endian, local SHA256d verification with hashlib confirming hash < target, compact `bits` field decoded step by step.
- M3 complete: 3-year difficulty history from mempool.space, adjustment events marked red/green, block time ratio per period, summary statistics (51 up / 28 down adjustments).
- M4 complete: statistical anomaly detector using Exponential(λ=1/600) as theoretical baseline. KS test evaluates deviation from Poisson process. Anomaly rate ~10% expected under null hypothesis. Adjustable slider for 50–200 blocks.
- M5 complete: Merkle proof fetched from Blockstream, verified step by step with hashlib SHA256d. 13 levels for a 4,743-tx block → 448 bytes proof vs 151,776 bytes full list (99.7% saving). SPV efficiency demonstrated.

## M4 Model Notes

**Model**: Statistical Anomaly Detection — Exponential(λ = 1/600 s⁻¹) baseline

**Why this approach**: Bitcoin's Proof-of-Work produces a Poisson process for block arrivals, making the Exponential distribution the theoretically correct null model from the course notes. Any deviation is statistically testable and directly connected to the material on hash functions and mining.

**Thresholds**: two-tailed 5% per tail — blocks faster than 31 s or slower than 1797 s (30 min) are flagged as anomalies.

**Evaluation**: KS test statistic and p-value. Anomaly rate ~10% under null hypothesis. Typical results: p-value ≥ 0.05, confirming block arrivals are consistent with a Poisson process.

**Limitations**: small samples (~100 blocks ≈ 17 hours) may not capture rare network events. The detector flags statistical outliers but cannot distinguish natural variance from genuine mining pool behaviour without additional on-chain data.

## Technical Notes

- `blockchain_client.py`: shared API layer for M1–M8. Uses blockchain.info for block data, mempool.space for difficulty history and block timestamp pages (15 blocks/request → ~12× faster), and Blockstream for Merkle proofs.
- All modules expose a `render()` function consumed by `app.py` via Streamlit tabs.
- In-memory TTL cache prevents repeated API calls on Streamlit rerenders.

## Next Step

- Implement M6: Security Score — estimate the cost in USD/hour of a 51% attack using live hash rate data, and visualise how confirmation depth reduces attack probability (Nakamoto 2008, §11).

## Main Problem or Blocker

- No current blockers. Previous issues resolved: blockchain.info charts API → switched to mempool.space. Block timestamp fetch latency → solved with paged API (~12× faster).

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Project Structure

```text
blockchain_dashboard_antonio/
|-- README.md
|-- requirements.txt
|-- .gitignore
|-- app.py
|-- api/
|   `-- blockchain_client.py
`-- modules/
    |-- m1_pow_monitor.py
    |-- m2_block_header.py
    |-- m3_difficulty_history.py
    |-- m4_ai_component.py
    |-- m5_merkle_verifier.py
    |-- m6_security_score.py       (in progress)
    |-- m7_fee_estimator.py        (coming)
    `-- m8_onchain_agent.py        (coming)
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