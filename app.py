"""Simple Streamlit entry point for the student project."""

import streamlit as st

from modules.m1_pow_monitor import render as render_m1
from modules.m2_block_header import render as render_m2
from modules.m3_difficulty_history import render as render_m3
from modules.m4_ai_component import render as render_m4

st.set_page_config(page_title="Blockchain Dashboard", layout="wide")

st.title("Blockchain Dashboard")

tab1, tab2, tab3, tab4 = st.tabs(
    ["M1 - PoW Monitor", "M2 - Block Header", "M3 - Difficulty History", "M4 - AI Component"]
)

with tab1:
    render_m1()

with tab2:
    render_m2()

with tab3:
    render_m3()

with tab4:
    render_m4()
