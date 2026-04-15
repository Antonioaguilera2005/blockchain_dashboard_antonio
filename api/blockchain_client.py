import requests

# Fetch latest block hash from Mempool.space API (second recommended API)
hash_url = "https://mempool.space/api/v1/blocks/tip/hash"
block_hash = requests.get(hash_url).text.strip()

# Fetch full block details
block_url = f"https://mempool.space/api/v1/block/{block_hash}"
block = requests.get(block_url).json()

# Print required fields
print(f"Height: {block['height']}\nHash: {block['id']}\nDifficulty: {block['difficulty']}\nNonce: {block['nonce']}\nBits: {block['bits']}\nTx count: {block['tx_count']}")

# Observations:
# - The block hash starts with many leading zeros, which is the proof-of-work requirement.
# - The 'bits' field encodes the target threshold. A lower bits value makes the target smaller,
#   increasing the difficulty (more leading zeros needed in the hash).