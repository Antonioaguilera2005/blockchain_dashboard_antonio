"""
M5 · Merkle Proof Verifier
===========================
Streamlit module — exposes render() for app.py.

What this module does:
  1. Fetches the latest block and picks a transaction from it.
  2. Retrieves the Merkle proof (sibling hashes) for that transaction.
  3. Verifies step by step that hashing up the tree produces the
     Merkle root stored in the block header.
  4. Shows every hash computation so the verification is fully transparent.

THEORY — MERKLE TREES IN BITCOIN
----------------------------------
Bitcoin stores all transactions in a block as a binary Merkle tree:

    level 0 (leaves): SHA256d(tx_0), SHA256d(tx_1), ..., SHA256d(tx_n)
    level 1:          SHA256d(hash_0 || hash_1), SHA256d(hash_2 || hash_3), ...
    ...
    root:             single 32-byte hash stored in the block header

To prove that tx_i is in the block WITHOUT downloading all transactions,
you only need log2(n) sibling hashes — the Merkle proof.  Each step:

    current = SHA256d(current || sibling)   if sibling is on the right
    current = SHA256d(sibling || current)   if sibling is on the left

If the final result equals the Merkle root in the header, the transaction
is provably included in the block.

BYTE ORDER NOTE
---------------
Bitcoin displays hashes in reversed byte order (big-endian) for human
readability, but computes them internally in little-endian.  We reverse
all hashes before concatenating and reverse back for display.

API: Blockstream /block/{hash}/txid/{index} and /block/{hash}/merkle-proof
"""

from __future__ import annotations

import hashlib

import requests
import streamlit as st

from api.blockchain_client import get_latest_block

BLOCKSTREAM = "https://blockstream.info/api"


# ===========================================================================
# Merkle helpers
# ===========================================================================

def sha256d(data: bytes) -> bytes:
    """Bitcoin double-SHA256."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def merkle_step(current_hex: str, sibling_hex: str, position: str) -> tuple[str, str]:
    """
    One step up the Merkle tree.

    Args:
        current_hex: current hash (big-endian hex)
        sibling_hex: sibling hash (big-endian hex)
        position:    'left' if current is left child, 'right' if right child

    Returns:
        (parent_hex, computation_str) — parent hash and human-readable step
    """
    # Convert to little-endian bytes for hashing
    current_le = bytes.fromhex(current_hex)[::-1]
    sibling_le = bytes.fromhex(sibling_hex)[::-1]

    if position == "left":
        combined = current_le + sibling_le
        label = f"SHA256d( current || sibling )"
    else:
        combined = sibling_le + current_le
        label = f"SHA256d( sibling || current )"

    parent_le  = sha256d(combined)
    parent_hex = parent_le[::-1].hex()

    computation = (
        f"{label}\n"
        f"  current : {current_hex}\n"
        f"  sibling : {sibling_hex}\n"
        f"  → parent: {parent_hex}"
    )
    return parent_hex, computation


# ===========================================================================
# API helpers
# ===========================================================================

@st.cache_data(ttl=300)
def _fetch_proof(block_hash: str, tx_index: int) -> dict | None:
    try:
        # Get txid at this index
        r_txid = requests.get(
            f"{BLOCKSTREAM}/block/{block_hash}/txid/{tx_index}", timeout=10
        )
        r_txid.raise_for_status()
        txid = r_txid.text.strip().strip('"')

        # Correct endpoint: /tx/{txid}/merkle-proof
        r_proof = requests.get(
            f"{BLOCKSTREAM}/tx/{txid}/merkle-proof", timeout=10
        )
        r_proof.raise_for_status()
        proof_data = r_proof.json()
        # Returns: {"block_height": N, "merkle": [...], "pos": N}
        return {
            "txid":     txid,
            "siblings": proof_data.get("merkle", []),
            "pos":      proof_data.get("pos", tx_index),
        }
    except Exception as exc:
        return {"error": str(exc)}


@st.cache_data(ttl=30)
def _fetch_block_info() -> dict:
    block = get_latest_block()
    return {
        "hash":        block["hash"],
        "height":      block["height"],
        "n_tx":        block["n_tx"],
        "merkle_root": block["mrkl_root"],
    }


# ===========================================================================
# Verification logic
# ===========================================================================

def verify_merkle_proof(
    txid: str,
    siblings: list[str],
    pos: int,
    expected_root: str,
) -> tuple[bool, list[dict]]:
    """
    Walk up the Merkle tree and verify the proof.

    Returns (valid, steps) where steps is a list of dicts for display.
    """
    steps = []

    # The leaf hash is SHA256d(txid_bytes_le) reversed → but Blockstream
    # already gives us the txid in display order (reversed).
    # The Merkle leaf = txid reversed to internal order, then SHA256d, reversed back.
    # Actually for Merkle proofs, the leaf IS the txid in internal byte order.
    # Blockstream's merkle-proof expects us to start with the txid directly.
    current = txid
    index   = pos

    steps.append({
        "level":       0,
        "description": "Starting hash (transaction ID)",
        "hash":        current,
        "is_leaf":     True,
    })

    for level, sibling in enumerate(siblings, start=1):
        # Determine position: if index is even, current is left child
        position = "left" if (index % 2 == 0) else "right"
        parent, computation = merkle_step(current, sibling, position)

        steps.append({
            "level":       level,
            "description": f"Level {level} — current is {'left' if position=='left' else 'right'} child",
            "computation": computation,
            "hash":        parent,
            "sibling":     sibling,
            "position":    position,
            "is_leaf":     False,
        })

        current = parent
        index   = index // 2

    valid = current.lower() == expected_root.lower()
    return valid, steps


# ===========================================================================
# Streamlit render
# ===========================================================================

def render() -> None:
    st.header("M5 · Merkle Proof Verifier")
    st.caption(
        "Picks a transaction from the latest block and verifies its "
        "inclusion in the Merkle tree step by step using hashlib."
    )

    with st.expander("ℹ️ What is a Merkle proof?", expanded=False):
        st.markdown("""
