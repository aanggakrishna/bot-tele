import os
import json
import base58
import aiohttp
from typing import Optional, Dict
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class SolanaService:
    def __init__(self):
        self.client = None
        self.keypair = None
        self.rpc_url = os.getenv('RPC_URL', 'https://api.mainnet-beta.solana.com')
        
    def init_from_env(self):
        """Initialize from environment variables"""
        try:
            # Setup RPC client
            self.client = AsyncClient(self.rpc_url)
            logger.info(f"🌐 Connected to Solana RPC: {self.rpc_url}")
            
            # Load wallet
            self._load_wallet()
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Solana service: {e}")
    
    def _load_wallet(self):
        """Load wallet from environment"""
        try:
            # Try base58 private key first
            private_key_b58 = os.getenv('SOLANA_PRIVATE_KEY_BASE58')
            if private_key_b58 and private_key_b58 != 'your_solana_private_key_base58':
                key_bytes = base58.b58decode(private_key_b58)
                self.keypair = Keypair.from_bytes(key_bytes)
                logger.info(f"🔑 Wallet loaded: {self.keypair.pubkey()}")
                return
            
            # Try wallet file
            wallet_path = os.getenv('PRIVATE_KEY_PATH')
            if wallet_path and os.path.exists(wallet_path):
                with open(wallet_path, 'r') as f:
                    wallet_data = json.load(f)
                key_bytes = bytes(wallet_data)
                self.keypair = Keypair.from_bytes(key_bytes)
                logger.info(f"🔑 Wallet loaded from file: {self.keypair.pubkey()}")
                return
            
            logger.warning("⚠️ No wallet configured - monitoring mode only")
            
        except Exception as e:
            logger.error(f"❌ Error loading wallet: {e}")
    
    async def get_token_price_sol(self, token_mint_str: str) -> Optional[float]:
        """Get token price in SOL (mock implementation)"""
        try:
            # Validate token address
            if not self._is_valid_address(token_mint_str):
                logger.error(f"❌ Invalid token address: {token_mint_str}")
                return None
            
            logger.debug(f"🔍 Getting price for: {token_mint_str}")
            
            # Mock price for testing - replace with real price API
            mock_price = 0.0001
            logger.debug(f"💰 Price: {mock_price} SOL")
            return mock_price
            
        except Exception as e:
            logger.error(f"❌ Error getting price for {token_mint_str}: {e}")
            return None
    
    async def get_wallet_balance(self) -> Optional[float]:
        """Get wallet SOL balance"""
        try:
            if not self.keypair:
                return None
            
            response = await self.client.get_balance(self.keypair.pubkey())
            if response.value is not None:
                return response.value / 1_000_000_000  # Convert to SOL
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting balance: {e}")
            return None
    
    async def buy_token(self, token_mint: str) -> Optional[Dict]:
        """Buy token (mock implementation)"""
        try:
            if not self._is_valid_address(token_mint):
                logger.error(f"❌ Invalid token address: {token_mint}")
                return None
            
            logger.info(f"🚀 Mock buying token: {token_mint}")
            
            # Mock buy result for testing
            import time
            result = {
                'token_mint_address': token_mint,
                'buy_price_sol': 0.0001,
                'amount_bought_token': 1000000.0,
                'wallet_token_account': str(self.keypair.pubkey()) if self.keypair else 'mock_account',
                'buy_tx_signature': f'mock_buy_{int(time.time())}'
            }
            
            logger.info(f"✅ Mock buy successful: {token_mint}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error buying token {token_mint}: {e}")
            return None
    
    async def sell_token(self, token_mint: str, amount: float, wallet_account: str) -> Optional[Dict]:
        """Sell token (mock implementation)"""
        try:
            if not self._is_valid_address(token_mint):
                logger.error(f"❌ Invalid token address: {token_mint}")
                return None
            
            logger.info(f"💰 Mock selling token: {token_mint}")
            
            # Mock sell result for testing
            import time
            result = {
                'sell_price_sol': 0.0002,
                'sell_tx_signature': f'mock_sell_{int(time.time())}'
            }
            
            logger.info(f"✅ Mock sell successful: {token_mint}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error selling token {token_mint}: {e}")
            return None
    
    def _is_valid_address(self, address: str) -> bool:
        """Validate Solana address"""
        try:
            if not (32 <= len(address) <= 44):
                return False
            
            decoded = base58.b58decode(address)
            if len(decoded) != 32:
                return False
            
            Pubkey.from_string(address)
            return True
            
        except Exception:
            return False

# Global instance
solana_service = SolanaService()

# Initialize on import
def init_solana_config_from_env():
    solana_service.init_from_env()

# Wrapper functions for compatibility
async def get_token_price_sol(token_mint):
    if isinstance(token_mint, str):
        return await solana_service.get_token_price_sol(token_mint)
    else:
        return await solana_service.get_token_price_sol(str(token_mint))

async def buy_token_solana(token_mint_address: str):
    return await solana_service.buy_token(token_mint_address)

async def sell_token_solana(token_mint_address: str, amount: float, wallet_token_account: str):
    return await solana_service.sell_token(token_mint_address, amount, wallet_token_account)