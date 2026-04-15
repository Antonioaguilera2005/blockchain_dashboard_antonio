"""Starter file for module M1."""

import streamlit as st

from api.blockchain_client import get_latest_block


def render() -> None:
    """Render the M1 panel."""
    st.header("M1 - Proof of Work Monitor")
    st.write("Use this module to show live Bitcoin mining data.")
    st.write("Suggested ideas:")
    st.write("- latest block height")
    st.write("- block hash")
    st.write("- difficulty")
    st.write("- nonce")
    st.write("- number of transactions")

    if st.button("Fetch latest block", key="m1_fetch"):
        with st.spinner("Fetching data..."):
            try:
                block = get_latest_block()
                st.success(f"Block height: {block.get('height')}")
                st.json(block)
            except Exception as exc:
                st.error(f"Error fetching data: {exc}")
    else:
        st.info("Click the button to test the API connection.")
