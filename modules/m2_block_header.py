"""
M2 · Block Header Analyzer
============================
Streamlit module — exposes render() for app.py.

What this module does:
  1. Fetches the raw 80-byte Bitcoin block header for the latest block.
  2. Parses all six fields (version, prev_hash, merkle_root, timestamp,
     bits, nonce) respecting little-endian byte order.
  3. Recomputes SHA256(SHA256(header)) locally with hashlib and verifies
     the result is below the current target — exactly what every Bitcoin
     full node does when it validates a new block.
  4. Counts leading zero bits in the hash and shows the full verification
     step clearly.

WHY LITTLE-ENDIAN MATTERS
--------------------------
Bitcoin serialises multi-byte integers in little-endian order (least
significant byte first).  When you reverse the bytes of prev_hash or
merkle_root, you get the human-readable big-endian hex you see on block
explorers.  If you forget this step, your locally computed hash will not
match the one the network agrees on — a classic source of bugs.

HOW SHA256d VERIFICATION WORKS
--------------------------------
Bitcoin defines a valid block as one where:
    SHA256(SHA256(header_bytes)) < target

Both rounds of SHA-256 are applied to the same 80 raw bytes.  We use
Python's hashlib — no external crypto library needed.  This demonstrates
that Bitcoin's Proof-of-Work is purely a hash comparison, nothing magic.
"""

from __future__ import annotations

import hashlib
import struct
import time

import streamlit as st

from api.blockchain_client import get_block, get_latest_block, bits_to_target


# ===========================================================================
# Header parsing — 80 bytes, all fields little-endian
# ===========================================================================

# Bitcoin block header layout (80 bytes total):
#   Offset  Size  Field
#   0       4     version        (int32, little-endian)
#   4       32    prev_hash      (bytes, displayed reversed = big-endian)
#   36      32    merkle_root    (bytes, displayed reversed = big-endian)
#   68      4     timestamp      (uint32, little-endian, Unix epoch)
#   72      4     bits           (uint32, little-endian, compact target)
#   76      4     nonce          (uint32, little-endian)
HEADER_STRUCT = struct.Struct("<I32s32sIII")  # 4+32+32+4+4+4 = 80 bytes


def build_header_bytes(block: dict) -> bytes:
    """
    Reconstruct the 80-byte block header from the fields returned by the API.

    The API returns hashes as big-endian hex strings (human-readable).
    We must reverse them to little-endian bytes before packing, because
    that is how Bitcoin serialises them internally.
    """
    version = block["ver"]
    # prev_block and mrkl_root are big-endian hex → reverse to little-endian
    prev_hash_le = bytes.fromhex(block["prev_block"])[::-1]
    merkle_root_le = bytes.fromhex(block["mrkl_root"])[::-1]
    timestamp = block["time"]
    bits = block["bits"]
    nonce = block["nonce"]

    return HEADER_STRUCT.pack(version, prev_hash_le, merkle_root_le,
                               timestamp, bits, nonce)


def parse_header(raw: bytes) -> dict:
    """
    Parse 80 raw header bytes into a dict with human-readable field values.
    All multi-byte fields are converted back to big-endian for display.
    """
    version, prev_le, merkle_le, timestamp, bits, nonce = HEADER_STRUCT.unpack(raw)
    return {
        "version": version,
        "prev_hash": prev_le[::-1].hex(),      # back to big-endian for display
        "merkle_root": merkle_le[::-1].hex(),  # back to big-endian for display
        "timestamp": timestamp,
        "bits": bits,
        "nonce": nonce,
    }


# ===========================================================================
# Proof-of-Work verification
# ===========================================================================


def sha256d(data: bytes) -> bytes:
    """Bitcoin's double-SHA256: SHA256(SHA256(data))."""
    first = hashlib.sha256(data).digest()
    return hashlib.sha256(first).digest()


