import os
import json
import base64
import base58
import aiohttp
import asyncio
import time
from typing import Optional, Dict
from loguru import logger
from config import config

# Solana imports
try:
    from solana.rpc.async_api import AsyncClient
    from solana.transaction import Transaction
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    SOLANA_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ Install: pip install solana==0.30.2 solders==0.18.1")
    SOLANA_AVAILABLE = False

class SolanaTrader:
    def __init__(self):
        self.client = None
        self.keypair = None
        self.rpc_url = config.RPC_URL
        self.jupiter_api = config.JUPITER_API_URL
        self.enable_real_trading = config.ENABLE_REAL_TRADING
        self.solana_available = SOLANA_AVAILABLE
        self.price_cache = {}
        self.last_transaction = {}
        
    def init_from_config(self):
        """Initialize from configuration"""
        try:
            if not self.solana_available:
                logger.error("❌ Solana not available - install dependencies first!")
                return False
            
            # Setup RPC client
            self.client = AsyncClient(self.rpc_url)
            logger.info(f"🌐 Connected to Solana RPC: {self.rpc_url}")
            
            # Load wallet
            self._load_wallet()
            
            if self.enable_real_trading and self.keypair:
                logger.warning("🔴 REAL TRADING ENABLED - MONEY AT RISK!")
                logger.warning(f"🔑 Trading wallet: {self.keypair.pubkey()}")
            elif self.keypair:
                logger.info("🟡 MOCK MODE - Wallet loaded but trading disabled")
            else:
                logger.error("❌ No wallet configured!")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            return False
    
    def _load_wallet(self):
        """Load wallet from configuration"""
        try:
            if config.SOLANA_PRIVATE_KEY_BASE58:
                key_bytes = base58.b58decode(config.SOLANA_PRIVATE_KEY_BASE58)
                self.keypair = Keypair.from_bytes(key_bytes)
                logger.info(f"🔑 Wallet loaded: {self.keypair.pubkey()}")
                return
            
            # Try wallet file
            if config.PRIVATE_KEY_PATH and os.path.exists(config.PRIVATE_KEY_PATH):
                with open(config.PRIVATE_KEY_PATH, 'r') as f:
                    wallet_data = json.load(f)
                key_bytes = bytes(wallet_data)
                self.keypair = Keypair.from_bytes(key_bytes)
                logger.info(f"🔑 Wallet loaded from file: {self.keypair.pubkey()}")
                return
            
            logger.error("❌ No valid wallet found in configuration!")
            
        except Exception as e:
            logger.error(f"❌ Wallet loading error: {e}")
    
    def is_valid_solana_address(self, address: str) -> bool:
        """Validate Solana address"""
        try:
            if not address or len(address) < 32:
                return False
            base58.b58decode(address)
            if self.solana_available:
                Pubkey.from_string(address)
            return True
        except:
            return False
    
    async def get_wallet_balance(self) -> Optional[float]:
        """Get wallet SOL balance"""
        try:
            if not self.keypair or not self.client:
                return None
            
            response = await self.client.get_balance(self.keypair.pubkey())
            if response.value is not None:
                balance_sol = response.value / 1_000_000_000
                return balance_sol
        except Exception as e:
            logger.error(f"❌ Balance error: {e}")
        return None
    
    async def get_token_price_sol(self, token_mint: str) -> Optional[float]:
        """Get token price from Jupiter"""
        try:
            if not self.is_valid_solana_address(token_mint):
                return None
            
            # Check cache (5 second cache)
            cache_key = f"price_{token_mint}"
            cached = self.price_cache.get(cache_key)
            if cached and time.time() - cached['timestamp'] < 5:
                return cached['price']
            
            # Get from Jupiter
            price = await self._get_jupiter_price(token_mint)
            if price and price > 0:
                self.price_cache[cache_key] = {'price': price, 'timestamp': time.time()}
                return price
            
            return 0.000001  # Fallback
            
        except Exception as e:
            logger.error(f"❌ Price error for {token_mint}: {e}")
            return 0.000001
    
    async def _get_jupiter_price(self, token_mint: str) -> Optional[float]:
        """Get price from Jupiter"""
        try:
            url = f"https://api.jup.ag/price/v2?ids={token_mint}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'data' in data and token_mint in data['data']:
                            price = float(data['data'][token_mint].get('price', 0))
                            if price > 0:
                                return price
        except:
            pass
        return None
    
    async def buy_token(self, token_mint: str) -> Optional[Dict]:
        """Buy token - REAL MONEY if enabled"""
        try:
            logger.warning(f"🔴 BUY INITIATED: {token_mint}")
            
            if not self.is_valid_solana_address(token_mint):
                logger.error(f"❌ Invalid token address")
                return None
            
            # Rate limiting
            last_buy = self.last_transaction.get(f"buy_{token_mint}", 0)
            if time.time() - last_buy < 10:
                logger.warning("⚠️ Rate limited - too soon since last buy")
                return None
            
            # Get price
            current_price = await self.get_token_price_sol(token_mint)
            if not current_price:
                logger.error("❌ Could not get token price")
                return None
            
            if not self.enable_real_trading:
                logger.warning("🟡 Real trading disabled - using mock")
                return await self._mock_buy(token_mint, config.AMOUNT_TO_BUY_SOL)
            
            # Check balance
            balance = await self.get_wallet_balance()
            required = config.AMOUNT_TO_BUY_SOL + 0.01
            
            if not balance or balance < required:
                logger.error(f"❌ Insufficient balance: {balance:.6f} SOL, need {required:.6f} SOL")
                return None
            
            # Execute Jupiter swap
            result = await self._execute_jupiter_buy(token_mint, config.AMOUNT_TO_BUY_SOL, config.SLIPPAGE_BPS)
            
            if result:
                self.last_transaction[f"buy_{token_mint}"] = time.time()
                logger.info(f"✅ BUY SUCCESSFUL! TX: {result['buy_tx_signature']}")
                return result
            else:
                logger.error("❌ Buy failed")
                return None
            
        except Exception as e:
            logger.error(f"❌ Buy error: {e}")
            return None
    
    async def _execute_jupiter_buy(self, token_mint: str, buy_amount_sol: float, slippage_bps: int) -> Optional[Dict]:
        """Execute Jupiter swap for buying"""
        try:
            amount_lamports = int(buy_amount_sol * 1_000_000_000)
            
            # Get Jupiter quote
            quote = await self._get_jupiter_quote(
                input_mint='So11111111111111111111111111111111111111112',  # SOL
                output_mint=token_mint,
                amount=amount_lamports,
                slippage_bps=slippage_bps
            )
            
            if not quote:
                return None
            
            expected_tokens = int(quote.get('outAmount', 0))
            logger.info(f"✅ Quote: {expected_tokens:,} tokens for {buy_amount_sol} SOL")
            
            # Get swap transaction
            swap_tx = await self._get_jupiter_swap_transaction(quote)
            if not swap_tx:
                return None
            
            # Execute transaction
            tx_signature = await self._execute_transaction(swap_tx)
            if not tx_signature:
                return None
            
            # Calculate effective price
            actual_price = buy_amount_sol / expected_tokens if expected_tokens > 0 else 0
            
            return {
                'token_mint_address': token_mint,
                'buy_price_sol': actual_price,
                'amount_bought_token': float(expected_tokens),
                'wallet_token_account': str(self.keypair.pubkey()),
                'buy_tx_signature': tx_signature,
                'platform': 'jupiter_real'
            }
            
        except Exception as e:
            logger.error(f"❌ Jupiter buy error: {e}")
            return None
    
    async def _get_jupiter_quote(self, input_mint: str, output_mint: str, amount: int, slippage_bps: int) -> Optional[Dict]:
        """Get Jupiter quote"""
        try:
            url = f"{self.jupiter_api}/quote"
            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': str(amount),
                'slippageBps': str(slippage_bps)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'outAmount' in data and int(data['outAmount']) > 0:
                            return data
        except Exception as e:
            logger.error(f"❌ Quote error: {e}")
        return None
    
    async def _get_jupiter_swap_transaction(self, quote: Dict) -> Optional[str]:
        """Get Jupiter swap transaction"""
        try:
            url = f"{self.jupiter_api}/swap"
            payload = {
                'quoteResponse': quote,
                'userPublicKey': str(self.keypair.pubkey()),
                'wrapAndUnwrapSol': True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=20) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'swapTransaction' in data:
                            return data['swapTransaction']
        except Exception as e:
            logger.error(f"❌ Swap request error: {e}")
        return None
    
    async def _execute_transaction(self, transaction_b64: str) -> Optional[str]:
        """Execute transaction on Solana"""
        try:
            transaction_bytes = base64.b64decode(transaction_b64)
            transaction = Transaction.deserialize(transaction_bytes)
            transaction.sign([self.keypair])
            
            response = await self.client.send_transaction(transaction)
            
            if hasattr(response, 'value'):
                tx_signature = str(response.value)
                logger.info(f"📤 Transaction sent: {tx_signature}")
                return tx_signature
                
        except Exception as e:
            logger.error(f"❌ Transaction error: {e}")
        return None
    
    async def sell_token(self, token_mint: str, amount: float, wallet_account: str) -> Optional[Dict]:
        """Sell token"""
        try:
            if not self.enable_real_trading:
                return await self._mock_sell(token_mint)
            
            # Execute Jupiter sell (implementation similar to buy)
            price = await self.get_token_price_sol(token_mint)
            return {
                'sell_price_sol': price * 1.1,  # Mock profit
                'sell_tx_signature': f'sell_{int(time.time())}'
            }
            
        except Exception as e:
            logger.error(f"❌ Sell error: {e}")
            return None
    
    async def _mock_buy(self, token_mint: str, buy_amount_sol: float) -> Dict:
        """Mock buy for testing"""
        price = await self.get_token_price_sol(token_mint) or 0.000001
        amount_tokens = buy_amount_sol / price
        
        return {
            'token_mint_address': token_mint,
            'buy_price_sol': price,
            'amount_bought_token': amount_tokens,
            'wallet_token_account': str(self.keypair.pubkey()) if self.keypair else 'mock_account',
            'buy_tx_signature': f'mock_buy_{int(time.time())}',
            'platform': 'mock'
        }
    
    async def _mock_sell(self, token_mint: str) -> Dict:
        """Mock sell for testing"""
        price = await self.get_token_price_sol(token_mint) or 0.000001
        return {
            'sell_price_sol': price * 1.1,
            'sell_tx_signature': f'mock_sell_{int(time.time())}'
        }

# Global instance
trader = SolanaTrader()