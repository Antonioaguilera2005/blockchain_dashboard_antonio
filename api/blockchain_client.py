"""
Blockchain API client.

Provides helper functions to fetch blockchain data from public APIs.
All functions raise requests.HTTPError on non-2xx responses and
requests.Timeout on slow connections — callers should handle these.
"""

import time
from unittest import result

import requests

BASE_URL = "https://blockchain.info"

# ---------------------------------------------------------------------------
# Simple in-memory cache so repeated Streamlit rerenders don't hammer the API
# ---------------------------------------------------------------------------
_cache: dict = {}
_CACHE_TTL = 30  # seconds


def _get_cached(url: str, params: dict | None = None, ttl: int = _CACHE_TTL):
    """Return cached response or fetch fresh data."""
    key = (url, str(params))
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"] < ttl):
        return entry["data"]
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    _cache[key] = {"ts": time.time(), "data": data}
    return data


# ---------------------------------------------------------------------------
# Difficulty helpers
# ---------------------------------------------------------------------------

# Genesis block target (the 'bits' field of block 0): 0x1d00ffff
# This is the reference used to compute the relative difficulty of any block.
_GENESIS_TARGET = 0x00000000FFFF0000000000000000000000000000000000000000000000000000


def bits_to_target(bits: int) -> int:
    """Decode the compact 'bits' field into the full 256-bit target integer."""
    exponent = (bits >> 24) & 0xFF
    mantissa = bits & 0x007FFFFF
    return mantissa * (256 ** (exponent - 3))


def difficulty_from_bits(bits: int) -> float:
    """
    Compute difficulty from the compact 'bits' field.

    difficulty = genesis_target / current_target

    blockchain.info's /rawblock endpoint does not always include a 'difficulty'
    field, so we derive it ourselves from 'bits' — which is always present.
    """
    target = bits_to_target(bits)
    if target == 0:
        return 0.0
    return _GENESIS_TARGET / target


# ---------------------------------------------------------------------------
# Public API functions
# ---------------------------------------------------------------------------


def get_latest_block() -> dict:
    """Return the latest block summary from blockchain.info/latestblock."""
    return _get_cached(f"{BASE_URL}/latestblock")


def get_block(block_hash: str) -> dict:
    """
    Return full details for a block identified by *block_hash*.

    Guarantees the returned dict always contains a 'difficulty' key,
    computed from 'bits' if the API does not supply it directly.
    """
    data = _get_cached(f"{BASE_URL}/rawblock/{block_hash}", ttl=3600)
    # Ensure 'difficulty' is always present — API sometimes omits it
    if "difficulty" not in data and "bits" in data:
        data["difficulty"] = difficulty_from_bits(data["bits"])
    return data


def get_difficulty_history(n_points: int = 100) -> list[dict]:
    """
    Fetch difficulty adjustment history from mempool.space.
    Endpoint returns: [timestamp_seconds, block_height, difficulty, change_percent]
    Uses '3y' timespan to get ~1 year of adjustment periods.
    """
    response = requests.get(
        "https://mempool.space/api/v1/mining/difficulty-adjustments/3y",
        timeout=10,
    )
    response.raise_for_status()
    history = response.json()
    # entry format: [timestamp, height, difficulty, change_percent]
    # timestamp is in seconds (Unix epoch)
    result = []
    for entry in history:
        ts = entry[0]
        if ts > 1e12:
            ts = ts / 1000
        result.append({
            "x": int(ts),
            "y": entry[2],
            "change_percent": entry[3] 
        })
    result.sort(key=lambda x: x["x"])  # asegurar orden cronológico ascendente
    return result[-n_points:]

def get_block_interval_timestamps(n_blocks: int = 50) -> list[int]:
    """
    Walk back *n_blocks* blocks from the tip and return their Unix timestamps
    in reverse-chronological order (newest first).

    Useful for computing inter-block intervals in M1.
    """
    timestamps: list[int] = []
    latest = get_latest_block()
    current_hash: str = latest["hash"]

    for _ in range(n_blocks + 1):
        block = get_block(current_hash)
        timestamps.append(block["time"])
        current_hash = block["prev_block"]

    return timestamps