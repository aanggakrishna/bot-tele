import requests
import json
from solana.rpc.api import Client
from solana.keypair import Keypair
from solana.transaction import Transaction
import config

def load_wallet():
    with open(config.WALLET_FILE, "r") as f:
        secret = json.load(f)
        return Keypair.from_secret_key(bytes(secret))

def execute_trade(target_token):
    wallet = load_wallet()
    solana_client = Client(config.SOLANA_RPC)
    
    SOL_MINT = "So11111111111111111111111111111111111111112"
    amount = int(0.05 * 1e9)  # 0.05 SOL sebagai contoh

    params = {
        "inputMint": SOL_MINT,
        "outputMint": target_token,
        "amount": amount,
        "slippageBps": 500,
        "swapMode": "ExactIn"
    }

    response = requests.get(config.JUPITER_QUOTE_URL, params=params)
    quote = response.json()

    print("💰 Quote diterima:", quote)
    
    # DISINI NANTI kita lanjut ke eksekusi swap via Jupiter
    # Ini masih dummy ya
    print("🚀 (SIMULASI) Beli token selesai.")

