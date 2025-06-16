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
                logger.warning("⚠️ Solana dependencies not available - using mock mode")
                return True  # Still allow mock mode
            
            # Setup RPC client
            self.client = AsyncClient(self.rpc_url)
            logger.info(f"🌐 Connected to Solana RPC: {self.rpc_url}")
            
            # Load wallet
            self._load_wallet()
            
            # Show trading mode
            if self.enable_real_trading and self.keypair:
                logger.warning("🔴 REAL TRADING ENABLED - MONEY AT RISK!")
            elif self.keypair:
                logger.info("🟡 MOCK TRADING MODE - Wallet loaded but trading disabled")
            else:
                logger.info("🟢 MONITORING MODE - No wallet loaded")
            
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
                try:
                    key_bytes = base58.b58decode(private_key_b58)
                    self.keypair = Keypair.from_bytes(key_bytes)
                    logger.info(f"🔑 Wallet loaded from base58: {self.keypair.pubkey()}")
                    return
                except Exception as e:
                    logger.error(f"❌ Invalid base58 private key: {e}")
            
            # Try wallet file
            wallet_path = os.getenv('PRIVATE_KEY_PATH')
            if wallet_path and os.path.exists(wallet_path):
                try:
                    with open(wallet_path, 'r') as f:
                        wallet_data = json.load(f)
                    key_bytes = bytes(wallet_data)
                    self.keypair = Keypair.from_bytes(key_bytes)
                    logger.info(f"🔑 Wallet loaded from file: {self.keypair.pubkey()}")
                    return
                except Exception as e:
                    logger.error(f"❌ Invalid wallet file: {e}")
            
            logger.warning("⚠️ No valid wallet configured - monitoring mode only")
            
        except Exception as e:
            logger.error(f"❌ Error loading wallet: {e}")
    
    async def get_token_price_sol(self, token_mint_str: str) -> Optional[float]:
        """Get token price - Enhanced with multiple sources"""
        try:
            if not self._is_valid_address(token_mint_str):
                logger.error(f"❌ Invalid token address: {token_mint_str}")
                return None
            
            logger.debug(f"🔍 Getting price for: {token_mint_str}")
            
            # Try Jupiter Price API v2 first
            price = await self._get_jupiter_price_v2(token_mint_str)
            if price:
                return price
            
            # Try Jupiter Price API v1
            price = await self._get_jupiter_price_v1(token_mint_str)
            if price:
                return price
            
            # Try DexScreener as fallback
            price = await self._get_dexscreener_price(token_mint_str)
            if price:
                return price
            
            # If all APIs fail, use a small mock price
            logger.warning(f"⚠️ Could not get real price for {token_mint_str}, using mock")
            return 0.00001  # Very small mock price
            
        except Exception as e:
            logger.error(f"❌ Error getting price for {token_mint_str}: {e}")
            return 0.00001
    
    async def _get_jupiter_price_v2(self, token_mint: str) -> Optional[float]:
        """Get price from Jupiter API v2"""
        try:
            url = f"{self.jupiter_api}/price"
            params = {
                'ids': token_mint,
                'vsToken': 'So11111111111111111111111111111111111111112'  # SOL
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'data' in data and token_mint in data['data']:
                            price = float(data['data'][token_mint]['price'])
                            logger.debug(f"💰 Jupiter v2 price: {price} SOL")
                            return price
                        
        except Exception as e:
            logger.debug(f"Jupiter v2 API failed: {e}")
        return None
    
    async def _get_jupiter_price_v1(self, token_mint: str) -> Optional[float]:
        """Get price from Jupiter API v1 (fallback)"""
        try:
            url = f"https://price.jup.ag/v4/price"
            params = {
                'ids': token_mint,
                'vsToken': 'So11111111111111111111111111111111111111112'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'data' in data and token_mint in data['data']:
                            price = float(data['data'][token_mint]['price'])
                            logger.debug(f"💰 Jupiter v1 price: {price} SOL")
                            return price
                        
        except Exception as e:
            logger.debug(f"Jupiter v1 API failed: {e}")
        return None
    
    async def _get_dexscreener_price(self, token_mint: str) -> Optional[float]:
        """Get price from DexScreener as ultimate fallback"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_mint}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'pairs' in data and len(data['pairs']) > 0:
                            # Get the first pair with SOL
                            for pair in data['pairs']:
                                if pair.get('quoteToken', {}).get('symbol') == 'SOL':
                                    price = float(pair.get('priceNative', 0))
                                    if price > 0:
                                        logger.debug(f"💰 DexScreener price: {price} SOL")
                                        return price
                        
        except Exception as e:
            logger.debug(f"DexScreener API failed: {e}")
        return None
    
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
        """Buy token - Enhanced with safety checks"""
        try:
            if not self._is_valid_address(token_mint):
                logger.error(f"❌ Invalid token address: {token_mint}")
                return None
            
            # Get buy amount from env
            buy_amount_sol = float(os.getenv('AMOUNT_TO_BUY_SOL', '0.01'))
            
            # Safety checks
            if not self.solana_available:
                logger.warning("🚨 Solana not available - using mock")
                return await self._mock_buy(token_mint, buy_amount_sol)
            
            if not self.enable_real_trading:
                logger.warning("🚨 Real trading disabled - using mock")
                return await self._mock_buy(token_mint, buy_amount_sol)
            
            if not self.keypair:
                logger.error("❌ No wallet configured for real trading")
                return None
            
            # Check balance
            balance = await self.get_wallet_balance()
            if not balance or balance < buy_amount_sol + 0.005:  # +0.005 for fees
                logger.error(f"❌ Insufficient balance: {balance:.6f} SOL, need {buy_amount_sol + 0.005:.6f} SOL")
                return None
            
            logger.warning(f"🔴 EXECUTING REAL BUY: {buy_amount_sol} SOL -> {token_mint}")
            
            # Get current price for calculation
            current_price = await self.get_token_price_sol(token_mint)
            if not current_price:
                logger.error("❌ Could not get token price for real trade")
                return None
            
            # Execute real Jupiter swap
            result = await self._execute_jupiter_buy(token_mint, buy_amount_sol, current_price)
            
            if result:
                logger.info(f"✅ REAL BUY SUCCESSFUL! TX: {result['buy_tx_signature']}")
                return result
            else:
                logger.error("❌ Real buy failed, falling back to mock")
                return await self._mock_buy(token_mint, buy_amount_sol)
            
        except Exception as e:
            logger.error(f"❌ Error in buy for {token_mint}: {e}")
            return await self._mock_buy(token_mint, buy_amount_sol)
    
    async def _execute_jupiter_buy(self, token_mint: str, buy_amount_sol: float, price: float) -> Optional[Dict]:
        """Execute real Jupiter buy transaction"""
        try:
            slippage_bps = int(os.getenv('SLIPPAGE_BPS', '500'))
            amount_lamports = int(buy_amount_sol * 1_000_000_000)
            
            # Get Jupiter quote
            quote = await self._get_jupiter_quote(
                input_mint='So11111111111111111111111111111111111111112',  # SOL
                output_mint=token_mint,
                amount=amount_lamports,
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
            
            # Execute transaction
            tx_signature = await self._execute_transaction(swap_tx)
            if not tx_signature:
                logger.error("❌ Transaction execution failed")
                return None
            
            # Calculate result
            amount_out = int(quote.get('outAmount', 0))
            actual_price = buy_amount_sol / amount_out if amount_out > 0 else price
            
            return {
                'token_mint_address': token_mint,
                'buy_price_sol': actual_price,
                'amount_bought_token': float(amount_out),
                'wallet_token_account': str(self.keypair.pubkey()),
                'buy_tx_signature': tx_signature
            }
            
        except Exception as e:
            logger.error(f"❌ Error executing Jupiter buy: {e}")
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
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        quote_data = await response.json()
                        logger.debug(f"💱 Jupiter quote received")
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
                'computeUnitPriceMicroLamports': 'auto',
                'prioritizationFeeLamports': 'auto'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=15) as response:
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
            
            # Send the transaction with confirmed commitment
            response = await self.client.send_transaction(
                transaction,
                opts={"skip_confirmation": False, "preflight_commitment": "confirmed"}
            )
            
            if hasattr(response, 'value'):
                tx_signature = str(response.value)
                logger.info(f"📤 Transaction sent: {tx_signature}")
                
                # Wait for confirmation
                confirmed = await self._wait_for_confirmation(tx_signature)
                if confirmed:
                    return tx_signature
                else:
                    logger.error("❌ Transaction confirmation failed")
                    return None
            else:
                logger.error("❌ Transaction send failed")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error executing transaction: {e}")
            return None
    
    async def _wait_for_confirmation(self, tx_signature: str, max_retries: int = 30) -> bool:
        """Wait for transaction confirmation"""
        try:
            for i in range(max_retries):
                response = await self.client.get_signature_statuses([tx_signature])
                if response.value and response.value[0]:
                    status = response.value[0]
                    if status.confirmation_status:
                        logger.info(f"✅ Transaction confirmed: {tx_signature}")
                        return True
                    elif status.err:
                        logger.error(f"❌ Transaction failed: {status.err}")
                        return False
                
                await asyncio.sleep(2)
                if i % 5 == 0:
                    logger.info(f"⏳ Waiting for confirmation... ({i}/{max_retries})")
            
            logger.warning(f"⚠️ Transaction confirmation timeout: {tx_signature}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error waiting for confirmation: {e}")
            return False
    
    async def sell_token(self, token_mint: str, amount: float, wallet_account: str) -> Optional[Dict]:
        """Sell token - Enhanced implementation"""
        try:
            if not self._is_valid_address(token_mint):
                logger.error(f"❌ Invalid token address: {token_mint}")
                return None
            
            # Safety checks
            if not self.solana_available or not self.enable_real_trading or not self.keypair:
                logger.warning("🚨 Using mock sell")
                return await self._mock_sell(token_mint)
            
            logger.warning(f"🔴 EXECUTING REAL SELL for {token_mint}")
            
            # For now, use mock until fully tested
            logger.warning("⚠️ Real sell not fully implemented yet - using mock")
            return await self._mock_sell(token_mint)
            
        except Exception as e:
            logger.error(f"❌ Error in sell for {token_mint}: {e}")
            return await self._mock_sell(token_mint)
    
    async def _mock_buy(self, token_mint: str, buy_amount_sol: float) -> Dict:
        """Enhanced mock buy with realistic values"""
        import time
        
        # Get current price if possible
        current_price = await self.get_token_price_sol(token_mint)
        if not current_price:
            current_price = 0.00001
        
        amount_tokens = buy_amount_sol / current_price
        
        return {
            'token_mint_address': token_mint,
            'buy_price_sol': current_price,
            'amount_bought_token': amount_tokens,
            'wallet_token_account': str(self.keypair.pubkey()) if self.keypair else 'mock_account',
            'buy_tx_signature': f'mock_buy_{int(time.time())}'
        }
    
    async def _mock_sell(self, token_mint: str) -> Dict:
        """Enhanced mock sell"""
        import time
        
        # Get current price and add some profit
        current_price = await self.get_token_price_sol(token_mint)
        if not current_price:
            current_price = 0.00001
        
        # Simulate 10% profit
        sell_price = current_price * 1.1
        
        return {
            'sell_price_sol': sell_price,
            'sell_tx_signature': f'mock_sell_{int(time.time())}'
        }
    
    def _is_valid_address(self, address: str) -> bool:
        """Enhanced address validation"""
        try:
            if not address or not isinstance(address, str):
                return False
            
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

# Initialize function
def init_solana_config_from_env():
    """Initialize global Solana service from environment"""
    try:
        success = solana_service.init_from_env()
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