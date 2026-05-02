# Blockchain Dashboard Project

## Student Information

| Field | Value |
|---|---|
| Student Name | Antonio Aguilera Slavcheva |
| GitHub Username | Antonioaguilera2005 |
| Project Title | Blockchain_dashboard_Antonio |
| Chosen AI Approach | Difficulty Predictor using Facebook Prophet |

## Module Tracking

| Module | What it includes | Status |
|---|---|---|
| M1 | Proof of Work Monitor | Done |
| M2 | Block Header Analyzer | Done |
| M3 | Difficulty History | Done |
| M4 | AI Component — Difficulty Predictor (Prophet) | Done |
| M5 | Merkle Proof Verifier | Not started |
| M6 | Security Score — 51% attack cost | Not started |
| M7 | Second AI approach | Not started |
| M8 | On-chain conversational agent (Anthropic API) | Not started |

## Current Progress

- M1 complete: live difficulty, hash rate (948 EH/s), inter-block time distribution with exponential curve overlay, and 256-bit SHA-256 space visualisation. Data from blockchain.info.
- M2 complete: full 80-byte header parsing in little-endian, local SHA256d verification with hashlib confirming hash < target, and compact `bits` field decoded step by step.
- M3 complete: 3-year difficulty history from mempool.space, adjustment events marked in red/green, block time ratio per period, and summary statistics (51 up / 28 down adjustments over the dataset).
- M4 complete: Facebook Prophet model trained on ~78 adjustment periods. Evaluated on a held-out test set of 10 periods. MAPE = 24% — the model correctly captured the long-term upward trend but underestimated the hashrate correction of early 2026, which is consistent with the documented limitations of trend-only time-series models.

## M4 Model Notes

**Model**: Facebook Prophet (Taylor & Letham, 2017)

**Why Prophet**: Bitcoin difficulty has a clear upward trend with irregular changepoints. Prophet handles these automatically without manual feature engineering. The ~14-day adjustment period makes the series regular and well-suited for time-series forecasting. Unlike LSTM, Prophet requires no hyperparameter tuning and trains in seconds on a small dataset.

**Evaluation**: The model was trained on all data except the last 10 adjustment periods (held-out test set). MAE = 33T, MAPE = 24%. The prediction error is explained by a series of downward difficulty adjustments between January and May 2026 — a hashrate shock the model could not anticipate without hashrate as an external feature. This illustrates the fundamental limitation of purely autoregressive models for assets with volatile fundamentals.

**Limitations**:
- Assumes future resembles the past. A sudden hashrate shock causes large prediction errors.
- Small dataset (~80 points). Uncertainty grows quickly beyond 3–4 forecast periods.
- Predicts difficulty value, not direction of change — the latter would require modelling hashrate directly.

## Next Step

- Implement M5: Merkle Proof Verifier — pick a transaction from the latest block and verify its inclusion step by step using hashlib.

## Main Problem or Blocker

- blockchain.info charts API returns empty responses intermittently. Solved by switching difficulty history to mempool.space `/api/v1/mining/difficulty-adjustments/3y`.

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
    |-- m5_merkle_verifier.py      (coming)
    |-- m6_security_score.py       (coming)
    |-- m7_second_ai.py            (coming)
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
