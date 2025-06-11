import json
from solana.keypair import Keypair
from solana.rpc.api import Client

# RPC endpoint Solana
RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"

def load_wallet(path='wallet.json'):
    with open(path, 'r') as f:
        secret_key = json.load(f)
    keypair = Keypair.from_secret_key(bytes(secret_key))
    return keypair

def check_balance(keypair):
    client = Client(RPC_ENDPOINT)
    balance = client.get_balance(keypair.public_key)['result']['value'] / 1e9
    print(f"Public Key: {keypair.public_key}")
    print(f"Balance: {balance} SOL")
    return balance

if __name__ == "__main__":
    keypair = load_wallet()
    check_balance(keypair)
