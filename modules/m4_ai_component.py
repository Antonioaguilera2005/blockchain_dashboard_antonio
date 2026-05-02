"""
M4 · AI Component — Difficulty Predictor
==========================================
Streamlit module — exposes render() for app.py.

MODEL CHOICE: Facebook Prophet
-------------------------------
We use Prophet (Taylor & Letham, 2017) for the following reasons:

1. The difficulty time series has a clear upward trend with occasional
   reversals — Prophet models trend changes automatically via changepoints.

2. Difficulty adjustments happen on a fixed schedule (~14 days), making
   the series regular and well-suited for time-series forecasting.

3. Prophet is interpretable: it decomposes the forecast into trend +
   seasonality components, which we can explain and visualise.

4. Unlike LSTM, Prophet requires no hyperparameter tuning and trains
   in seconds on small datasets (~80 data points over 3 years).

EVALUATION
----------
We use a time-series cross-validation approach:
  - Training set: all points except the last 10
  - Test set: last 10 adjustment periods (~20 weeks)
  - Metrics: MAE (Mean Absolute Error) and MAPE (Mean Absolute Percentage Error)

LIMITATIONS (required in the report)
--------------------------------------
- Prophet assumes the future resembles the past. A sudden hashrate shock
  (e.g. a country banning mining, a new ASIC generation) would cause a
  large prediction error.
- The dataset is small (~80 points over 3 years). More data would help
  but difficulty only started being significant around 2017.
- We predict the difficulty value, not the change direction — the latter
  would require modelling hashrate directly.
"""

from __future__ import annotations

from io import StringIO
import time
from turtle import pd
from unittest import result
import warnings

import streamlit as st

warnings.filterwarnings("ignore")  # suppress Prophet/cmdstanpy output

from api.blockchain_client import get_difficulty_history

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ADJUSTMENT_PERIOD_DAYS = 14   # one Bitcoin difficulty adjustment ≈ 14 days
N_FORECAST_PERIODS     = 6    # predict next 6 adjustment periods (~12 weeks)
N_TEST_PERIODS         = 10   # last 10 periods held out for evaluation


# ===========================================================================
# Data helpers
# ===========================================================================

@st.cache_data(ttl=600)
def _fetch_history() -> list[dict]:
    """Fetch full difficulty history (3 years) for model training."""
    return get_difficulty_history(n_points=150)


def _prepare_dataframe(history: list[dict]):
    """Convert history to a pandas DataFrame in Prophet format (ds, y)."""
    import pandas as pd
    import numpy as np

    df = pd.DataFrame(history)
    df["ds"] = pd.to_datetime(df["x"], unit="s")
    df["y"]  = df["y"].astype(float)

    # Prophet works better on log scale for exponentially growing series
    df["y_log"] = np.log(df["y"])

    return df.sort_values("ds").reset_index(drop=True)


# ===========================================================================
# Model training and forecasting
# ===========================================================================

@st.cache_data(ttl=600)
def _train_and_forecast(history_json: str):
    """
    Train Prophet on difficulty history and return forecast + evaluation.

    We pass history as a JSON string so st.cache_data can hash it.
    """
    import json
    import numpy as np
    import pandas as pd
    from prophet import Prophet

    history = json.loads(history_json)
    df = _prepare_dataframe(history)

    if len(df) < N_TEST_PERIODS + 5:
        return None

    # ------------------------------------------------------------------
    # Train / test split
    # ------------------------------------------------------------------
    train_df = df.iloc[:-N_TEST_PERIODS].copy()
    test_df  = df.iloc[-N_TEST_PERIODS:].copy()

    # ------------------------------------------------------------------
    # Train Prophet on log-transformed difficulty
    # ------------------------------------------------------------------
    model = Prophet(
        changepoint_prior_scale=0.3,   # allow moderate trend changes
        seasonality_mode="additive",
        daily_seasonality=False,
        weekly_seasonality=False,
        yearly_seasonality=False,      # ~26 adjustments/year is too sparse
        interval_width=0.90,           # 90% confidence interval
    )
    model.fit(train_df[["ds", "y_log"]].rename(columns={"y_log": "y"}))

    # ------------------------------------------------------------------
    # In-sample test: predict the held-out test periods
    # ------------------------------------------------------------------
    test_forecast = model.predict(test_df[["ds"]])
    test_pred_log = test_forecast["yhat"].values
    test_actual   = test_df["y_log"].values

    # Back-transform from log scale
    test_pred = np.exp(test_pred_log)
    test_real = np.exp(test_actual)

    mae  = float(np.mean(np.abs(test_pred - test_real)))
    mape = float(np.mean(np.abs((test_pred - test_real) / test_real)) * 100)

    # ------------------------------------------------------------------
    # Retrain on full dataset for future forecast
    # ------------------------------------------------------------------
    full_model = Prophet(
        changepoint_prior_scale=0.3,
        seasonality_mode="additive",
        daily_seasonality=False,
        weekly_seasonality=False,
        yearly_seasonality=False,
        interval_width=0.90,
    )
    full_model.fit(df[["ds", "y_log"]].rename(columns={"y_log": "y"}))

    # Future dataframe: one row per adjustment period
    future = full_model.make_future_dataframe(
        periods=N_FORECAST_PERIODS,
        freq=f"{ADJUSTMENT_PERIOD_DAYS}D",
    )
    forecast = full_model.predict(future)

    # Back-transform all forecast values
    forecast["yhat_actual"]        = np.exp(forecast["yhat"])
    forecast["yhat_lower_actual"]  = np.exp(forecast["yhat_lower"])
    forecast["yhat_upper_actual"]  = np.exp(forecast["yhat_upper"])

    return {
        "df":           df.to_json(),
        "train_df":     train_df.to_json(),
        "test_df":      test_df.to_json(),
        "forecast":     forecast[["ds", "yhat_actual",
                                   "yhat_lower_actual",
                                   "yhat_upper_actual"]].to_json(),
        "test_pred":    test_pred.tolist(),
        "test_real":    test_real.tolist(),
        "test_dates":   test_df["ds"].dt.strftime("%Y-%m-%d").tolist(),
        "mae":          mae,
        "mape":         mape,
    }


