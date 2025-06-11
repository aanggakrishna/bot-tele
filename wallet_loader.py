import json
from solana.account import Account
from solana.publickey import PublicKey
from solana.rpc.api import Client

# RPC endpoint Solana
RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"

def load_wallet(path='wallet.json'):
    with open(path, 'r') as f:
        secret_key = json.load(f)
    account = Account(secret_key)
    return account

def check_balance(account):
    client = Client(RPC_ENDPOINT)
    balance = client.get_balance(account.public_key())['result']['value'] / 1e9
    print(f"Public Key: {account.public_key()}")
    print(f"Balance: {balance} SOL")
    return balance

if __name__ == "__main__":
    account = load_wallet()
    check_balance(account)
