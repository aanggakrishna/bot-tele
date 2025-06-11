import json
import base58
import os
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.api import Client
from dotenv import load_dotenv

# Load env
load_dotenv()

RPC_URL = os.getenv("RPC_URL")
WALLET_JSON_PATH = os.getenv("WALLET_JSON_PATH")

client = Client(RPC_URL)

# Load keypair dari wallet.json
def load_wallet():
    with open(WALLET_JSON_PATH, "r") as f:
        key_data = json.load(f)
    keypair = Keypair.from_bytes(bytes(key_data))
    return keypair

wallet = load_wallet()

# Cek balance native SOL
def check_balance():
    balance_result = client.get_balance(wallet.pubkey())
    lamports = balance_result["result"]["value"]
    sol = lamports / 10**9
    print(f"Saldo: {sol} SOL")
    return sol

# Dummy function beli token (nanti pakai Jupiter API buat real trading)
def buy_token(ca):
    print(f"[BUY] Membeli token CA: {ca}")
    # --- nanti disini kita akan hubungkan ke Jupiter API ---
    # sementara kita hanya simulasi

# Dummy function jual token (sell 100% posisi)
def sell_token(ca):
    print(f"[SELL] Menjual token CA: {ca}")
    # --- nanti juga akan konek ke Jupiter atau Raydium API ---

if __name__ == "__main__":
    print("✅ Wallet Address:", wallet.pubkey())
    check_balance()

    # Simulasi trading
    ca_address = "E2pxg6FezvFWJLoLtLqsedaZ86pgF2o3XJ6Fa59Upump"
    buy_token(ca_address)
    sell_token(ca_address)
