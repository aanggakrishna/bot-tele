import json
from solders.keypair import Keypair
from solana.rpc.api import Client

def load_keypair():
    with open("wallet.json", "r") as f:
        secret = json.load(f)
        keypair = Keypair.from_bytes(bytes(secret))
        return keypair

def check_balance(keypair):
    client = Client("https://api.mainnet-beta.solana.com")
    balance_resp = client.get_balance(keypair.pubkey())
    balance = balance_resp.value / 1e9
    print(f"Public Key: {keypair.pubkey()}")
    print(f"Balance: {balance} SOL")

if __name__ == "__main__":
    keypair = load_keypair()
    check_balance(keypair)
