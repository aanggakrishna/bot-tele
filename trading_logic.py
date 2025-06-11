import os
import json
import time
from dotenv import load_dotenv
from solders.keypair import Keypair
from solana.rpc.api import Client
from notifier import notify_owner

load_dotenv()

# Load config
RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"
BUY_AMOUNT = float(os.getenv("BUY_AMOUNT"))  # Jumlah beli dalam SOL
SLIPPAGE = float(os.getenv("SLIPPAGE")) / 100
MAX_OPEN_TRADES = 2

client = Client(RPC_ENDPOINT)
trades_file = "open_trades.json"

def load_wallet(path='wallet.json'):
    with open(path, 'r') as f:
        secret_key = json.load(f)
    return Keypair.from_bytes(bytes(secret_key))

wallet = load_wallet()

def load_open_trades():
    if os.path.exists(trades_file):
        with open(trades_file, 'r') as f:
            return json.load(f)
    return []

def save_open_trades(trades):
    with open(trades_file, 'w') as f:
        json.dump(trades, f)

def buy_token(ca_address):
    open_trades = load_open_trades()
    if len(open_trades) >= MAX_OPEN_TRADES:
        print("Masih ada posisi nyangkut, skip beli.")
        return

    # Simulasi harga market (nanti kita pakai API dexscreener)
    market_price = 1.0  # mock price
    buy_price = market_price * (1 + SLIPPAGE)

    trade = {
        "ca": ca_address,
        "buy_price": buy_price,
        "buy_time": int(time.time())
    }

    open_trades.append(trade)
    save_open_trades(open_trades)

    log = f"✅ BUY {ca_address}\nBuy Price: {buy_price} SOL"
    print(log)
    notify_owner(log)

def monitor_trades():
    open_trades = load_open_trades()
    new_trades = []

    for trade in open_trades:
        current_price = 1.0  # Simulasi harga

        tp_price = trade['buy_price'] * 1.75
        sl_price = trade['buy_price'] * 0.48
        stagnant_time = 86400

        now = int(time.time())

        if current_price >= tp_price:
            log = f"🎯 TAKE PROFIT {trade['ca']} at {current_price} SOL"
            print(log)
            notify_owner(log)
        elif current_price <= sl_price:
            log = f"🛑 STOP LOSS {trade['ca']} at {current_price} SOL"
            print(log)
            notify_owner(log)
        elif now - trade['buy_time'] > stagnant_time:
            log = f"⏳ STAGNAN SELL {trade['ca']} at {current_price} SOL"
            print(log)
            notify_owner(log)
        else:
            new_trades.append(trade)

    save_open_trades(new_trades)
