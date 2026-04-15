"""Starter file for module M2."""

import streamlit as st

from api.blockchain_client import get_block


def render() -> None:
    """Render the M2 panel."""
    st.header("M2 - Block Header Analyzer")
    st.write("Use this module to inspect the fields of one block header.")

    block_hash = st.text_input(
        "Block hash",
        placeholder="Enter a block hash",
        key="m2_hash",
    )

    if st.button("Look up block", key="m2_lookup") and block_hash:
        with st.spinner("Fetching data..."):
            try:
                block = get_block(block_hash)
                st.subheader("Block header fields")
                header_fields = {
                    "Hash": block.get("hash"),
                    "Height": block.get("height"),
                    "Time": block.get("time"),
                    "Nonce": block.get("nonce"),
                    "Bits": block.get("bits"),
                    "Merkle root": block.get("mrkl_root"),
                    "Previous block": block.get("prev_block"),
                }
                for label, value in header_fields.items():
                    st.write(f"**{label}:** {value}")
            except Exception as exc:
                st.error(f"Error fetching block: {exc}")
    elif not block_hash:
        st.info("Enter a block hash and click Look up block.")