A **Merkle tree** is a binary hash tree where each leaf is a transaction hash
and each internal node is `SHA256d(left_child || right_child)`.
The root is stored in every block header.

A **Merkle proof** lets you verify that a transaction is in a block by providing
only `log₂(n)` sibling hashes — without downloading the entire block.

**Verification steps**:
1. Start with the transaction ID (leaf).
2. At each level, concatenate with the sibling and hash: `SHA256d(left || right)`.
3. If the final hash equals the Merkle root in the header → **transaction is proven included**.

This is what SPV (Simplified Payment Verification) wallets use — they verify
payments without running a full node.
        """)

    # ------------------------------------------------------------------
    # Fetch latest block
    # ------------------------------------------------------------------
    with st.spinner("Fetching latest block…"):
        try:
            info = _fetch_block_info()
        except Exception as exc:
            st.error(f"Could not fetch block: {exc}")
            return

    col1, col2, col3 = st.columns(3)
    col1.metric("Block height", f"{info['height']:,}")
    col2.metric("Transactions", f"{info['n_tx']:,}")
    col3.metric("Block hash", info["hash"][:16] + "…")

    st.markdown("**Merkle root** (from block header):")
    st.code(info["merkle_root"], language=None)

    # ------------------------------------------------------------------
    # Transaction selector
    # ------------------------------------------------------------------
    st.subheader("Select a transaction to verify")

    max_idx = info["n_tx"] - 1
    tx_index = st.number_input(
        f"Transaction index (0 = coinbase, max = {max_idx})",
        min_value=0, max_value=max_idx, value=1, step=1,
        key="m5_tx_index",
    )

    if st.button("🔍 Fetch proof and verify", key="m5_verify"):
        with st.spinner(f"Fetching Merkle proof for transaction #{tx_index}…"):
            proof = _fetch_proof(info["hash"], int(tx_index))

        if not proof or "error" in proof:
            st.error(f"Could not fetch proof: {proof.get('error', 'unknown error')}")
            return

        txid     = proof["txid"]
        siblings = proof["siblings"]
        pos      = proof["pos"]

        st.subheader("1 · Transaction ID")
        st.code(txid, language=None)
        st.caption(
            f"Position in block: #{pos}  |  "
            f"Proof depth: {len(siblings)} levels  |  "
            f"Covers ~{2**len(siblings):,} leaf slots"
        )

        # ------------------------------------------------------------------
        # Run verification
        # ------------------------------------------------------------------
        valid, steps = verify_merkle_proof(txid, siblings, pos, info["merkle_root"])

        st.subheader("2 · Verification steps")
        st.caption(
            "Each step concatenates the current hash with its sibling and "
            "computes SHA256(SHA256( left || right )) to move one level up the tree."
        )

        for step in steps:
            level = step["level"]
            if step["is_leaf"]:
                with st.expander(f"Level 0 — Transaction leaf", expanded=True):
                    st.code(step["hash"], language=None)
                    st.caption("This is the transaction ID — the starting leaf of the proof.")
            else:
                expanded = (level == len(steps) - 1)  # expand last step
                with st.expander(
                    f"Level {level} — {step['description']}", expanded=expanded
                ):
                    st.code(step["computation"], language=None)
                    col_a, col_b = st.columns(2)
                    col_a.markdown(f"**Result hash:**")
                    col_a.code(step["hash"][:32] + "…", language=None)

        # ------------------------------------------------------------------
        # Final result
        # ------------------------------------------------------------------
        st.subheader("3 · Verification result")

        computed_root = steps[-1]["hash"] if len(steps) > 1 else txid
        st.code(
            f"Computed root : {computed_root}\n"
            f"Header root   : {info['merkle_root']}\n\n"
            f"Match         : {'✅  YES — proof is VALID' if valid else '❌  NO — proof is INVALID'}",
            language=None,
        )

        if valid:
            st.success(
                f"✅ **Merkle proof verified.** "
                f"Transaction #{tx_index} (`{txid[:16]}…`) is provably included "
                f"in block {info['height']:,}. "
                f"The proof required only {len(siblings)} hashes instead of "
                f"all {info['n_tx']:,} transactions."
            )
        else:
            st.error(
                "❌ Proof verification failed — the computed root does not match "
                "the Merkle root in the block header."
            )

        # ------------------------------------------------------------------
        # Efficiency note
        # ------------------------------------------------------------------
        st.subheader("4 · Efficiency of Merkle proofs")
        import math
        proof_size_bytes = (len(siblings) + 1) * 32
        full_block_bytes = info["n_tx"] * 32
        saving_pct = (1 - proof_size_bytes / full_block_bytes) * 100 if full_block_bytes else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Proof size",      f"{proof_size_bytes} bytes ({len(siblings)} hashes)")
        col2.metric("Full tx list",    f"{full_block_bytes:,} bytes ({info['n_tx']:,} hashes)")
        col3.metric("Data saved",      f"{saving_pct:.1f}%")

        st.info(
            f"A Merkle proof scales as **O(log₂ n)** — for this block with "
            f"{info['n_tx']:,} transactions, only **{len(siblings)} hashes** "
            f"({proof_size_bytes} bytes) are needed instead of the full "
            f"{full_block_bytes:,}-byte transaction list. "
            f"This is the foundation of Bitcoin's SPV (light client) protocol."
        )

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    st.divider()
    if st.button("🔄 Refresh block", key="m5_refresh"):
        st.cache_data.clear()
        st.rerun()