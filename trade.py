import requests
import config
from solders.keypair import Keypair
from solana.rpc.api import Client
from wallet_utils import load_wallet
from solders.transaction import VersionedTransaction
from base64 import b64decode
import time

client = Client(config.RPC_URL)
wallet = load_wallet(config.WALLET_JSON_PATH)

JUPITER_URL = "https://quote-api.jup.ag/v6"
purchased_tokens = {}

def get_token_info(token_address):
    url = f"{JUPITER_URL}/tokens"
    tokens = requests.get(url).json()
    for token in tokens:
        if token["address"] == token_address:
            return token
    return None

def swap(input_mint, output_mint, amount, swap_mode="ExactIn"):
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": amount,
        "slippageBps": config.SLIPPAGE_BPS,
        "swapMode": swap_mode,
    }

    quote = requests.get(f"{JUPITER_URL}/quote", params=params).json()
    if not quote.get("routes"):
        print("❌ Tidak ada route swap ditemukan")
        return None

    route = quote["routes"][0]
    swap_request = {
        "route": route,
        "userPublicKey": str(wallet.pubkey()),
        "wrapUnwrapSOL": True
    }

    swap_tx = requests.post(f"{JUPITER_URL}/swap", json=swap_request).json()

    swap_tx_bytes = b64decode(swap_tx['swapTransaction'])
    tx = VersionedTransaction.deserialize(swap_tx_bytes)
    signed_tx = tx.sign([wallet])
    raw_signed = signed_tx.serialize()

    send_result = client.send_raw_transaction(raw_signed)
    print(f"✅ Swap sukses: {send_result['result']}")
    return send_result['result']

def buy_token(ca, send_dm):
    amount = int(config.BUY_AMOUNT_SOL * 10**9)
    tx = swap("So11111111111111111111111111111111111111112", ca, amount)
    if tx:
        purchased_tokens[ca] = {
            "buy_price": get_price(ca),
            "amount_in_sol": config.BUY_AMOUNT_SOL
        }
        send_dm(f"✅ BUY {ca}\nTX: {tx}")
        time.sleep(5)
        auto_sell(ca, send_dm)

def auto_sell(ca, send_dm):
    time.sleep(20)  # tunggu pool stabil

    current_price = get_price(ca)
    buy_price = purchased_tokens[ca]["buy_price"]

    if current_price >= buy_price * config.PROFIT_TARGET:
        print(f"🎯 Profit target tercapai: {current_price} (buy: {buy_price})")
        amount = int(purchased_tokens[ca]["amount_in_sol"] * 10**9)
        tx = swap(ca, "So11111111111111111111111111111111111111112", amount)
        if tx:
            send_dm(f"✅ SELL {ca}\nTX: {tx}")
    else:
        print(f"⏳ Profit belum tercapai: {current_price} (target: {buy_price * config.PROFIT_TARGET})")

def get_price(ca):
    params = {
        "inputMint": ca,
        "outputMint": "So11111111111111111111111111111111111111112",
        "amount": int(10**9),
        "swapMode": "ExactIn"
    }
    quote = requests.get(f"{JUPITER_URL}/quote", params=params).json()
    if quote.get("routes"):
        out_amount = quote["routes"][0]["outAmount"]
        return int(out_amount) / 10**9
    return 0
