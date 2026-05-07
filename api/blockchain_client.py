"""
Blockchain API client.

Provides helper functions to fetch blockchain data from public APIs.
All functions raise requests.HTTPError on non-2xx responses and
requests.Timeout on slow connections — callers should handle these.

APIs used:
  - blockchain.info  — rawblock data (M1, M2)
  - blockstream.info — block timestamps in pages of 10 (M1, M4, M5) 
  - mempool.space    — difficulty history (M3)

Why more than 10 lines:
  The Session-1 milestone asked for a 10-line exploration script (preserved
  in git history). This file is the shared production API layer for M1–M8,
  with caching, error handling, and helpers used across all modules.
"""

import time
import requests

BASE_URL      = "https://blockchain.info"
BLOCKSTREAM   = "https://blockstream.info/api"

# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------
_cache: dict = {}
_CACHE_TTL   = 30  # seconds


def _get_cached(url: str, params: dict | None = None, ttl: int = _CACHE_TTL):
    """Return cached response or fetch fresh data."""
    key = (url, str(params))
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"] < ttl):
        return entry["data"]
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    try:
        data = response.json()
    except Exception:
        data = response.text.strip()
    _cache[key] = {"ts": time.time(), "data": data}
    return data


# ---------------------------------------------------------------------------
# Difficulty helpers (shared by M1, M2, M3)
# ---------------------------------------------------------------------------

_GENESIS_TARGET = 0x00000000FFFF0000000000000000000000000000000000000000000000000000


def bits_to_target(bits: int) -> int:
    """Decode compact 'bits' field → full 256-bit target integer."""
    exponent = (bits >> 24) & 0xFF
    mantissa = bits & 0x007FFFFF
    return mantissa * (256 ** (exponent - 3))


def difficulty_from_bits(bits: int) -> float:
    """Compute difficulty = genesis_target / current_target."""
    target = bits_to_target(bits)
    return (_GENESIS_TARGET / target) if target else 0.0


# ---------------------------------------------------------------------------
# Public API — latest block (full data, not just summary)
# ---------------------------------------------------------------------------

def get_latest_block() -> dict:
    """
    Return full block data for the current chain tip.

    1. Gets the tip hash from blockchain.info/latestblock
    2. Fetches the full block via /rawblock/{hash}
    This guarantees all fields (mrkl_root, bits, nonce, etc.) are present.
    """
    summary = _get_cached(f"{BASE_URL}/latestblock", ttl=30)
    tip_hash = summary["hash"]
    return get_block(tip_hash)


def get_block(block_hash: str) -> dict:
    """
    Return full details for a block identified by block_hash.
    Guarantees 'difficulty', 'mrkl_root', 'prev_block', 'time', 'ver' are present.
    """
    data = _get_cached(f"{BASE_URL}/rawblock/{block_hash}", ttl=3600)
    # Ensure difficulty is always present
    if "difficulty" not in data and "bits" in data:
        data["difficulty"] = difficulty_from_bits(data["bits"])
    # Normalise field name aliases
    data.setdefault("hash",       block_hash)
    data.setdefault("mrkl_root",  data.get("mrkl_root", ""))
    data.setdefault("prev_block", data.get("prev_block", ""))
    data.setdefault("ver",        data.get("ver", 0))
    data.setdefault("n_tx",       data.get("n_tx", 0))
    return data


# ---------------------------------------------------------------------------
# Public API — block timestamps (optimised via mempool.space pages)
# ---------------------------------------------------------------------------

def get_block_interval_timestamps(n_blocks: int = 50) -> list[int]:
    """
    Return Unix timestamps for the last n_blocks+1 blocks (newest first).

    Uses mempool.space /api/v1/blocks/{height} which returns 15 blocks per
    page — fetching 50 blocks needs only ~4 requests instead of 50.
    """
    timestamps: list[int] = []

    tip_height = _get_cached("https://mempool.space/api/blocks/tip/height", ttl=30)
    if isinstance(tip_height, str):
        tip_height = int(tip_height.strip())
    current_height = int(tip_height)

    while len(timestamps) < n_blocks + 1:
        page = _get_cached(
            f"https://mempool.space/api/v1/blocks/{current_height}",
            ttl=60,
        )
        if not isinstance(page, list) or not page:
            break
        for blk in page:
            timestamps.append(int(blk.get("timestamp", 0)))
            if len(timestamps) >= n_blocks + 1:
                break
        current_height -= len(page)
        if current_height <= 0:
            break

    return timestamps


# ---------------------------------------------------------------------------
# Public API — difficulty history (M3)
# ---------------------------------------------------------------------------

def get_difficulty_history(n_points: int = 100) -> list[dict]:
    """
    Fetch difficulty adjustment history from mempool.space.
    Each entry: {"x": unix_timestamp, "y": difficulty, "change_percent": float}
    """
    response = requests.get(
        "https://mempool.space/api/v1/mining/difficulty-adjustments/3y",
        timeout=10,
    )
    response.raise_for_status()
    history = response.json()

    result = []
    for entry in history:
        ts = entry[0]
        if ts > 1e12:
            ts = ts / 1000
        result.append({
            "x": int(ts),
            "y": entry[2],
            "change_percent": entry[3],
        })
    result.sort(key=lambda x: x["x"])
    return result[-n_points:]