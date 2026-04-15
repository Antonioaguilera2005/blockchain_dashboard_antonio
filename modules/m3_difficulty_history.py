"""Starter file for module M3."""

import pandas as pd
import plotly.express as px
import streamlit as st

from api.blockchain_client import get_difficulty_history


def render() -> None:
    """Render the M3 panel."""
    st.header("M3 - Difficulty History")
    st.write("Use this module to plot the history of Bitcoin difficulty.")

    n_points = st.slider("Number of data points", min_value=10, max_value=365, value=100, key="m3_n")

    if st.button("Load difficulty chart", key="m3_load"):
        with st.spinner("Fetching data..."):
            try:
                values = get_difficulty_history(n_points)
                df = pd.DataFrame(values)
                df["x"] = pd.to_datetime(df["x"], unit="s")
                df = df.rename(columns={"x": "Date", "y": "Difficulty"})

                fig = px.line(df, x="Date", y="Difficulty", title="Bitcoin Mining Difficulty")
                st.plotly_chart(fig, use_container_width=True)
            except Exception as exc:
                st.error(f"Error loading chart: {exc}")
    else:
        st.info("Click Load difficulty chart to display the chart.")
