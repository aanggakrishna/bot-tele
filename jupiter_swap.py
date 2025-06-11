import requests
import json
from solana.rpc.api import Client
from solana.transaction import Transaction
from solana.keypair import Keypair
from wallet_utils import load_wallet
import base64

RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"
JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"

client = Client(RPC_ENDPOINT)
wallet = load_wallet("wallet.json")
owner = str(wallet.public_key)

def get_quote(input_mint, output_mint, amount, slippage=1):
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": amount,
        "slippageBps": slippage * 100,
        "onlyDirectRoutes": False
    }
    resp = requests.get(JUPITER_QUOTE_URL, params=params)
    return resp.json()

def execute_swap(input_mint, output_mint, amount, slippage=1):
    quote = get_quote(input_mint, output_mint, amount, slippage)
    if not quote.get("routes"):
        raise Exception("No route found")

    route = quote["routes"][0]
    swap_resp = requests.post(JUPITER_SWAP_URL, json={
        "route": route,
        "userPublicKey": owner,
        "wrapUnwrapSOL": True,
        "asLegacyTransaction": True
    })
    swap_data = swap_resp.json()

    tx = base64.b64decode(swap_data['swapTransaction'])
    txn = Transaction.deserialize(tx)
    txn.sign(wallet)
    txid = client.send_transaction(txn)
    return txid["result"]
