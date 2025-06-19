import os
import json
import base64
import base58
import aiohttp
import asyncio
import time
from typing import Optional, Dict, List
from loguru import logger
from dotenv import load_dotenv

# Solana imports
try:
    from solana.rpc.async_api import AsyncClient
    from solana.transaction import Transaction
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    from solders.instruction import Instruction
    from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
    SOLANA_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ Install: pip install solana==0.30.2 solders==0.18.1")
    SOLANA_AVAILABLE = False

load_dotenv()

class RealSolanaTrader:
    def __init__(self):
        self.client = None
        self.keypair = None
        self.rpc_url = os.getenv('RPC_URL', 'https://api.mainnet-beta.solana.com')
        self.jupiter_api = 'https://quote-api.jup.ag/v6'
        self.enable_real_trading = os.getenv('ENABLE_REAL_TRADING', 'false').lower() == 'true'
        self.solana_available = SOLANA_AVAILABLE
        self.price_cache = {}
        self.last_transaction = {}
        
    def init_from_env(self):
        """Initialize real trading service"""
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
        """Load wallet from environment"""
        try:
            private_key_b58 = os.getenv('SOLANA_PRIVATE_KEY_BASE58')
            if private_key_b58:
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
            
            logger.error("❌ No valid wallet found in environment!")
            
        except Exception as e:
            logger.error(f"❌ Wallet loading error: {e}")
    
    async def get_token_price_sol(self, token_mint: str) -> Optional[float]:
        """Get token price from multiple sources"""
        try:
            if not self._is_valid_address(token_mint):
                return None
            
            # Check cache first (5 second cache)
            cache_key = f"price_{token_mint}"
            cached = self.price_cache.get(cache_key)
            if cached and time.time() - cached['timestamp'] < 5:
                return cached['price']
            
            # Try multiple price sources
            price = None
            
            # 1. Jupiter Price API
            price = await self._get_jupiter_price(token_mint)
            if price and price > 0:
                self._cache_price(cache_key, price)
                return price
            
            # 2. DexScreener
            price = await self._get_dexscreener_price(token_mint)
            if price and price > 0:
                self._cache_price(cache_key, price)
                return price
            
            # 3. Birdeye
            price = await self._get_birdeye_price(token_mint)
            if price and price > 0:
                self._cache_price(cache_key, price)
                return price
            
            # 4. Pump.fun API (untuk pump tokens)
            price = await self._get_pumpfun_price(token_mint)
            if price and price > 0:
                self._cache_price(cache_key, price)
                return price
            
            logger.warning(f"⚠️ No price found for {token_mint}, using fallback")
            return 0.000001  # Very small fallback
            
        except Exception as e:
            logger.error(f"❌ Price error for {token_mint}: {e}")
            return 0.000001
    
    def _cache_price(self, cache_key: str, price: float):
        """Cache price with timestamp"""
        self.price_cache[cache_key] = {
            'price': price,
            'timestamp': time.time()
        }
    
    async def _get_jupiter_price(self, token_mint: str) -> Optional[float]:
        """Get price from Jupiter"""
        try:
            endpoints = [
                f"https://api.jup.ag/price/v2?ids={token_mint}",
                f"{self.jupiter_api}/price?ids={token_mint}&vsToken=So11111111111111111111111111111111111111112"
            ]
            
            for endpoint in endpoints:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(endpoint, timeout=5) as response:
                            if response.status == 200:
                                data = await response.json()
                                if 'data' in data and token_mint in data['data']:
                                    price = float(data['data'][token_mint].get('price', 0))
                                elif token_mint in data:
                                    price = float(data[token_mint].get('price', 0))
                                else:
                                    continue
                                
                                if price > 0:
                                    logger.debug(f"💰 Jupiter price: {price:.12f} SOL")
                                    return price
                except:
                    continue
        except:
            pass
        return None
    
    async def _get_dexscreener_price(self, token_mint: str) -> Optional[float]:
        """Get price from DexScreener"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_mint}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'pairs' in data and len(data['pairs']) > 0:
                            for pair in data['pairs']:
                                if pair.get('quoteToken', {}).get('symbol') == 'SOL':
                                    price = float(pair.get('priceNative', 0))
                                    if price > 0:
                                        logger.debug(f"💰 DexScreener: {price:.12f} SOL")
                                        return price
        except:
            pass
        return None
    
    async def _get_birdeye_price(self, token_mint: str) -> Optional[float]:
        """Get price from Birdeye"""
        try:
            url = f"https://public-api.birdeye.so/defi/price"
            params = {'address': token_mint}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success') and 'data' in data:
                            usd_price = float(data['data'].get('value', 0))
                            if usd_price > 0:
                                sol_usd = await self._get_sol_usd_price()
                                price_sol = usd_price / sol_usd if sol_usd else 0
                                if price_sol > 0:
                                    logger.debug(f"💰 Birdeye: {price_sol:.12f} SOL")
                                    return price_sol
        except:
            pass
        return None
    
    async def _get_pumpfun_price(self, token_mint: str) -> Optional[float]:
        """Get price from Pump.fun API"""
        try:
            url = f"https://frontend-api.pump.fun/coins/{token_mint}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'usd_market_cap' in data and 'supply' in data:
                            market_cap = float(data.get('usd_market_cap', 0))
                            supply = float(data.get('supply', 0))
                            if market_cap > 0 and supply > 0:
                                usd_price = market_cap / supply
                                sol_usd = await self._get_sol_usd_price()
                                price_sol = usd_price / sol_usd if sol_usd else 0
                                if price_sol > 0:
                                    logger.debug(f"💰 Pump.fun: {price_sol:.12f} SOL")
                                    return price_sol
        except:
            pass
        return None
    
    async def _get_sol_usd_price(self) -> float:
        """Get SOL/USD price"""
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get('solana', {}).get('usd', 100))
        except:
            pass
        return 100.0  # Fallback
    
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
    
    async def buy_token_real(self, token_mint: str) -> Optional[Dict]:
        """🔴 REAL BUY FUNCTION - ACTUAL MONEY AT RISK!"""
        try:
            logger.warning(f"🔴 REAL BUY INITIATED: {token_mint}")
            
            if not self._is_valid_address(token_mint):
                logger.error(f"❌ Invalid token address")
                return None
            
            # Get trading settings
            buy_amount_sol = float(os.getenv('AMOUNT_TO_BUY_SOL', '0.005'))
            slippage_bps = int(os.getenv('SLIPPAGE_BPS', '1500'))
            
            # Safety checks
            if not self.enable_real_trading:
                logger.warning("🚨 Real trading disabled - using mock")
                return await self._mock_buy(token_mint, buy_amount_sol)
            
            if not self.keypair:
                logger.error("❌ No wallet configured")
                return None
            
            # Rate limiting - max 1 buy per token per 10 seconds
            last_buy = self.last_transaction.get(f"buy_{token_mint}", 0)
            if time.time() - last_buy < 10:
                logger.warning("⚠️ Rate limited - too soon since last buy")
                return None
            
            # Check balance
            balance = await self.get_wallet_balance()
            required = buy_amount_sol + 0.01  # Extra for fees
            
            if not balance or balance < required:
                logger.error(f"❌ Insufficient balance: {balance:.6f} SOL, need {required:.6f} SOL")
                return None
            
            # Get current price
            current_price = await self.get_token_price_sol(token_mint)
            if not current_price:
                logger.error("❌ Could not get token price")
                return None
            
            logger.warning(f"🔴 EXECUTING REAL BUY:")
            logger.warning(f"   💰 Amount: {buy_amount_sol} SOL")
            logger.warning(f"   🪙 Token: {token_mint}")
            logger.warning(f"   💵 Price: {current_price:.12f} SOL")
            logger.warning(f"   📊 Slippage: {slippage_bps/100:.1f}%")
            
            # Execute Jupiter swap
            result = await self._execute_jupiter_buy(token_mint, buy_amount_sol, slippage_bps)
            
            if result:
                # Update rate limit
                self.last_transaction[f"buy_{token_mint}"] = time.time()
                
                logger.info(f"✅ REAL BUY SUCCESSFUL!")
                logger.info(f"   🔗 TX: {result['buy_tx_signature']}")
                logger.info(f"   📊 Got: {result['amount_bought_token']:,.0f} tokens")
                
                return result
            else:
                logger.error("❌ Real buy failed")
                return None
            
        except Exception as e:
            logger.error(f"❌ Buy error: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return None
    
    async def _execute_jupiter_buy(self, token_mint: str, buy_amount_sol: float, slippage_bps: int) -> Optional[Dict]:
        """Execute Jupiter swap for buying"""
        try:
            amount_lamports = int(buy_amount_sol * 1_000_000_000)
            
            # Step 1: Get Jupiter quote
            logger.info(f"🔄 Getting Jupiter quote...")
            quote = await self._get_jupiter_quote(
                input_mint='So11111111111111111111111111111111111111112',  # SOL
                output_mint=token_mint,
                amount=amount_lamports,
                slippage_bps=slippage_bps
            )
            
            if not quote:
                logger.error("❌ Jupiter quote failed")
                return None
            
            expected_tokens = int(quote.get('outAmount', 0))
            logger.info(f"✅ Quote: {expected_tokens:,} tokens for {buy_amount_sol} SOL")
            
            # Step 2: Get swap transaction
            logger.info(f"🔄 Getting swap transaction...")
            swap_tx = await self._get_jupiter_swap_transaction(quote)
            if not swap_tx:
                logger.error("❌ Swap transaction failed")
                return None
            
            # Step 3: Execute transaction
            logger.info(f"🔄 Executing transaction on blockchain...")
            tx_signature = await self._execute_transaction(swap_tx)
            if not tx_signature:
                logger.error("❌ Transaction execution failed")
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
                'slippageBps': str(slippage_bps),
                'onlyDirectRoutes': 'false',
                'asLegacyTransaction': 'false'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'outAmount' in data and int(data['outAmount']) > 0:
                            return data
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Jupiter quote error {response.status}: {error_text}")
        except Exception as e:
            logger.error(f"❌ Quote request error: {e}")
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
                'prioritizationFeeLamports': {
                    'auto': {}
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=20) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('swapTransaction')
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Jupiter swap error {response.status}: {error_text}")
        except Exception as e:
            logger.error(f"❌ Swap request error: {e}")
        return None
    
    async def _execute_transaction(self, transaction_b64: str) -> Optional[str]:
        """Execute transaction on Solana"""
        try:
            # Decode and sign transaction
            transaction_bytes = base64.b64decode(transaction_b64)
            transaction = Transaction.deserialize(transaction_bytes)
            transaction.sign([self.keypair])
            
            # Send transaction
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
            
        except Exception as e:
            logger.error(f"❌ Transaction error: {e}")
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
                    logger.info(f"⏳ Waiting for confirmation... ({i+1}/{max_retries})")
            
            logger.warning(f"⚠️ Confirmation timeout: {tx_signature}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Confirmation error: {e}")
            return False
    
    async def sell_token_real(self, token_mint: str, amount: float, wallet_account: str) -> Optional[Dict]:
        """🔴 REAL SELL FUNCTION - ACTUAL MONEY AT RISK!"""
        try:
            logger.warning(f"🔴 REAL SELL INITIATED: {token_mint}")
            
            if not self.enable_real_trading:
                return await self._mock_sell(token_mint)
            
            if not self.keypair:
                logger.error("❌ No wallet for selling")
                return None
            
            # Rate limiting
            last_sell = self.last_transaction.get(f"sell_{token_mint}", 0)
            if time.time() - last_sell < 10:
                logger.warning("⚠️ Rate limited - too soon since last sell")
                return None
            
            # Execute Jupiter sell
            result = await self._execute_jupiter_sell(token_mint, int(amount))
            
            if result:
                self.last_transaction[f"sell_{token_mint}"] = time.time()
                logger.info(f"✅ REAL SELL SUCCESSFUL!")
                logger.info(f"   🔗 TX: {result['sell_tx_signature']}")
                return result
            
        except Exception as e:
            logger.error(f"❌ Sell error: {e}")
        return None
    
    async def _execute_jupiter_sell(self, token_mint: str, amount: int) -> Optional[Dict]:
        """Execute Jupiter sell"""
        try:
            slippage_bps = int(os.getenv('SLIPPAGE_BPS', '1500'))
            
            # Get sell quote
            quote = await self._get_jupiter_quote(
                input_mint=token_mint,
                output_mint='So11111111111111111111111111111111111111112',  # SOL
                amount=amount,
                slippage_bps=slippage_bps
            )
            
            if not quote:
                return None
            
            # Get swap transaction
            swap_tx = await self._get_jupiter_swap_transaction(quote)
            if not swap_tx:
                return None
            
            # Execute
            tx_signature = await self._execute_transaction(swap_tx)
            if not tx_signature:
                return None
            
            # Calculate SOL received
            sol_received = int(quote.get('outAmount', 0)) / 1_000_000_000
            
            return {
                'sell_price_sol': sol_received,
                'sell_tx_signature': tx_signature
            }
            
        except Exception as e:
            logger.error(f"❌ Jupiter sell error: {e}")
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
            'sell_price_sol': price * 1.1,  # 10% profit simulation
            'sell_tx_signature': f'mock_sell_{int(time.time())}'
        }
    
    def _is_valid_address(self, address: str) -> bool:
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

# Global instance
real_trader = RealSolanaTrader()

# Wrapper functions
async def init_real_trading():
    """Initialize real trading service"""
    return real_trader.init_from_env()

async def get_token_price_sol(token_mint):
    """Get token price"""
    return await real_trader.get_token_price_sol(str(token_mint))

async def buy_token_solana(token_mint_address: str):
    """Buy token - REAL MONEY"""
    return await real_trader.buy_token_real(token_mint_address)

async def sell_token_solana(token_mint_address: str, amount: float, wallet_token_account: str):
    """Sell token - REAL MONEY"""
    return await real_trader.sell_token_real(token_mint_address, amount, wallet_token_account)

def is_valid_solana_address(address: str) -> bool:
    """Validate address"""
    return real_trader._is_valid_address(address)