# ===========================================================================
# Streamlit render
# ===========================================================================

def render() -> None:
    """Draw the M4 AI Component tab."""
    import json
    import numpy as np
    import pandas as pd
    import plotly.graph_objects as go

    st.header("M4 · AI Component — Difficulty Predictor")
    st.caption(
        "Uses Facebook Prophet to forecast the next Bitcoin difficulty "
        "adjustments based on historical data."
    )

    # ------------------------------------------------------------------
    # Model info box
    # ------------------------------------------------------------------
    with st.expander("ℹ️ About the model", expanded=False):
        st.markdown("""
**Model**: Facebook Prophet (Taylor & Letham, 2017)

**Why Prophet?**
- Bitcoin difficulty follows a clear upward trend with occasional reversals — Prophet handles trend changepoints automatically.
- Adjustments happen on a fixed ~14-day schedule, making the series regular and predictable.
- Interpretable: decomposes forecast into trend + components.
- Trains in seconds on our ~80-point dataset with no hyperparameter tuning.

**Training data**: last 3 years of difficulty adjustments (~78 periods) from mempool.space

**Evaluation**: held-out test set = last 10 adjustment periods (~20 weeks)

**Metrics**: MAE (Mean Absolute Error), MAPE (Mean Absolute Percentage Error)

**Limitations**:
- Assumes future resembles the past. A sudden hashrate shock (mining ban, new ASIC generation) would cause large errors.
- Small dataset (~80 points). The model captures trend well but uncertainty grows quickly beyond 3–4 periods.
- We predict the difficulty *value*, not the direction of change — the latter would require modelling hashrate directly.
        """)

    # ------------------------------------------------------------------
    # Fetch data and train
    # ------------------------------------------------------------------
    with st.spinner("Fetching difficulty history and training Prophet…"):
        history = _fetch_history()
        if not history:
            st.error("Could not fetch difficulty history.")
            return
        result = _train_and_forecast(json.dumps(history))

    if result is None:
        st.error("Not enough data to train the model (need at least 15 adjustment periods).")
        return

    from io import StringIO
    df       = pd.read_json(StringIO(result["df"]))
    forecast = pd.read_json(StringIO(result["forecast"]))
    test_df  = pd.read_json(StringIO(result["test_df"]))

    df["ds"]       = pd.to_datetime(df["ds"], unit="ms")
    forecast["ds"] = pd.to_datetime(forecast["ds"], unit="ms")
    test_df["ds"]  = pd.to_datetime(test_df["ds"], unit="ms")

    mae  = result["mae"]
    mape = result["mape"]

    # ------------------------------------------------------------------
    # Section 1 — Forecast chart
    # ------------------------------------------------------------------
    st.subheader("1 · Difficulty forecast (next 6 adjustment periods ≈ 12 weeks)")

    fig = go.Figure()

    # Historical data
    fig.add_trace(go.Scatter(
        x=df["ds"], y=df["y"],
        mode="lines+markers",
        name="Historical difficulty",
        line=dict(color="#f7931a", width=2),
        marker=dict(size=4),
    ))

    # Confidence interval (only for forecast region)
    future_mask = forecast["ds"] > df["ds"].max()
    fc_future = forecast[future_mask]

    fig.add_trace(go.Scatter(
        x=pd.concat([fc_future["ds"], fc_future["ds"].iloc[::-1]]),
        y=pd.concat([fc_future["yhat_upper_actual"],
                     fc_future["yhat_lower_actual"].iloc[::-1]]),
        fill="toself",
        fillcolor="rgba(99,102,241,0.2)",
        line=dict(color="rgba(255,255,255,0)"),
        name="90% confidence interval",
        showlegend=True,
    ))

    # Forecast line (all periods including fitted)
    fig.add_trace(go.Scatter(
        x=forecast["ds"], y=forecast["yhat_actual"],
        mode="lines",
        name="Prophet forecast",
        line=dict(color="#6366f1", width=2, dash="dash"),
    ))

    # Mark the train/test split
    split_date = test_df["ds"].min()
    fig.add_vline(
        x=split_date.timestamp() * 1000,
        line_dash="dot", line_color="gray",
        annotation_text="Train/test split",
        annotation_position="top left",
    )

    fig.update_layout(
        title="Bitcoin Difficulty — Historical + Prophet Forecast",
        xaxis_title="Date",
        yaxis_title="Difficulty",
        yaxis_tickformat=".2s",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------------------------------
    # Section 2 — Model evaluation
    # ------------------------------------------------------------------
    st.subheader("2 · Model evaluation on held-out test set")
    st.caption(
        f"The model was trained on all data except the last {N_TEST_PERIODS} "
        f"adjustment periods, which were used exclusively for evaluation."
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("MAE", f"{mae/1e12:.2f} T",
                help="Mean Absolute Error — average prediction error in difficulty units")
    col2.metric("MAPE", f"{mape:.1f}%",
                help="Mean Absolute Percentage Error — average % prediction error")
    col3.metric("Test periods", str(N_TEST_PERIODS))

    # Interpretation
    if mape < 5:
        quality = "🟢 Excellent"
        explanation = "The model predicts difficulty within 5% on average — strong performance for a time-series forecast."
    elif mape < 10:
        quality = "🟡 Good"
        explanation = "The model predicts difficulty within 10% on average — acceptable for planning purposes."
    else:
        quality = "🟠 Moderate"
        explanation = "Prediction error exceeds 10% — likely due to a hashrate shock during the test period."

    st.info(f"**{quality}** — {explanation}")

    # Predicted vs actual chart for test set
    fig_eval = go.Figure()

    fig_eval.add_trace(go.Scatter(
        x=result["test_dates"],
        y=[v / 1e12 for v in result["test_real"]],
        mode="lines+markers",
        name="Actual difficulty (T)",
        line=dict(color="#f7931a", width=2),
        marker=dict(size=8),
    ))

    fig_eval.add_trace(go.Scatter(
        x=result["test_dates"],
        y=[v / 1e12 for v in result["test_pred"]],
        mode="lines+markers",
        name="Prophet prediction (T)",
        line=dict(color="#6366f1", width=2, dash="dash"),
        marker=dict(size=8, symbol="diamond"),
    ))

    fig_eval.update_layout(
        title=f"Actual vs Predicted — last {N_TEST_PERIODS} adjustment periods",
        xaxis_title="Date",
        yaxis_title="Difficulty (T)",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_eval, use_container_width=True)

    # ------------------------------------------------------------------
    # Section 3 — Next adjustment predictions table
    # ------------------------------------------------------------------
    st.subheader("3 · Predicted next difficulty adjustments")

    future_forecasts = forecast[forecast["ds"] > df["ds"].max()].head(N_FORECAST_PERIODS)

    table_rows = []
    for _, row in future_forecasts.iterrows():
        table_rows.append({
            "Predicted date":       row["ds"].strftime("%Y-%m-%d"),
            "Predicted difficulty": f"{row['yhat_actual']/1e12:.2f} T",
            "Lower bound (90%)":    f"{row['yhat_lower_actual']/1e12:.2f} T",
            "Upper bound (90%)":    f"{row['yhat_upper_actual']/1e12:.2f} T",
        })

    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    st.caption(
        "Bounds represent the 90% confidence interval — there is a 90% probability "
        "the actual difficulty will fall within these bounds, assuming no structural "
        "break in the hashrate trend."
    )

    # ------------------------------------------------------------------
    # Refresh button
    # ------------------------------------------------------------------
    st.divider()
    if st.button("🔄 Refresh now", key="m4_refresh"):
        st.cache_data.clear()
        st.rerun()