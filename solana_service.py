import asyncio
import json
import os
import base64
from typing import Optional, Dict, Any
import aiohttp
import base58
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.pubkey import Pubkey as PublicKey
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class SolanaService:
    def __init__(self):
        self.rpc_client = None
        self.keypair = None
        self.jupiter_api_url = os.getenv('JUPITER_API_URL', 'https://quote-api.jup.ag/v6')
        self.slippage_bps = int(os.getenv('SLIPPAGE_BPS', '500'))
        
    def init_solana_config_from_env(self):
        """Initialize Solana configuration from environment variables"""
        try:
            # Initialize RPC client
            rpc_url = os.getenv('RPC_URL', 'https://api.mainnet-beta.solana.com')
            self.rpc_client = AsyncClient(rpc_url)
            logger.info(f"🌐 Solana RPC client initialized: {rpc_url}")
            
            # Initialize wallet keypair
            private_key_base58 = os.getenv('SOLANA_PRIVATE_KEY_BASE58')
            wallet_path = os.getenv('PRIVATE_KEY_PATH')
            
            if private_key_base58 and private_key_base58 not in ['your_solana_private_key_base58', 'your_base58_private_key_from_generate_wallet_script']:
                # Use base58 private key
                try:
                    secret_key_bytes = base58.b58decode(private_key_base58)
                    if len(secret_key_bytes) != 32:
                        raise ValueError(f"Invalid secret key length: {len(secret_key_bytes)}. Expected 32 bytes.")
                    
                    self.keypair = Keypair.from_bytes(secret_key_bytes)
                    logger.info(f"🔑 Wallet loaded from base58 key: {self.keypair.pubkey()}")
                except Exception as e:
                    logger.error(f"❌ Error loading base58 private key: {e}")
                    raise
            elif wallet_path and os.path.exists(wallet_path):
                # Use wallet file
                try:
                    with open(wallet_path, 'r') as f:
                        wallet_data = json.load(f)
                    
                    # Handle different wallet formats
                    if len(wallet_data) == 32:
                        # Secret key only
                        secret_key_bytes = bytes(wallet_data)
                    elif len(wallet_data) == 64:
                        # Full keypair, take first 32 bytes
                        secret_key_bytes = bytes(wallet_data[:32])
                    else:
                        raise ValueError(f"Invalid wallet data length: {len(wallet_data)}")
                    
                    self.keypair = Keypair.from_bytes(secret_key_bytes)
                    logger.info(f"🔑 Wallet loaded from file: {self.keypair.pubkey()}")
                except Exception as e:
                    logger.error(f"❌ Error loading wallet file: {e}")
                    raise
            else:
                logger.warning("⚠️ No valid private key found. Bot will run in monitoring mode only.")
                logger.info("Please set SOLANA_PRIVATE_KEY_BASE58 in your .env file for trading functionality")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Solana config: {e}")
            raise

    async def get_token_price_sol(self, token_mint: PublicKey) -> Optional[float]:
        """Get token price in SOL using Jupiter API"""
        try:
            # Convert 1 token to SOL
            input_mint = str(token_mint)
            output_mint = "So11111111111111111111111111111111111111112"  # WSOL
            amount = 1000000  # 1 token with 6 decimals
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.jupiter_api_url}/quote"
                params = {
                    'inputMint': input_mint,
                    'outputMint': output_mint,
                    'amount': amount,
                    'slippageBps': self.slippage_bps
                }
                
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        out_amount = int(data['outAmount'])
                        # Convert lamports to SOL
                        price_sol = out_amount / 1_000_000_000  # 1 SOL = 1e9 lamports
                        return price_sol
                    else:
                        logger.warning(f"Jupiter quote API error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error getting token price: {e}")
            return None

    async def get_wallet_balance(self) -> Optional[float]:
        """Get wallet SOL balance"""
        try:
            if not self.keypair:
                return None
                
            response = await self.rpc_client.get_balance(self.keypair.pubkey())
            if response.value is not None:
                balance_sol = response.value / 1_000_000_000  # Convert lamports to SOL
                return balance_sol
            return None
            
        except Exception as e:
            logger.error(f"Error getting wallet balance: {e}")
            return None

    async def buy_token_solana(self, token_mint_address: str) -> Optional[Dict[str, Any]]:
        """Buy token using Jupiter swap"""
        try:
            logger.info(f"🔄 Initiating buy for token: {token_mint_address}")
            
            # Validate inputs
            if not self.keypair:
                raise ValueError("Wallet not initialized - cannot execute trades")
            
            # Check wallet balance
            balance = await self.get_wallet_balance()
            if balance is None:
                raise ValueError("Could not fetch wallet balance")
            
            sol_amount = float(os.getenv('AMOUNT_TO_BUY_SOL', '0.001'))
            if balance < sol_amount:
                raise ValueError(f"Insufficient balance. Need {sol_amount} SOL, have {balance} SOL")
            
            logger.info(f"💰 Wallet balance: {balance} SOL, buying with: {sol_amount} SOL")
            
            # Get quote from Jupiter
            lamports = int(sol_amount * 1_000_000_000)  # Convert SOL to lamports
            
            quote = await self._get_jupiter_quote(
                input_mint="So11111111111111111111111111111111111111112",  # WSOL
                output_mint=token_mint_address,
                amount=lamports,
                swap_mode="ExactIn"
            )
            
            if not quote:
                logger.error("Failed to get Jupiter quote")
                return None
            
            logger.info(f"📊 Quote received: {quote.get('outAmount', 'unknown')} tokens for {sol_amount} SOL")
            
            # Get swap transaction
            swap_tx = await self._get_jupiter_swap_transaction(quote)
            if not swap_tx:
                logger.error("Failed to get swap transaction")
                return None
            
            # Execute transaction
            tx_signature = await self._execute_transaction(swap_tx)
            if not tx_signature:
                logger.error("Failed to execute transaction")
                return None
            
            # Calculate results
            output_amount = int(quote['outAmount'])
            tokens_received = output_amount / 1_000_000  # Assuming 6 decimals
            price_per_token = sol_amount / tokens_received if tokens_received > 0 else 0
            
            result = {
                'token_mint_address': token_mint_address,
                'buy_price_sol': price_per_token,
                'amount_bought_token': tokens_received,
                'wallet_token_account': str(self.keypair.pubkey()),
                'buy_tx_signature': tx_signature
            }
            
            logger.info(f"✅ Buy successful: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error buying token: {e}")
            return None

    async def sell_token_solana(self, token_mint_address: str, amount_to_sell: float, 
                               wallet_token_account: str) -> Optional[Dict[str, Any]]:
        """Sell token using Jupiter swap"""
        try:
            logger.info(f"🔄 Initiating sell for token: {token_mint_address}")
            
            if not self.keypair:
                raise ValueError("Wallet not initialized - cannot execute trades")
            
            # Convert amount to proper decimals
            amount_lamports = int(amount_to_sell * 1_000_000)  # Assuming 6 decimals
            
            # Get quote from Jupiter
            quote = await self._get_jupiter_quote(
                input_mint=token_mint_address,
                output_mint="So11111111111111111111111111111111111111112",  # WSOL
                amount=amount_lamports,
                swap_mode="ExactIn"
            )
            
            if not quote:
                logger.error("Failed to get Jupiter sell quote")
                return None
            
            logger.info(f"📊 Sell quote received: {quote.get('outAmount', 'unknown')} lamports for {amount_to_sell} tokens")
            
            # Get swap transaction
            swap_tx = await self._get_jupiter_swap_transaction(quote)
            if not swap_tx:
                logger.error("Failed to get sell swap transaction")
                return None
            
            # Execute transaction
            tx_signature = await self._execute_transaction(swap_tx)
            if not tx_signature:
                logger.error("Failed to execute sell transaction")
                return None
            
            # Calculate results
            output_sol = int(quote['outAmount']) / 1_000_000_000  # Convert lamports to SOL
            price_per_token = output_sol / amount_to_sell if amount_to_sell > 0 else 0
            
            result = {
                'token_mint_address': token_mint_address,
                'sell_price_sol': price_per_token,
                'amount_sold_token': amount_to_sell,
                'sol_received': output_sol,
                'sell_tx_signature': tx_signature
            }
            
            logger.info(f"✅ Sell successful: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error selling token: {e}")
            return None

    async def _get_jupiter_quote(self, input_mint: str, output_mint: str, 
                                amount: int, swap_mode: str = "ExactIn") -> Optional[Dict]:
        """Get quote from Jupiter API"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.jupiter_api_url}/quote"
                params = {
                    'inputMint': input_mint,
                    'outputMint': output_mint,
                    'amount': amount,
                    'slippageBps': self.slippage_bps,
                    'swapMode': swap_mode
                }
                
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Jupiter quote error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error getting Jupiter quote: {e}")
            return None

    async def _get_jupiter_swap_transaction(self, quote: Dict) -> Optional[str]:
        """Get swap transaction from Jupiter API"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.jupiter_api_url}/swap"
                data = {
                    'quoteResponse': quote,
                    'userPublicKey': str(self.keypair.pubkey()),
                    'wrapAndUnwrapSol': True
                }
                
                async with session.post(url, json=data, timeout=15) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('swapTransaction')
                    else:
                        logger.error(f"Jupiter swap error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error getting Jupiter swap transaction: {e}")
            return None

    async def _execute_transaction(self, transaction_base64: str) -> Optional[str]:
        """Execute transaction on Solana network"""
        try:
            # Decode and deserialize transaction
            transaction_bytes = base64.b64decode(transaction_base64)
            transaction = VersionedTransaction.from_bytes(transaction_bytes)
            
            # Sign transaction - this might need adjustment based on solders version
            try:
                # Method 1: Try signing the transaction directly
                signed_tx = self.keypair.sign_message(transaction.message.serialize())
                transaction.signatures[0] = signed_tx
            except Exception as sign_e:
                logger.error(f"❌ Error signing transaction: {sign_e}")
                return None
            
            # Send transaction
            response = await self.rpc_client.send_transaction(transaction)
            
            if response.value:
                tx_signature = str(response.value)
                logger.info(f"✅ Transaction sent: {tx_signature}")
                
                # Wait for confirmation
                await asyncio.sleep(3)
                
                # Simple confirmation check
                try:
                    confirmation = await self.rpc_client.confirm_transaction(response.value)
                    if confirmation.value:
                        logger.info(f"✅ Transaction confirmed: {tx_signature}")
                        return tx_signature
                    else:
                        logger.warning(f"⚠️ Transaction confirmation unknown: {tx_signature}")
                        return tx_signature  # Return anyway, it might be confirmed
                except Exception as conf_e:
                    logger.warning(f"⚠️ Confirmation check failed: {conf_e}")
                    return tx_signature  # Return anyway
            else:
                logger.error("❌ Failed to send transaction")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error executing transaction: {e}")
            return None

# Global instance
solana_service_instance = SolanaService()

# Module-level functions for backward compatibility
def init_solana_config_from_env():
    return solana_service_instance.init_solana_config_from_env()

async def get_token_price_sol(token_mint):
    return await solana_service_instance.get_token_price_sol(token_mint)

async def buy_token_solana(token_mint_address):
    return await solana_service_instance.buy_token_solana(token_mint_address)

async def sell_token_solana(token_mint_address, amount_to_sell, wallet_token_account):
    return await solana_service_instance.sell_token_solana(token_mint_address, amount_to_sell, wallet_token_account)