def verify_pow(header_bytes: bytes, bits: int) -> dict:
    """
    Verify that SHA256(SHA256(header_bytes)) < target(bits).

    Returns a dict with:
        hash_hex        — the computed hash as big-endian hex (for display)
        hash_int        — the hash as a 256-bit integer (for comparison)
        target          — the target as a 256-bit integer
        target_hex      — the target as a 64-char hex string
        valid           — True if hash < target
        leading_zero_bits — number of leading zero bits in the hash
    """
    # SHA256d returns bytes in little-endian order (Bitcoin convention).
    # We reverse for display so it matches block explorers (big-endian).
    hash_le = sha256d(header_bytes)
    hash_be = hash_le[::-1]
    hash_hex = hash_be.hex()
    hash_int = int.from_bytes(hash_be, "big")

    target = bits_to_target(bits)
    target_hex = f"{target:064x}"

    # Count leading zero bits
    leading_zero_bits = 0
    for byte in hash_be:
        if byte == 0:
            leading_zero_bits += 8
        else:
            # Count remaining zero bits in this byte
            leading_zero_bits += 8 - byte.bit_length()
            break

    return {
        "hash_hex": hash_hex,
        "hash_int": hash_int,
        "target": target,
        "target_hex": target_hex,
        "valid": hash_int < target,
        "leading_zero_bits": leading_zero_bits,
    }


# ===========================================================================
# Cached data fetch
# ===========================================================================


@st.cache_data(ttl=30)
def _fetch_block_data() -> dict:
    """Fetch latest block and build/verify its header. Cached 30 s."""
    latest = get_latest_block()
    block = get_block(latest["hash"])

    header_bytes = build_header_bytes(block)
    fields = parse_header(header_bytes)
    pow_result = verify_pow(header_bytes, block["bits"])

    return {
        "block_hash": block["hash"],
        "height": block["height"],
        "n_tx": block["n_tx"],
        "header_hex": header_bytes.hex(),
        "header_bytes": list(header_bytes),  # list so st.cache_data can serialise
        "fields": fields,
        "pow": pow_result,
    }


# ===========================================================================
# Streamlit render
# ===========================================================================


