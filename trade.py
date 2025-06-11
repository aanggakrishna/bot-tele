import requests
import json
import time
import base64
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.rpc.responses import SendTransactionResp
from solana.rpc.api import Client
from tenacity import retry, stop_after_attempt, wait_fixed
import config

client = Client(config.SOLANA_RPC)

def load_wallet():
    with open(config.WALLET_FILE, "r") as f:
        secret = json.load(f)
        return Keypair.from_bytes(bytes(secret))

wallet = load_wallet()
wallet_pubkey = wallet.pubkey()

# Fungsi kirim tx Jupiter
@retry(stop=stop_after_attempt(5), wait=wait_fixed(2))
def send_jupiter_swap(route, output_mint):
    swap = requests.post(config.JUPITER_SWAP_URL, json={
        "route": route,
        "userPublicKey": str(wallet_pubkey),
        "wrapUnwrapSOL": True
    }).json()

    tx_bytes = base64.b64decode(swap["swapTransaction"])
    tx = VersionedTransaction.deserialize(tx_bytes)
    tx.sign([wallet])

    resp: SendTransactionResp = client.send_raw_transaction(tx.serialize(), opts={"skip_preflight": True, "max_retries": 5})
    print(f"✅ Swap transaction: {resp.value}")
    return resp.value

# Proses beli
def execute_trade(token_address):
    amount_lamports = int(config.BUY_AMOUNT_SOL * 1e9)

    quote = requests.get(config.JUPITER_QUOTE_URL, params={
        "inputMint": "So11111111111111111111111111111111111111112",
        "outputMint": token_address,
        "amount": amount_lamports,
        "slippageBps": 300
    }).json()

    if not quote.get("routes"):
        print("❌ No route found on Jupiter.")
        return

    route = quote["routes"][0]
    send_jupiter_swap(route, token_address)

    # Start monitoring harga untuk take profit
    monitor_price(token_address)

# Fungsi monitor harga auto take profit
def monitor_price(token_address):
    print("🚀 Start monitoring price for take profit...")

    while True:
        try:
            amount_in_lamports = int(config.BUY_AMOUNT_SOL * 1e9)

            quote = requests.get(config.JUPITER_QUOTE_URL, params={
                "inputMint": token_address,
                "outputMint": "So11111111111111111111111111111111111111112",
                "amount": None
            }).json()

            if not quote.get("routes"):
                print("⏳ Waiting for liquidity...")
                time.sleep(5)
                continue

            price_out = quote['routes'][0]['outAmount'] / 1e9
            print(f"📈 Current est price: {price_out} SOL")

            if price_out >= config.BUY_AMOUNT_SOL * config.TAKE_PROFIT_MULTIPLIER:
                print("🎯 Target profit tercapai! Menjual token...")

                route = quote['routes'][0]
                send_jupiter_swap(route, token_address)
                print("✅ Auto-take profit selesai.")
                break

            time.sleep(5)
        except Exception as e:
            print("⚠ Error monitor:", e)
            time.sleep(5)
