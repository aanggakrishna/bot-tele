import os
import json
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
    
    # Monitor Users Configuration
    MONITOR_USERS = [int(x.strip()) for x in os.getenv('MONITOR_USERS', '').split(',') if x.strip()]
    MONITOR_USER_USERNAMES = [x.strip() for x in os.getenv('MONITOR_USER_USERNAMES', '').split(',') if x.strip()]
    
    # Bot Configuration
    BOT_ENABLED = os.getenv('BOT_ENABLED', 'true').lower() == 'true'
    
    # Monitoring Control Flags
    ENABLE_CHANNEL_MONITORING = os.getenv('ENABLE_CHANNEL_MONITORING', 'true').lower() == 'true'
    ENABLE_GROUP_MONITORING = os.getenv('ENABLE_GROUP_MONITORING', 'true').lower() == 'true'
    ENABLE_USER_MONITORING = os.getenv('ENABLE_USER_MONITORING', 'true').lower() == 'true'
    SELECT_MODE_ON_STARTUP = os.getenv('SELECT_MODE_ON_STARTUP', 'false').lower() == 'true'
    
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
    # Also enable/disable native Solana address detection
    ENABLE_NATIVE = os.getenv('ENABLE_NATIVE', 'true').lower() == 'true'
    
    # Entity details cache
    _entity_details = None
    
    def get_entity_details(self):
        """Get cached entity details from file"""
        if self._entity_details is None:
            try:
                if os.path.exists('entity_details.json'):
                    with open('entity_details.json', 'r') as f:
                        self._entity_details = json.load(f)
                    # Ensure keys exist
                    if 'groups' not in self._entity_details:
                        self._entity_details['groups'] = {str(id): f"Group {id}" for id in self.MONITOR_GROUPS}
                    if 'channels' not in self._entity_details:
                        self._entity_details['channels'] = {str(id): f"Channel {id}" for id in self.MONITOR_CHANNELS}
                    if 'users' not in self._entity_details:
                        self._entity_details['users'] = {str(id): f"User {id}" for id in getattr(self, 'MONITOR_USERS', [])}
                else:
                    self._entity_details = {
                        'groups': {str(id): f"Group {id}" for id in self.MONITOR_GROUPS},
                        'channels': {str(id): f"Channel {id}" for id in self.MONITOR_CHANNELS},
                        'users': {str(id): f"User {id}" for id in getattr(self, 'MONITOR_USERS', [])}
                    }
            except Exception as e:
                logger.error(f"❌ Error loading entity details: {e}")
                self._entity_details = {
                    'groups': {str(id): f"Group {id}" for id in self.MONITOR_GROUPS},
                    'channels': {str(id): f"Channel {id}" for id in self.MONITOR_CHANNELS},
                    'users': {str(id): f"User {id}" for id in getattr(self, 'MONITOR_USERS', [])}
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

# Initialize config instance
config = Config()