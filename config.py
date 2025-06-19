import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

class Config:
    # Telegram Configuration
    API_ID = int(os.getenv('API_ID'))
    API_HASH = os.getenv('API_HASH')
    OWNER_ID = int(os.getenv('OWNER_ID'))
    TO_USER_ID = int(os.getenv('TO_USER_ID', '0'))
    
    # Monitor Groups and Channels
    MONITOR_GROUPS = [int(x.strip()) for x in os.getenv('MONITOR_GROUPS', '').split(',') if x.strip()]
    MONITOR_CHANNELS = [int(x.strip()) for x in os.getenv('MONITOR_CHANNELS', '').split(',') if x.strip()]
    
    # Bot Configuration
    BOT_ENABLED = os.getenv('BOT_ENABLED', 'true').lower() == 'true'  # Tambahkan ini
    
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

    _entity_details = None
    
    def get_entity_details(self):
        """Get cached entity details from file"""
        if self._entity_details is None:
            try:
                if os.path.exists('entity_details.json'):
                    with open('entity_details.json', 'r') as f:
                        self._entity_details = json.load(f)
                else:
                    self._entity_details = {
                        'groups': {str(id): f"Group {id}" for id in self.MONITOR_GROUPS},
                        'channels': {str(id): f"Channel {id}" for id in self.MONITOR_CHANNELS}
                    }
            except Exception as e:
                logger.error(f"❌ Error loading entity details: {e}")
                self._entity_details = {
                    'groups': {str(id): f"Group {id}" for id in self.MONITOR_GROUPS},
                    'channels': {str(id): f"Channel {id}" for id in self.MONITOR_CHANNELS}
                }
        return self._entity_details
    
    def save_entity_details(self, details):
        """Save entity details to file"""
        if details:
            try:
                with open('entity_details.json', 'w') as f:
                    json.dump(details, f, indent=2)
                self._entity_details = details
            except Exception as e:
                logger.error(f"❌ Error saving entity details: {e}")

