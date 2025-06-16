import os
import json
import base58
import aiohttp
import asyncio
from typing import Optional, Dict, List
from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction
from solders.system_program import transfer, TransferParams
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class SolanaService:
    def __init__(self):
        self.client = None
        self.keypair = None
        self.rpc_url = os.getenv('RPC_URL', 'https://api.mainnet-beta.solana.com')
        self.jupiter_api = 'https://quote-api.jup.ag/v6'
        self.enable_real_trading = os.getenv('ENABLE_REAL_TRADING', 'false').lower() == 'true'
        
    def init_from_env(self):
        """Initialize from environment variables"""
        try:
            # Setup RPC client
            self.client = AsyncClient(self.rpc_url)
            logger.info(f"🌐 Connected to Solana RPC: {self.rpc_url}")
            
            # Load wallet
            self._load_wallet()
            
            # Show trading mode
            mode = "🔴 REAL TRADING ENABLED" if self.enable_real_trading else "🟡 MOCK TRADING MODE"
            logger.warning(f"⚠️ {mode}")
            
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
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'data' in data and token_mint_str in data['data']:
                            price = float(data['data'][token_mint_str]['price'])
                            logger.debug(f"💰 Real price for {token_mint_str}: {price} SOL")
                            return price
            
            # Fallback to mock price if API fails
            logger.warning(f"⚠️ Could not get real price for {token_mint_str}, using mock")
            return 0.0001
            
        except Exception as e:
            logger.error(f"❌ Error getting price for {token_mint_str}: {e}")
            return 0.0001  # Fallback mock price
    
    async def get_wallet_balance(self) -> Optional[float]:
        """Get real wallet SOL balance"""
        try:
            if not self.keypair:
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
        """Buy token - REAL IMPLEMENTATION"""
        try:
            if not self._is_valid_address(token_mint):
                logger.error(f"❌ Invalid token address: {token_mint}")
                return None
            
            if not self.keypair:
                logger.error(f"❌ No wallet configured for trading")
                return None
            
            # Safety check for real trading
            if not self.enable_real_trading:
                logger.warning("🚨 REAL TRADING DISABLED - Returning mock result")
                return await self._mock_buy(token_mint)
            
            logger.warning(f"🔴 EXECUTING REAL BUY for {token_mint}")
            
            # Get buy amount from env
            buy_amount_sol = float(os.getenv('AMOUNT_TO_BUY_SOL', '0.01'))
            slippage_bps = int(os.getenv('SLIPPAGE_BPS', '300'))  # 3%
            
            # Check wallet balance first
            balance = await self.get_wallet_balance()
            if not balance or balance < buy_amount_sol + 0.001:  # +0.001 for fees
                logger.error(f"❌ Insufficient balance: {balance} SOL, need {buy_amount_sol + 0.001} SOL")
                return None
            
            logger.info(f"💰 Buying {buy_amount_sol} SOL worth of {token_mint}")
            
            # Get Jupiter quote
            quote = await self._get_jupiter_quote(
                input_mint='So11111111111111111111111111111111111111112',  # SOL
                output_mint=token_mint,
                amount=int(buy_amount_sol * 1_000_000_000),  # Convert to lamports
                slippage_bps=slippage_bps
            )
            
            if not quote:
                logger.error("❌ Could not get Jupiter quote")
                return None
            
            # Get swap transaction
            swap_tx = await self._get_jupiter_swap_transaction(quote)
            if not swap_tx:
                logger.error("❌ Could not get swap transaction")
                return None
            
            # Execute the transaction
            tx_signature = await self._execute_transaction(swap_tx)
            if not tx_signature:
                logger.error("❌ Transaction failed")
                return None
            
            logger.info(f"✅ REAL BUY SUCCESSFUL! TX: {tx_signature}")
            
            # Calculate result based on quote
            amount_out = int(quote['outAmount'])
            price_per_token = buy_amount_sol / amount_out if amount_out > 0 else 0
            
            result = {
                'token_mint_address': token_mint,
                'buy_price_sol': price_per_token,
                'amount_bought_token': float(amount_out),
                'wallet_token_account': str(self.keypair.pubkey()),
                'buy_tx_signature': tx_signature
            }
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in real buy for {token_mint}: {e}")
            return None
    
    async def sell_token(self, token_mint: str, amount: float, wallet_account: str) -> Optional[Dict]:
        """Sell token - REAL IMPLEMENTATION"""
        try:
            if not self._is_valid_address(token_mint):
                logger.error(f"❌ Invalid token address: {token_mint}")
                return None
            
            if not self.keypair:
                logger.error(f"❌ No wallet configured for trading")
                return None
            
            # Safety check for real trading
            if not self.enable_real_trading:
                logger.warning("🚨 REAL TRADING DISABLED - Returning mock result")
                return await self._mock_sell(token_mint)
            
            logger.warning(f"🔴 EXECUTING REAL SELL for {token_mint}")
            
            slippage_bps = int(os.getenv('SLIPPAGE_BPS', '300'))  # 3%
            
            # Get Jupiter quote for selling
            quote = await self._get_jupiter_quote(
                input_mint=token_mint,
                output_mint='So11111111111111111111111111111111111111112',  # SOL
                amount=int(amount),
                slippage_bps=slippage_bps
            )
            
            if not quote:
                logger.error("❌ Could not get Jupiter sell quote")
                return None
            
            # Get swap transaction
            swap_tx = await self._get_jupiter_swap_transaction(quote)
            if not swap_tx:
                logger.error("❌ Could not get sell swap transaction")
                return None
            
            # Execute the transaction
            tx_signature = await self._execute_transaction(swap_tx)
            if not tx_signature:
                logger.error("❌ Sell transaction failed")
                return None
            
            logger.info(f"✅ REAL SELL SUCCESSFUL! TX: {tx_signature}")
            
            # Calculate result
            amount_out_lamports = int(quote['outAmount'])
            sell_price_sol = amount_out_lamports / 1_000_000_000
            
            result = {
                'sell_price_sol': sell_price_sol,
                'sell_tx_signature': tx_signature
            }
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in real sell for {token_mint}: {e}")
            return None
    
    async def _get_jupiter_quote(self, input_mint: str, output_mint: str, amount: int, slippage_bps: int) -> Optional[Dict]:
        """Get Jupiter swap quote"""
        try:
            url = f"{self.jupiter_api}/quote"
            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': str(amount),
                'slippageBps': str(slippage_bps),
                'onlyDirectRoutes': 'false',
                'asLegacyTransaction': 'false'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        quote_data = await response.json()
                        logger.debug(f"💱 Jupiter quote: {quote_data}")
                        return quote_data
                    else:
                        logger.error(f"❌ Jupiter quote API error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Error getting Jupiter quote: {e}")
            return None
    
    async def _get_jupiter_swap_transaction(self, quote: Dict) -> Optional[str]:
        """Get Jupiter swap transaction"""
        try:
            url = f"{self.jupiter_api}/swap"
            payload = {
                'quoteResponse': quote,
                'userPublicKey': str(self.keypair.pubkey()),
                'wrapAndUnwrapSol': True,
                'computeUnitPriceMicroLamports': 'auto'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        swap_data = await response.json()
                        if 'swapTransaction' in swap_data:
                            return swap_data['swapTransaction']
                    
                    logger.error(f"❌ Jupiter swap API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error getting Jupiter swap transaction: {e}")
            return None
    
    async def _execute_transaction(self, transaction_b64: str) -> Optional[str]:
        """Execute the transaction on Solana"""
        try:
            # Decode the transaction
            transaction_bytes = base64.b64decode(transaction_b64)
            transaction = Transaction.deserialize(transaction_bytes)
            
            # Sign the transaction
            transaction.sign([self.keypair])
            
            # Send the transaction
            response = await self.client.send_transaction(transaction)
            
            if hasattr(response, 'value'):
                tx_signature = str(response.value)
                logger.info(f"📤 Transaction sent: {tx_signature}")
                
                # Wait for confirmation (optional but recommended)
                await self._wait_for_confirmation(tx_signature)
                
                return tx_signature
            else:
                logger.error("❌ Transaction send failed")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error executing transaction: {e}")
            return None
    
    async def _wait_for_confirmation(self, tx_signature: str, max_retries: int = 30):
        """Wait for transaction confirmation"""
        try:
            for i in range(max_retries):
                response = await self.client.get_signature_statuses([tx_signature])
                if response.value and response.value[0]:
                    status = response.value[0]
                    if status.confirmation_status:
                        logger.info(f"✅ Transaction confirmed: {tx_signature}")
                        return True
                
                await asyncio.sleep(2)  # Wait 2 seconds between checks
            
            logger.warning(f"⚠️ Transaction confirmation timeout: {tx_signature}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error waiting for confirmation: {e}")
            return False
    
    async def _mock_buy(self, token_mint: str) -> Dict:
        """Mock buy for testing"""
        import time
        return {
            'token_mint_address': token_mint,
            'buy_price_sol': 0.0001,
            'amount_bought_token': 1000000.0,
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
            
            Pubkey.from_string(address)
            return True
            
        except Exception:
            return False

# Add base64 import at the top
import base64

# Global instance
solana_service = SolanaService()

# Initialize function - this is what main.py calls
def init_solana_config_from_env():
    """Initialize global Solana service from environment"""
    try:
        solana_service.init_from_env()
        logger.info("✅ Solana service initialized successfully")
        return True
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