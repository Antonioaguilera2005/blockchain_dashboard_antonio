import requests

tip_hash = requests.get("https://mempool.space/api/blocks/tip/hash").text.strip()
block    = requests.get(f"https://mempool.space/api/block/{tip_hash}").json()

print(f"Height:       {block['height']}")
print(f"Hash:         {block['id']}")
print(f"Difficulty:   {block['difficulty']}")
print(f"Nonce:        {block['nonce']}")
print(f"Transactions: {block['tx_count']}")
print(f"Bits:         {block['bits']}")

# OBSERVACIONES CRIPTOGRÁFICAS:
# - El hash empieza por múltiples ceros → prueba visible del Proof of Work (SHA-256)
# - El campo 'bits' codifica el target threshold en formato compacto de 256 bits
# - La dificultad indica cuántas veces más difícil es minar ahora vs el bloque génesis
# - El nonce es el valor que los mineros varían hasta encontrar un hash válido