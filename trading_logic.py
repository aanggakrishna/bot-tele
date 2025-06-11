from solana.rpc.api import Client
from solders.keypair import Keypair
import json
import os
from wallet_loader import load_keypair

client = Client("https://api.mainnet-beta.solana.com")

# Load wallet
keypair = load_keypair()

# Dummy function beli token
def buy_token(ca):
    print(f"🚀 Simulasi membeli token: {ca}")
    # Nanti kita integrasikan ke Raydium via Jupiter aggregator atau Orca router
