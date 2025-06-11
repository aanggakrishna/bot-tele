import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
GROUP_ID = int(os.getenv("GROUP_ID"))
RPC_URL = os.getenv("RPC_URL")
WALLET_JSON_PATH = os.getenv("WALLET_JSON_PATH")
BUY_AMOUNT_SOL = float(os.getenv("BUY_AMOUNT_SOL"))
SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS"))
PROFIT_TARGET = float(os.getenv("PROFIT_TARGET"))
OWNER_ID = int(os.getenv("OWNER_ID"))
