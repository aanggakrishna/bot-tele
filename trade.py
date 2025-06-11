import requests
import json
import base64
import config
import datetime
from solders.keypair import Keypair
from solders.rpc.api import Client
from solders.transaction import VersionedTransaction

def load_wallet():
    with open("wallet.json", "r") as f:
        secret = json.load(f)
    return Keypair.from_bytes(bytes(secret))

wallet = load_wallet()
solana_client = Client(config.SOLANA_RPC)

def log_trade(action, token_address, amount, price=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("trade_log.txt", "a") as f:
        f.write(f"[{timestamp}] {action} | Token: {token_address} | Amount: {amount} SOL | Price: {price} SOL\n")

def execute_trade(token_address):
    amount_lamports = int(config.BUY_AMOUNT_SOL * 1e9)
    quote = requests.get(config.JUPITER_QUOTE_URL, params={
        "inputMint": "So11111111111111111111111111111111111111112",
        "outputMint": token_address,
        "amount": amount_lamports,
        "slippageBps": config.SLIPPAGE_BPS
    }).json()

    route = quote["routes"][0]
    send_jupiter_swap(route, token_address)
    price_in = amount_lamports / 1e9
    log_trade("BUY", token_address, config.BUY_AMOUNT_SOL, price_in)

    price_out = config.BUY_AMOUNT_SOL * config.TAKE_PROFIT_MULTIPLIER
    sell_quote = requests.get(config.JUPITER_QUOTE_URL, params={
        "inputMint": token_address,
        "outputMint": "So11111111111111111111111111111111111111112",
        "amount": int(route["outAmount"]),
        "slippageBps": config.SLIPPAGE_BPS
    }).json()

    sell_route = sell_quote["routes"][0]
    send_jupiter_swap(sell_route, token_address)
    log_trade("SELL", token_address, config.BUY_AMOUNT_SOL, price_out)

def send_jupiter_swap(route, token_address):
    swap = requests.post(config.JUPITER_SWAP_URL, json={
        "route": route,
        "userPublicKey": str(wallet.pubkey()),
        "wrapUnwrapSOL": True,
        "feeAccount": None,
        "asLegacyTransaction": False
    }).json()

    tx_bytes = base64.b64decode(swap["swapTransaction"])
    tx = VersionedTransaction.deserialize(tx_bytes)
    tx.sign([wallet])
    raw_tx = base64.b64encode(tx.serialize()).decode()
    resp = solana_client.send_transaction(raw_tx)
    print("✅ Swap transaction:", resp)
