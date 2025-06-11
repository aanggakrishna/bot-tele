import json
from solders.keypair import Keypair

def load_wallet(wallet_path):
    with open(wallet_path, "r") as f:
        key_data = json.load(f)
    keypair = Keypair.from_bytes(bytes(key_data))
    return keypair
