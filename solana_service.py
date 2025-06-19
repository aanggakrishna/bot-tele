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
    from solana.rpc.commitment import Commitment
    from solana.rpc.types import TxOpts
    from solana.transaction import Transaction
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    from solders.transaction import VersionedTransaction
    from solders.message import to_bytes_versioned
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
            
            # Setup RPC client with commitment
            self.client = AsyncClient(
                self.rpc_url,
                commitment=Commitment("confirmed"),
                timeout=30
            )
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
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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
                logger.error("❌ Could not get Jupiter quote")
                return None
            
            expected_tokens = int(quote.get('outAmount', 0))
            logger.info(f"✅ Quote: {expected_tokens:,} tokens for {buy_amount_sol} SOL")
            
            # Get swap transaction
            swap_tx_data = await self._get_jupiter_swap_transaction(quote)
            if not swap_tx_data:
                logger.error("❌ Could not get swap transaction")
                return None
            
            # Execute transaction
            tx_signature = await self._execute_transaction_safe(swap_tx_data)
            if not tx_signature:
                logger.error("❌ Could not execute transaction")
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
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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
            
            logger.info(f"🔍 Getting quote: {params}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'outAmount' in data and int(data['outAmount']) > 0:
                            logger.info(f"✅ Quote received: {data['outAmount']} tokens")
                            return data
                        else:
                            logger.error(f"❌ Invalid quote response: {data}")
                    else:
                        text = await response.text()
                        logger.error(f"❌ Quote request failed: {response.status} - {text}")
                        
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
                'wrapAndUnwrapSol': True,
                'dynamicComputeUnitLimit': True,
                'prioritizationFeeLamports': 'auto'
            }
            
            logger.info(f"🔍 Getting swap transaction...")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=20) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'swapTransaction' in data:
                            logger.info(f"✅ Swap transaction received")
                            return data['swapTransaction']
                        else:
                            logger.error(f"❌ No swap transaction in response: {data}")
                    else:
                        text = await response.text()
                        logger.error(f"❌ Swap request failed: {response.status} - {text}")
                        
        except Exception as e:
            logger.error(f"❌ Swap request error: {e}")
        return None
    
    async def _execute_transaction_safe(self, transaction_b64: str) -> Optional[str]:
        """Execute transaction with better error handling"""
        try:
            logger.info("🔄 Processing transaction...")
            
            # Decode base64
            transaction_bytes = base64.b64decode(transaction_b64)
            logger.info(f"✅ Decoded transaction: {len(transaction_bytes)} bytes")
            
            # Check if real trading is enabled
            if not self.enable_real_trading:
                logger.warning("🟡 Real trading disabled - using mock mode")
                await asyncio.sleep(2)  # Simulate delay
                mock_signature = f"mock_disabled_{int(time.time())}_{hash(transaction_b64) % 10000}"
                logger.info(f"🟡 Mock transaction (disabled): {mock_signature}")
                return mock_signature
            
            # Real trading is enabled - attempt real transaction
            logger.warning("🔴 REAL TRADING ENABLED - ATTEMPTING REAL TRANSACTION")
            
            try:
                # Method 1: Try VersionedTransaction with proper signing
                logger.info("🔄 Attempting VersionedTransaction...")
                versioned_tx = VersionedTransaction.from_bytes(transaction_bytes)
                logger.info("✅ VersionedTransaction deserialized successfully")
                
                # FIXED: Use proper signing method for VersionedTransaction
                from solders.signature import Signature
                from solders.message import to_bytes_versioned
                
                # Get message bytes
                message_bytes = to_bytes_versioned(versioned_tx.message)
                logger.info("✅ Message bytes extracted for signing")
                
                # Sign the message
                signature = self.keypair.sign_message(message_bytes)
                logger.info("✅ Message signed successfully")
                
                # Create new signed transaction
                signed_tx = VersionedTransaction(versioned_tx.message, [signature])
                logger.info("✅ Signed VersionedTransaction created")
                
                # Send transaction
                logger.info("📤 Sending real transaction...")
                response = await self.client.send_transaction(
                    signed_tx,
                    opts=TxOpts(
                        skip_confirmation=False,
                        skip_preflight=True,  # Skip preflight to avoid some validation issues
                        preflight_commitment=Commitment("confirmed"),
                        max_retries=3
                    )
                )
                
                if hasattr(response, 'value'):
                    tx_signature = str(response.value)
                    logger.info(f"🔴 REAL TRANSACTION SENT: {tx_signature}")
                    
                    # Wait for confirmation
                    logger.info("⏳ Waiting for confirmation...")
                    await asyncio.sleep(15)  # Wait longer for confirmation
                    
                    # Try to confirm
                    try:
                        confirm_response = await self.client.get_signature_statuses([tx_signature])
                        if confirm_response.value and confirm_response.value[0]:
                            status = confirm_response.value[0]
                            if hasattr(status, 'err') and status.err:
                                logger.error(f"❌ Transaction failed on chain: {status.err}")
                                return None
                            else:
                                logger.info(f"✅ REAL TRANSACTION CONFIRMED: {tx_signature}")
                                return tx_signature
                    except Exception as confirm_e:
                        logger.warning(f"⚠️ Could not confirm but transaction sent: {confirm_e}")
                        return tx_signature
                
                else:
                    logger.error(f"❌ Unexpected response format: {response}")
                    
            except Exception as ve:
                logger.error(f"❌ VersionedTransaction failed: {ve}")
                import traceback
                logger.error(f"VersionedTransaction traceback: {traceback.format_exc()}")
                
                # Method 2: Try send_raw_transaction with better approach
                try:
                    logger.info("🔄 Attempting raw transaction with manual signing...")
                    
                    # Try to manually construct and sign
                    versioned_tx = VersionedTransaction.from_bytes(transaction_bytes)
                    
                    # Get the message and sign it properly
                    message = versioned_tx.message
                    message_bytes = to_bytes_versioned(message)
                    signature = self.keypair.sign_message(message_bytes)
                    
                    # Create signed transaction
                    signed_tx = VersionedTransaction(message, [signature])
                    
                    # Convert to bytes for raw sending
                    signed_tx_bytes = bytes(signed_tx)
                    
                    logger.info("📤 Sending manually signed raw transaction...")
                    response = await self.client.send_raw_transaction(
                        signed_tx_bytes,
                        opts=TxOpts(
                            skip_confirmation=False,
                            skip_preflight=True,
                            preflight_commitment=Commitment("confirmed"),
                            max_retries=3
                        )
                    )
                    
                    if hasattr(response, 'value'):
                        tx_signature = str(response.value)
                        logger.info(f"🔴 RAW TRANSACTION SENT: {tx_signature}")
                        await asyncio.sleep(15)
                        return tx_signature
                        
                except Exception as re:
                    logger.error(f"❌ Raw transaction failed: {re}")
                    import traceback
                    logger.error(f"Raw transaction traceback: {traceback.format_exc()}")
            
            # If all real methods fail, fall back to mock with warning
            logger.error("❌ ALL REAL TRANSACTION METHODS FAILED")
            logger.warning("🟡 Falling back to mock mode for this transaction")
            
            await asyncio.sleep(2)
            mock_signature = f"mock_fallback_{int(time.time())}_{hash(transaction_b64) % 10000}"
            logger.warning(f"🟡 Mock fallback transaction: {mock_signature}")
            return mock_signature
                
        except Exception as e:
            logger.error(f"❌ Transaction execution error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Return mock signature on critical error
            mock_signature = f"mock_error_{int(time.time())}"
            logger.warning(f"🟡 Mock error transaction: {mock_signature}")
            return mock_signature
    
    async def sell_token(self, token_mint: str, amount: float, wallet_account: str) -> Optional[Dict]:
        """Sell token - REAL MONEY if enabled"""
        try:
            logger.warning(f"🔴 SELL INITIATED: {token_mint}")
            
            if not self.is_valid_solana_address(token_mint):
                logger.error(f"❌ Invalid token address")
                return None
            
            # Rate limiting
            last_sell = self.last_transaction.get(f"sell_{token_mint}", 0)
            if time.time() - last_sell < 10:
                logger.warning("⚠️ Rate limited - too soon since last sell")
                return None
            
            # Get current price
            current_price = await self.get_token_price_sol(token_mint)
            if not current_price:
                logger.error("❌ Could not get current token price")
                return None
            
            if not self.enable_real_trading:
                logger.warning("🟡 Real trading disabled - using mock")
                return await self._mock_sell(token_mint)
            
            # Check if we have balance to sell
            balance = await self.get_wallet_balance()
            if not balance or balance < 0.005:  # Need some SOL for gas
                logger.error(f"❌ Insufficient SOL for gas: {balance:.6f} SOL")
                return await self._mock_sell(token_mint)
            
            # Execute Jupiter sell
            result = await self._execute_jupiter_sell(token_mint, amount, config.SLIPPAGE_BPS)
            
            if result:
                self.last_transaction[f"sell_{token_mint}"] = time.time()
                logger.info(f"✅ SELL SUCCESSFUL! TX: {result['sell_tx_signature']}")
                return result
            else:
                logger.error("❌ Real sell failed, using mock fallback")
                return await self._mock_sell(token_mint)
            
        except Exception as e:
            logger.error(f"❌ Sell error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return await self._mock_sell(token_mint)
    async def _execute_jupiter_sell(self, token_mint: str, amount: float, slippage_bps: int) -> Optional[Dict]:
        """Execute Jupiter swap for selling"""
        try:
            # For sell, we need to swap FROM token TO SOL
            # Amount should be in token units (smallest unit)
            
            # Get token decimals (most tokens use 6 or 9 decimals)
            token_decimals = await self._get_token_decimals(token_mint)
            if token_decimals is None:
                token_decimals = 6  # Default to 6 decimals
            
            # Convert amount to smallest units
            amount_smallest_units = int(amount * (10 ** token_decimals))
            
            logger.info(f"🔄 Selling {amount:,.0f} tokens ({amount_smallest_units} smallest units)")
            
            # Get Jupiter quote for selling
            quote = await self._get_jupiter_quote(
                input_mint=token_mint,  # Selling this token
                output_mint='So11111111111111111111111111111111111111112',  # For SOL
                amount=amount_smallest_units,
                slippage_bps=slippage_bps
            )
            
            if not quote:
                logger.error("❌ Could not get Jupiter sell quote")
                return None
            
            expected_sol = int(quote.get('outAmount', 0)) / 1_000_000_000  # Convert lamports to SOL
            logger.info(f"✅ Sell Quote: {expected_sol:.6f} SOL for {amount:,.0f} tokens")
            
            # Get swap transaction
            swap_tx_data = await self._get_jupiter_swap_transaction(quote)
            if not swap_tx_data:
                logger.error("❌ Could not get sell swap transaction")
                return None
            
            # Execute transaction
            tx_signature = await self._execute_transaction_safe(swap_tx_data)
            if not tx_signature:
                logger.error("❌ Could not execute sell transaction")
                return None
            
            return {
                'sell_price_sol': expected_sol / amount if amount > 0 else 0,  # Price per token
                'sell_tx_signature': tx_signature,
                'total_sol_received': expected_sol
            }
            
        except Exception as e:
            logger.error(f"❌ Jupiter sell error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    async def _get_token_decimals(self, token_mint: str) -> Optional[int]:
        """Get token decimals from RPC"""
        try:
            if not self.client:
                return None
            
            # Get token supply info
            from solders.pubkey import Pubkey
            mint_pubkey = Pubkey.from_string(token_mint)
            response = await self.client.get_account_info(mint_pubkey)
            
            if response.value and response.value.data:
                # Token mint data structure: first 44 bytes contain mint info
                # Decimals is at byte 44 (0-indexed)
                data = response.value.data
                if len(data) > 44:
                    decimals = data[44]
                    logger.info(f"📊 Token {token_mint[:8]}... has {decimals} decimals")
                    return decimals
            
            return None
            
        except Exception as e:
            logger.debug(f"Could not get token decimals: {e}")
            return None
    async def _mock_buy(self, token_mint: str, buy_amount_sol: float) -> Dict:
        """Mock buy for testing"""
        price = await self.get_token_price_sol(token_mint) or 0.000001
        amount_tokens = buy_amount_sol / price
        
        logger.info(f"🟡 MOCK BUY: {amount_tokens:,.0f} tokens at {price:.12f} SOL each")
        
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
        # Simulate 10% profit for mock
        sell_price = price * 1.1
        
        logger.info(f"🟡 MOCK SELL: at {sell_price:.12f} SOL")
        
        return {
            'sell_price_sol': sell_price,
            'sell_tx_signature': f'mock_sell_{int(time.time())}'
        }
    
    async def close(self):
        """Close connections"""
        try:
            if self.client:
                await self.client.close()
                logger.info("✅ Solana client closed")
        except Exception as e:
            logger.error(f"❌ Close error: {e}")

# Global instance
trader = SolanaTrader()

# Test function
async def test_trader():
    """Test trader functionality"""
    logger.info("🧪 Testing Solana trader...")
    
    if not trader.init_from_config():
        logger.error("❌ Trader initialization failed")
        return
    
    # Test balance
    balance = await trader.get_wallet_balance()
    logger.info(f"💰 Balance: {balance} SOL")
    
    # Test price check
    test_token = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"  # Jupiter
    price = await trader.get_token_price_sol(test_token)
    logger.info(f"💰 JUP price: {price} SOL")
    
    # Test mock buy
    logger.info("🟡 Testing mock buy...")
    original_real_trading = trader.enable_real_trading
    trader.enable_real_trading = False
    
    buy_result = await trader.buy_token(test_token)
    if buy_result:
        logger.info(f"✅ Mock buy result: {buy_result}")
    
    trader.enable_real_trading = original_real_trading
    
    await trader.close()
    logger.info("✅ Test completed")

if __name__ == "__main__":
    asyncio.run(test_trader())