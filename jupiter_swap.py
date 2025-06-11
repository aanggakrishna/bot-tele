import requests
import json
from solders.keypair import Keypair
from solders.rpc.api import Client
from solders.rpc.config import SendTransactionConfig
from solders.rpc.commitment import Commitment

RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"
JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"

client = Client(RPC_ENDPOINT)

def load_keypair(path):
    with open(path, 'r') as f:
        secret = json.load(f)
    return Keypair.from_bytes(bytes(secret))

wallet = load_keypair("wallet.json")
owner = str(wallet.pubkey())

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

    tx = swap_data['swapTransaction']
    raw_tx = bytes.fromhex(tx)
    deserialized = client.deserialize_transaction(raw_tx)

    signed = deserialized.sign([wallet])
    sig = client.send_transaction(signed, opts=SendTransactionConfig(skip_preflight=True, preflight_commitment=Commitment("confirmed")))
    return sig
