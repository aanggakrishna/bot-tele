import asyncio
import json
import os
from typing import Optional, Dict, Any
import aiohttp
import base58
from solana.rpc.async_api import AsyncClient
from solana.keypair import Keypair
from solana.transaction import Transaction
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
            
            if private_key_base58 and private_key_base58 != 'your_actual_base58_private_key_here':
                # Use base58 private key
                try:
                    private_key_bytes = base58.b58decode(private_key_base58)
                    self.keypair = Keypair.from_secret_key(private_key_bytes)
                    logger.info(f"🔑 Wallet loaded from base58 key: {self.keypair.public_key}")
                except Exception as e:
                    logger.error(f"❌ Error loading base58 private key: {e}")
                    raise
            elif wallet_path and os.path.exists(wallet_path):
                # Use wallet file
                try:
                    with open(wallet_path, 'r') as f:
                        wallet_data = json.load(f)
                    private_key_bytes = bytes(wallet_data)
                    self.keypair = Keypair.from_secret_key(private_key_bytes)
                    logger.info(f"🔑 Wallet loaded from file: {self.keypair.public_key}")
                except Exception as e:
                    logger.error(f"❌ Error loading wallet file: {e}")
                    raise
            else:
                raise ValueError("No valid private key found. Set SOLANA_PRIVATE_KEY_BASE58 or PRIVATE_KEY_PATH")
                
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
                
                async with session.get(url, params=params) as response:
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

    async def buy_token_solana(self, token_mint_address: str) -> Optional[Dict[str, Any]]:
        """Buy token using Jupiter swap"""
        try:
            logger.info(f"🔄 Initiating buy for token: {token_mint_address}")
            
            # Validate inputs
            if not self.keypair:
                raise ValueError("Wallet not initialized")
            
            # Get quote from Jupiter
            sol_amount = float(os.getenv('AMOUNT_TO_BUY_SOL', '0.01'))
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
            price_per_token = lamports / output_amount if output_amount > 0 else 0
            
            result = {
                'token_mint_address': token_mint_address,
                'buy_price_sol': price_per_token,
                'amount_bought_token': output_amount / 1_000_000,  # Assuming 6 decimals
                'wallet_token_account': str(self.keypair.public_key),  # Simplified
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
            
            result = {
                'token_mint_address': token_mint_address,
                'sell_price_sol': output_sol / amount_to_sell if amount_to_sell > 0 else 0,
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
                
                async with session.get(url, params=params) as response:
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
                    'userPublicKey': str(self.keypair.public_key),
                    'wrapAndUnwrapSol': True
                }
                
                async with session.post(url, json=data) as response:
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
            # Decode transaction
            transaction_bytes = base64.b64decode(transaction_base64)
            transaction = Transaction.deserialize(transaction_bytes)
            
            # Sign transaction
            transaction.sign(self.keypair)
            
            # Send transaction
            response = await self.rpc_client.send_transaction(transaction)
            
            if response.value:
                tx_signature = str(response.value)
                logger.info(f"✅ Transaction sent: {tx_signature}")
                
                # Wait for confirmation
                await asyncio.sleep(2)
                confirmation = await self.rpc_client.confirm_transaction(response.value)
                
                if confirmation.value[0].confirmation_status:
                    logger.info(f"✅ Transaction confirmed: {tx_signature}")
                    return tx_signature
                else:
                    logger.error(f"❌ Transaction not confirmed: {tx_signature}")
                    return None
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