def render() -> None:
    """Draw the M2 Block Header Analyzer tab."""

    st.header("M2 · Block Header Analyzer")
    st.caption(
        "Parses the 80-byte Bitcoin block header and verifies "
        "Proof-of-Work locally using hashlib — no external libraries."
    )

    with st.spinner("Fetching latest block…"):
        data = _fetch_block_data()

    fields = data["fields"]
    pow_r = data["pow"]

    # ------------------------------------------------------------------
    # Block overview
    # ------------------------------------------------------------------
    col1, col2, col3 = st.columns(3)
    col1.metric("Block height", f"{data['height']:,}")
    col2.metric("Transactions", f"{data['n_tx']:,}")
    col3.metric(
        "Mined at",
        time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(fields["timestamp"])),
    )

    # ------------------------------------------------------------------
    # Section 1 — Raw 80-byte header
    # ------------------------------------------------------------------
    st.subheader("1 · Raw 80-byte header")
    st.caption(
        "These are the exact bytes that miners hash billions of times per second. "
        "Only the last 4 bytes (nonce) change between attempts."
    )

    header_hex = data["header_hex"]
    # Display in rows of 16 bytes (32 hex chars) for readability
    rows = [header_hex[i:i+32] for i in range(0, len(header_hex), 32)]
    annotated = "\n".join(
        f"  [{i*16:02d}-{min(i*16+15, 79):02d}]  {row}"
        for i, row in enumerate(rows)
    )
    st.code(annotated, language=None)

    # ------------------------------------------------------------------
    # Section 2 — Parsed fields
    # ------------------------------------------------------------------
    st.subheader("2 · Parsed header fields")
    st.caption(
        "All multi-byte integers are stored in **little-endian** format in "
        "the raw bytes, then converted to big-endian for display here "
        "(matching what block explorers show)."
    )

    # Build a table
    field_rows = [
        ("version", f"{fields['version']} (0x{fields['version']:08x})",
         "4 bytes · int32 · little-endian"),
        ("prev_hash", fields["prev_hash"][:32] + "…",
         "32 bytes · SHA-256 of previous block header"),
        ("merkle_root", fields["merkle_root"][:32] + "…",
         "32 bytes · root of transaction Merkle tree"),
        ("timestamp", (f"{fields['timestamp']} "
                       f"({time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(fields['timestamp']))})"),
         "4 bytes · uint32 · Unix epoch"),
        ("bits", f"0x{fields['bits']:08x}",
         "4 bytes · compact target encoding"),
        ("nonce", f"{fields['nonce']:,} (0x{fields['nonce']:08x})",
         "4 bytes · the value miners iterate over"),
    ]

    col_field, col_value, col_desc = st.columns([1, 3, 4])
    col_field.markdown("**Field**")
    col_value.markdown("**Value**")
    col_desc.markdown("**Description**")
    st.divider()
    for fname, fval, fdesc in field_rows:
        c1, c2, c3 = st.columns([1, 3, 4])
        c1.markdown(f"`{fname}`")
        c2.markdown(f"`{fval}`")
        c3.caption(fdesc)

    # Show full hashes in expandable section
    with st.expander("Show full prev_hash and merkle_root"):
        st.markdown("**prev_hash** (big-endian, as seen on block explorers):")
        st.code(fields["prev_hash"], language=None)
        st.markdown("**merkle_root** (big-endian):")
        st.code(fields["merkle_root"], language=None)

    # ------------------------------------------------------------------
    # Section 3 — Proof-of-Work verification
    # ------------------------------------------------------------------
    st.subheader("3 · Proof-of-Work verification")
    st.caption(
        "We recompute SHA256(SHA256(header)) locally and check that the "
        "result is below the target encoded in `bits`. "
        "This is the single check every Bitcoin full node performs."
    )

    # Show the computation step by step
    st.markdown("**Step 1 — Compute SHA256d locally (Python hashlib):**")
    st.code(
        "import hashlib\n\n"
        "round1 = hashlib.sha256(header_bytes).digest()   # first SHA-256\n"
        "round2 = hashlib.sha256(round1).digest()         # second SHA-256\n"
        "hash_le = round2                                  # little-endian bytes\n"
        "hash_be = hash_le[::-1]                          # reverse → big-endian",
        language="python",
    )

    st.markdown("**Step 2 — Result (our locally computed hash):**")
    st.code(pow_r["hash_hex"], language=None)

    leading_hex = len(pow_r["hash_hex"]) - len(pow_r["hash_hex"].lstrip("0"))
    st.info(
        f"**{leading_hex} leading hex zeros = {pow_r['leading_zero_bits']} leading zero bits.**  "
        f"Each hex zero represents 4 bits that had to be zero — miners tried "
        f"on average 2^{pow_r['leading_zero_bits']} ≈ "
        f"{2**pow_r['leading_zero_bits']:.2e} hashes to find this nonce."
    )

    st.markdown("**Step 3 — Compare with the 256-bit target:**")
    target_hex = pow_r["target_hex"]
    st.code(
        f"hash  (our result) = {pow_r['hash_hex']}\n"
        f"target (from bits) = {target_hex}\n\n"
        f"hash < target  →  {'✅  VALID — hash is below target' if pow_r['valid'] else '❌  INVALID'}",
        language=None,
    )

    if pow_r["valid"]:
        st.success(
            "✅ **Proof-of-Work verified locally.** "
            "The hash we computed from the raw header bytes is below the target — "
            "confirming this block required genuine computational work."
        )
    else:
        st.error(
            "❌ Something went wrong — the locally computed hash is not below the target. "
            "This should never happen with a real Bitcoin block."
        )

    # ------------------------------------------------------------------
    # Section 4 — bits field decoded
    # ------------------------------------------------------------------
    st.subheader("4 · The `bits` field decoded")
    bits = fields["bits"]
    exponent = (bits >> 24) & 0xFF
    mantissa = bits & 0x007FFFFF
    st.markdown(
        f"The compact `bits` value **0x{bits:08x}** encodes the target as:  \n"
        f"- **Exponent** (top byte): `0x{exponent:02x}` = {exponent}  \n"
        f"- **Mantissa** (lower 3 bytes): `0x{mantissa:06x}` = {mantissa:,}  \n"
        f"- **Formula**: `target = 0x{mantissa:06x} × 256^({exponent} − 3)`  \n"
        f"- **Result**: `{pow_r['target_hex'][:16]}…` (256-bit number)"
    )

    st.caption(
        "The difficulty is simply genesis_target / current_target. "
        "A smaller target = more leading zeros required = higher difficulty."
    )

    # ------------------------------------------------------------------
    # Refresh button
    # ------------------------------------------------------------------
    st.divider()
    if st.button("🔄 Refresh now", key="m2_refresh"):
        st.cache_data.clear()
        st.rerun()