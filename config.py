import os
from dotenv import load_dotenv

load_dotenv()

# Telegram config
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Admin username yang mem-pin
ADMIN_USERNAME = "adminxx123"

# Solana RPC
SOLANA_RPC = "https://api.mainnet-beta.solana.com"

# Jupiter API
JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"

# Wallet file
WALLET_FILE = "wallet.json"