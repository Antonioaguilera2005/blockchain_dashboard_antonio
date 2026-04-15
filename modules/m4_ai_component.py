"""Starter file for module M4."""

import streamlit as st


def render() -> None:
    """Render the M4 panel."""
    st.header("M4 - AI Component")
    st.info("Use this module for your AI idea.")

    st.subheader("Suggested steps")
    st.markdown(
        """
        1. Choose one AI approach.
        2. Explain it in the README.
        3. Show the result in this tab.
        """
    )
