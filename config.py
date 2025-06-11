import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

ADMIN_USERNAME = "adminxx123"
GROUP_ID = -1001915865922

SOLANA_RPC = "https://api.mainnet-beta.solana.com"
JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"

WALLET_FILE = "wallet.json"

BUY_AMOUNT_SOL = 0.01  # jumlah pembelian awal
TAKE_PROFIT_MULTIPLIER = 2.0  # target take profit (100% = x2)
