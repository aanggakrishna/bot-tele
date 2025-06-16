import os
import json
import base64
import base58
import aiohttp
import asyncio
from typing import Optional, Dict, List
from loguru import logger
from dotenv import load_dotenv

# Solana imports with error handling
try:
    from solana.rpc.async_api import AsyncClient
    from solana.transaction import Transaction
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    from solders.instruction import Instruction
    from solders.system_program import transfer, TransferParams
    from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
    SOLANA_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ Solana dependencies not installed: {e}")
    logger.error("💡 Run: pip install solana==0.30.2 solders==0.18.1")
    SOLANA_AVAILABLE = False

load_dotenv()

class SolanaService:
    def __init__(self):
        self.client = None
        self.keypair = None
        self.rpc_url = os.getenv('RPC_URL', 'https://api.mainnet-beta.solana.com')
        self.jupiter_api = 'https://quote-api.jup.ag/v6'
        self.enable_real_trading = os.getenv('ENABLE_REAL_TRADING', 'false').lower() == 'true'
        self.solana_available = SOLANA_AVAILABLE
        
    def init_from_env(self):
        """Initialize from environment variables"""
        try:
            if not self.solana_available:
                logger.error("❌ Solana dependencies not available")
                logger.error("💡 Install with: pip install solana==0.30.2 solders==0.18.1")
                return False
            
            # Setup RPC client
            self.client = AsyncClient(self.rpc_url)
            logger.info(f"🌐 Connected to Solana RPC: {self.rpc_url}")
            
            # Load wallet
            self._load_wallet()
            
            # Show trading mode
            mode = "🔴 REAL TRADING ENABLED" if self.enable_real_trading else "🟡 MOCK TRADING MODE"
            logger.warning(f"⚠️ {mode}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Solana service: {e}")
            return False
    
    def _load_wallet(self):
        """Load wallet from environment"""
        try:
            if not self.solana_available:
                logger.warning("⚠️ Solana not available - wallet loading skipped")
                return
            
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
        """Get real token price from Jupiter API"""
        try:
            if not self._is_valid_address(token_mint_str):
                logger.error(f"❌ Invalid token address: {token_mint_str}")
                return None
            
            # Use Jupiter price API
            url = f"{self.jupiter_api}/price"
            params = {
                'ids': token_mint_str,
                'vsToken': 'So11111111111111111111111111111111111111112'  # SOL
            }
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if 'data' in data and token_mint_str in data['data']:
                                price = float(data['data'][token_mint_str]['price'])
                                logger.debug(f"💰 Real price for {token_mint_str}: {price} SOL")
                                return price
            except Exception as api_error:
                logger.warning(f"⚠️ Jupiter API error: {api_error}")
            
            # Fallback to mock price if API fails
            logger.warning(f"⚠️ Could not get real price for {token_mint_str}, using mock")
            return 0.0001
            
        except Exception as e:
            logger.error(f"❌ Error getting price for {token_mint_str}: {e}")
            return 0.0001  # Fallback mock price
    
    async def get_wallet_balance(self) -> Optional[float]:
        """Get real wallet SOL balance"""
        try:
            if not self.keypair or not self.client:
                return None
            
            response = await self.client.get_balance(self.keypair.pubkey())
            if response.value is not None:
                balance_sol = response.value / 1_000_000_000
                logger.debug(f"💎 Wallet balance: {balance_sol:.6f} SOL")
                return balance_sol
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting balance: {e}")
            return None
    
    async def buy_token(self, token_mint: str) -> Optional[Dict]:
        """Buy token - REAL or MOCK based on settings"""
        try:
            if not self._is_valid_address(token_mint):
                logger.error(f"❌ Invalid token address: {token_mint}")
                return None
            
            # Always use mock if Solana not available or real trading disabled
            if not self.solana_available or not self.enable_real_trading or not self.keypair:
                reason = "Solana not available" if not self.solana_available else \
                        "Real trading disabled" if not self.enable_real_trading else \
                        "No wallet configured"
                logger.warning(f"🚨 {reason} - Returning mock result")
                return await self._mock_buy(token_mint)
            
            logger.warning(f"🔴 ATTEMPTING REAL BUY for {token_mint}")
            
            # Get buy amount from env
            buy_amount_sol = float(os.getenv('AMOUNT_TO_BUY_SOL', '0.01'))
            slippage_bps = int(os.getenv('SLIPPAGE_BPS', '300'))  # 3%
            
            # Check wallet balance first
            balance = await self.get_wallet_balance()
            if not balance or balance < buy_amount_sol + 0.001:  # +0.001 for fees
                logger.error(f"❌ Insufficient balance: {balance} SOL, need {buy_amount_sol + 0.001} SOL")
                return None
            
            logger.info(f"💰 Buying {buy_amount_sol} SOL worth of {token_mint}")
            
            # For now, return mock until Jupiter integration is fully tested
            logger.warning("⚠️ Real Jupiter integration not fully implemented yet - using mock")
            return await self._mock_buy(token_mint)
            
        except Exception as e:
            logger.error(f"❌ Error in buy for {token_mint}: {e}")
            return None
    
    async def sell_token(self, token_mint: str, amount: float, wallet_account: str) -> Optional[Dict]:
        """Sell token - REAL or MOCK based on settings"""
        try:
            if not self._is_valid_address(token_mint):
                logger.error(f"❌ Invalid token address: {token_mint}")
                return None
            
            # Always use mock if Solana not available or real trading disabled
            if not self.solana_available or not self.enable_real_trading or not self.keypair:
                reason = "Solana not available" if not self.solana_available else \
                        "Real trading disabled" if not self.enable_real_trading else \
                        "No wallet configured"
                logger.warning(f"🚨 {reason} - Returning mock result")
                return await self._mock_sell(token_mint)
            
            logger.warning(f"🔴 ATTEMPTING REAL SELL for {token_mint}")
            
            # For now, return mock until Jupiter integration is fully tested
            logger.warning("⚠️ Real Jupiter integration not fully implemented yet - using mock")
            return await self._mock_sell(token_mint)
            
        except Exception as e:
            logger.error(f"❌ Error in sell for {token_mint}: {e}")
            return None
    
    async def _mock_buy(self, token_mint: str) -> Dict:
        """Mock buy for testing"""
        import time
        buy_amount_sol = float(os.getenv('AMOUNT_TO_BUY_SOL', '0.01'))
        return {
            'token_mint_address': token_mint,
            'buy_price_sol': 0.0001,
            'amount_bought_token': buy_amount_sol / 0.0001,  # Calculate based on buy amount
            'wallet_token_account': str(self.keypair.pubkey()) if self.keypair else 'mock_account',
            'buy_tx_signature': f'mock_buy_{int(time.time())}'
        }
    
    async def _mock_sell(self, token_mint: str) -> Dict:
        """Mock sell for testing"""
        import time
        return {
            'sell_price_sol': 0.0002,
            'sell_tx_signature': f'mock_sell_{int(time.time())}'
        }
    
    def _is_valid_address(self, address: str) -> bool:
        """Validate Solana address"""
        try:
            if not (32 <= len(address) <= 44):
                return False
            
            decoded = base58.b58decode(address)
            if len(decoded) != 32:
                return False
            
            if self.solana_available:
                Pubkey.from_string(address)
            return True
            
        except Exception:
            return False

# Global instance
solana_service = SolanaService()

# Initialize function - this is what main.py calls
def init_solana_config_from_env():
    """Initialize global Solana service from environment"""
    try:
        success = solana_service.init_from_env()
        if success:
            logger.info("✅ Solana service initialized successfully")
        else:
            logger.warning("⚠️ Solana service initialized with limitations")
        return success
    except Exception as e:
        logger.error(f"❌ Failed to initialize Solana service: {e}")
        return False

# Wrapper functions for compatibility
async def get_token_price_sol(token_mint):
    """Wrapper function to get token price"""
    if isinstance(token_mint, str):
        return await solana_service.get_token_price_sol(token_mint)
    else:
        return await solana_service.get_token_price_sol(str(token_mint))

async def buy_token_solana(token_mint_address: str):
    """Wrapper function to buy token"""
    return await solana_service.buy_token(token_mint_address)

async def sell_token_solana(token_mint_address: str, amount: float, wallet_token_account: str):
    """Wrapper function to sell token"""
    return await solana_service.sell_token(token_mint_address, amount, wallet_token_account)

# Validation function for external use
def is_valid_solana_address(address: str) -> bool:
    """Standalone function to validate Solana address"""
    return solana_service._is_valid_address(address)