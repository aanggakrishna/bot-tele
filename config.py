import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

class Config:
    # Telegram Configuration
    API_ID = int(os.getenv('API_ID'))
    API_HASH = os.getenv('API_HASH')
    OWNER_ID = int(os.getenv('OWNER_ID'))
    
    # Monitor Groups and Channels
    MONITOR_GROUPS = [int(x.strip()) for x in os.getenv('MONITOR_GROUPS', '').split(',') if x.strip()]
    MONITOR_CHANNELS = [int(x.strip()) for x in os.getenv('MONITOR_CHANNELS', '').split(',') if x.strip()]
    
    # Solana Configuration
    RPC_URL = os.getenv('RPC_URL', 'https://api.mainnet-beta.solana.com')
    SOLANA_PRIVATE_KEY_BASE58 = os.getenv('SOLANA_PRIVATE_KEY_BASE58')
    PRIVATE_KEY_PATH = os.getenv('PRIVATE_KEY_PATH')
    
    # Trading Configuration
    ENABLE_REAL_TRADING = os.getenv('ENABLE_REAL_TRADING', 'false').lower() == 'true'
    AMOUNT_TO_BUY_SOL = float(os.getenv('AMOUNT_TO_BUY_SOL', '0.01'))
    SLIPPAGE_BPS = int(os.getenv('SLIPPAGE_BPS', '500'))
    STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '0.52'))
    TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '0.75'))
    MAX_PURCHASES_ALLOWED = int(os.getenv('MAX_PURCHASES_ALLOWED', '2'))
    
    # Jupiter API
    JUPITER_API_URL = os.getenv('JUPITER_API_URL', 'https://quote-api.jup.ag/v6')
    
    # Platform Enables
    ENABLE_PUMPFUN = os.getenv('ENABLE_PUMPFUN', 'true').lower() == 'true'
    ENABLE_MOONSHOT = os.getenv('ENABLE_MOONSHOT', 'true').lower() == 'true'
    ENABLE_RAYDIUM = os.getenv('ENABLE_RAYDIUM', 'true').lower() == 'true'
    ENABLE_BIRDEYE = os.getenv('ENABLE_BIRDEYE', 'true').lower() == 'true'

config = Config()