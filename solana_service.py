# solana_service.py - Full version with .env support

import os
import asyncio
import json
import base58
import base64
import aiohttp
from dotenv import load_dotenv
from solders.pubkey import Pubkey as PublicKey
from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.transaction import Transaction
from loguru import logger
from typing import Optional, Dict, Any

# Load environment variables from .env file
load_dotenv()

# Global variables
rpc_client = None
wallet_keypair = None
amount_to_buy_sol = None
slippage_bps = None
jupiter_api_url = None

def init_solana_config(rpc_url: str = None, private_key_path: str = None, 
                      amount_to_buy_sol_param: float = None, slippage_bps_param: int = None, 
                      jupiter_api_url_param: str = None, solana_private_key_base58: str = None):
    """
    Initialize Solana configuration
    If parameters are None, will try to load from environment variables
    """
    global rpc_client, wallet_keypair, amount_to_buy_sol, slippage_bps, jupiter_api_url
    
    # Load from environment variables if not provided
    rpc_url = rpc_url or os.getenv('SOLANA_RPC_URL')
    private_key_path = private_key_path or os.getenv('SOLANA_PRIVATE_KEY_PATH')
    amount_to_buy_sol_param = amount_to_buy_sol_param or float(os.getenv('AMOUNT_TO_BUY_SOL', '0.1'))
    slippage_bps_param = slippage_bps_param or int(os.getenv('SLIPPAGE_BPS', '50'))
    jupiter_api_url_param = jupiter_api_url_param or os.getenv('JUPITER_API_URL', 'https://quote-api.jup.ag/v6')
    solana_private_key_base58 = solana_private_key_base58 or os.getenv('SOLANA_PRIVATE_KEY_BASE58')
    
    # Validate required parameters
    if not rpc_url:
        raise ValueError("SOLANA_RPC_URL is required (either as parameter or environment variable)")
    
    if not solana_private_key_base58 and not private_key_path:
        raise ValueError("Either SOLANA_PRIVATE_KEY_BASE58 or SOLANA_PRIVATE_KEY_PATH is required")
    
    # Initialize RPC client
    rpc_client = AsyncClient(rpc_url)
    logger.info(f"Initialized Solana RPC client with URL: {rpc_url}")
    
    # Initialize wallet keypair
    if solana_private_key_base58:
        try:
            private_key_bytes = base58.b58decode(solana_private_key_base58)
            wallet_keypair = Keypair.from_bytes(private_key_bytes)
            logger.info(f"Loaded wallet keypair from base58: {wallet_keypair.pubkey()}")
        except Exception as e:
            logger.error(f"Failed to load keypair from base58: {e}")
            raise
    elif private_key_path and os.path.exists(private_key_path):
        try:
            with open(private_key_path, 'r') as f:
                private_key_data = json.load(f)
            
            if isinstance(private_key_data, list):
                private_key_bytes = bytes(private_key_data)
            else:
                private_key_bytes = base58.b58decode(private_key_data)
            
            wallet_keypair = Keypair.from_bytes(private_key_bytes)
            logger.info(f"Loaded wallet keypair from file: {wallet_keypair.pubkey()}")
        except Exception as e:
            logger.error(f"Failed to load keypair from file: {e}")
            raise
    else:
        logger.error("No valid private key source provided")
        raise ValueError("No valid private key source provided")
    
    # Set global variables
    amount_to_buy_sol = amount_to_buy_sol_param
    slippage_bps = slippage_bps_param
    jupiter_api_url = jupiter_api_url_param
    
    logger.info(f"Solana service initialized:")
    logger.info(f"  - Wallet: {wallet_keypair.pubkey()}")
    logger.info(f"  - Amount: {amount_to_buy_sol} SOL")
    logger.info(f"  - Slippage: {slippage_bps} BPS")
    logger.info(f"  - Jupiter API: {jupiter_api_url}")

def init_solana_config_from_env():
    """
    Initialize Solana configuration using only environment variables
    Convenience function for easier setup
    """
    return init_solana_config()

def validate_token_address(token_address: str) -> Optional[PublicKey]:
    """
    Validate and convert token address string to PublicKey
    Returns PublicKey if valid, None if invalid
    """
    if not token_address or not isinstance(token_address, str):
        logger.error(f"Invalid token address input: {token_address}")
        return None
    
    # Remove any whitespace
    token_address = token_address.strip()
    
    # Check length
    if not (32 <= len(token_address) <= 44):
        logger.error(f"Invalid token address length: {len(token_address)} (expected 32-44)")
        return None
    
    # Check base58 characters
    valid_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    if not all(c in valid_chars for c in token_address):
        logger.error(f"Invalid base58 characters in token address: {token_address}")
        return None
    
    try:
        # Try to create PublicKey
        pubkey = PublicKey.from_string(token_address)
        logger.info(f"✅ Valid token address: {token_address}")
        return pubkey
    except Exception as e:
        logger.error(f"Failed to create PublicKey from address '{token_address}': {e}")
        
        # Try base58 decode as fallback
        try:
            decoded = base58.b58decode(token_address)
            if len(decoded) == 32:
                pubkey = PublicKey(decoded)
                logger.info(f"✅ Valid token address (base58 fallback): {token_address}")
                return pubkey
            else:
                logger.error(f"Decoded address has wrong length: {len(decoded)} bytes (expected 32)")
        except Exception as e2:
            logger.error(f"Base58 decode also failed for '{token_address}': {e2}")
        
        return None

async def get_wallet_balance() -> Optional[float]:
    """
    Get wallet SOL balance
    """
    global rpc_client, wallet_keypair
    
    if not rpc_client or not wallet_keypair:
        logger.error("Solana service not initialized")
        return None
    
    try:
        response = await rpc_client.get_balance(wallet_keypair.pubkey())
        if response.value is not None:
            balance_sol = response.value / 1_000_000_000  # Convert lamports to SOL
            logger.info(f"Wallet balance: {balance_sol:.6f} SOL")
            return balance_sol
        else:
            logger.error("Failed to get wallet balance")
            return None
    except Exception as e:
        logger.error(f"Error getting wallet balance: {e}")
        return None

async def get_token_price_sol(token_mint: PublicKey) -> Optional[float]:
    """
    Get token price in SOL using Jupiter API
    """
    try:
        if not jupiter_api_url:
            logger.error("Jupiter API URL not configured")
            return None
        
        # Use Jupiter price API
        url = f"{jupiter_api_url}/price"
        params = {
            'ids': str(token_mint),
            'vsToken': 'So11111111111111111111111111111111111111112'  # SOL mint address
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if 'data' in data and str(token_mint) in data['data']:
                        price_data = data['data'][str(token_mint)]
                        price_sol = float(price_data.get('price', 0))
                        logger.info(f"Token {token_mint} price: {price_sol:.8f} SOL")
                        return price_sol
                    else:
                        logger.warning(f"No price data found for token {token_mint}")
                        return None
                else:
                    logger.error(f"Jupiter API error: {response.status}")
                    return None
    
    except Exception as e:
        logger.error(f"Error fetching token price: {e}")
        return None

async def get_token_info(token_mint: PublicKey) -> Optional[Dict[str, Any]]:
    """
    Get token information from Jupiter API
    """
    try:
        if not jupiter_api_url:
            logger.error("Jupiter API URL not configured")
            return None
        
        url = f"{jupiter_api_url}/tokens/{str(token_mint)}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    token_info = await response.json()
                    logger.info(f"Token info for {token_mint}: {token_info.get('name', 'Unknown')}")
                    return token_info
                else:
                    logger.warning(f"Could not fetch token info for {token_mint}")
                    return None
    
    except Exception as e:
        logger.error(f"Error fetching token info: {e}")
        return None

async def buy_token_solana(token_address: str, custom_amount: float = None) -> Optional[Dict[str, Any]]:
    """
    Buy token using Jupiter swap
    """
    global rpc_client, wallet_keypair, amount_to_buy_sol, slippage_bps, jupiter_api_url
    
    if not all([rpc_client, wallet_keypair, amount_to_buy_sol, slippage_bps, jupiter_api_url]):
        logger.error("Solana service not properly initialized")
        return None
    
    # Use custom amount if provided, otherwise use global amount
    buy_amount = custom_amount or amount_to_buy_sol
    
    try:
        logger.info(f"Starting buy process for token: {token_address}")
        
        # Check wallet balance first
        wallet_balance = await get_wallet_balance()
        if wallet_balance is None or wallet_balance < buy_amount:
            logger.error(f"Insufficient balance. Required: {buy_amount} SOL, Available: {wallet_balance} SOL")
            return None
        
        # Validate token address
        token_pubkey = validate_token_address(token_address)
        if not token_pubkey:
            logger.error(f"Invalid token address format: {token_address}")
            return None
        
        # Get token info
        token_info = await get_token_info(token_pubkey)
        token_name = token_info.get('name', 'Unknown') if token_info else 'Unknown'
        token_symbol = token_info.get('symbol', 'UNK') if token_info else 'UNK'
        
        # SOL mint address (wrapped SOL)
        sol_mint = PublicKey.from_string("So11111111111111111111111111111111111111112")
        
        # Convert SOL amount to lamports (1 SOL = 1,000,000,000 lamports)
        amount_lamports = int(buy_amount * 1_000_000_000)
        
        logger.info(f"Attempting to buy {buy_amount} SOL worth of {token_name} ({token_symbol})")
        logger.info(f"Amount in lamports: {amount_lamports}")
        
        # Get quote from Jupiter
        quote_url = f"{jupiter_api_url}/quote"
        quote_params = {
            'inputMint': str(sol_mint),
            'outputMint': str(token_pubkey),
            'amount': amount_lamports,
            'slippageBps': slippage_bps
        }
        
        async with aiohttp.ClientSession() as session:
            # Get quote
            async with session.get(quote_url, params=quote_params) as response:
                if response.status != 200:
                    logger.error(f"Jupiter quote API error: {response.status}")
                    error_text = await response.text()
                    logger.error(f"Error response: {error_text}")
                    return None
                
                quote_data = await response.json()
                logger.info(f"Received quote for {token_symbol}")
                
                if 'outAmount' not in quote_data:
                    logger.error("No outAmount in quote response")
                    return None
                
                expected_token_amount = int(quote_data['outAmount'])
                logger.info(f"Expected token amount: {expected_token_amount}")
            
            # Get swap transaction
            swap_url = f"{jupiter_api_url}/swap"
            swap_data = {
                'quoteResponse': quote_data,
                'userPublicKey': str(wallet_keypair.pubkey()),
                'wrapAndUnwrapSol': True,
                'computeUnitPriceMicroLamports': 'auto'
            }
            
            async with session.post(swap_url, json=swap_data) as response:
                if response.status != 200:
                    logger.error(f"Jupiter swap API error: {response.status}")
                    error_text = await response.text()
                    logger.error(f"Error response: {error_text}")
                    return None
                
                swap_response = await response.json()
                
                if 'swapTransaction' not in swap_response:
                    logger.error("No swapTransaction in response")
                    return None
                
                # Decode and sign transaction
                transaction_bytes = base64.b64decode(swap_response['swapTransaction'])
                transaction = Transaction.deserialize(transaction_bytes)
                
                # Sign transaction
                transaction.sign(wallet_keypair)
                
                # Send transaction
                logger.info(f"Sending swap transaction for {token_symbol}...")
                tx_response = await rpc_client.send_transaction(
                    transaction,
                    commitment=Confirmed,
                    skip_preflight=False,
                    max_retries=3
                )
                
                if tx_response.value:
                    tx_signature = str(tx_response.value)
                    logger.info(f"✅ Buy transaction successful: {tx_signature}")
                    
                    # Calculate token decimals (default to 6 if not available)
                    token_decimals = token_info.get('decimals', 6) if token_info else 6
                    actual_token_amount = expected_token_amount / (10 ** token_decimals)
                    buy_price_sol = buy_amount / actual_token_amount if actual_token_amount > 0 else 0
                    
                    # For now, we'll use a placeholder for wallet_token_account
                    # In a real implementation, you'd need to derive the associated token account
                    wallet_token_account = f"ATA_{str(wallet_keypair.pubkey())[:8]}_{str(token_pubkey)[:8]}"
                    
                    return {
                        'token_mint_address': token_address,
                        'token_name': token_name,
                        'token_symbol': token_symbol,
                        'buy_price_sol': buy_price_sol,
                        'amount_bought_token': actual_token_amount,
                        'amount_spent_sol': buy_amount,
                        'wallet_token_account': wallet_token_account,
                        'buy_tx_signature': tx_signature,
                        'explorer_url': f"https://solscan.io/tx/{tx_signature}"
                    }
                else:
                    logger.error("Transaction failed - no signature returned")
                    return None
    
    except Exception as e:
        logger.error(f"Error in buy_token_solana: {e}", exc_info=True)
        return None

async def sell_token_solana(token_address: str, amount_to_sell: float, 
                           wallet_token_account: str = None) -> Optional[Dict[str, Any]]:
    """
    Sell token using Jupiter swap
    """
    global rpc_client, wallet_keypair, slippage_bps, jupiter_api_url
    
    if not all([rpc_client, wallet_keypair, slippage_bps, jupiter_api_url]):
        logger.error("Solana service not properly initialized")
        return None
    
    try:
        logger.info(f"Starting sell process for token: {token_address}")
        
        # Validate token address
        token_pubkey = validate_token_address(token_address)
        if not token_pubkey:
            logger.error(f"Invalid token address format: {token_address}")
            return None
        
        # Get token info
        token_info = await get_token_info(token_pubkey)
        token_name = token_info.get('name', 'Unknown') if token_info else 'Unknown'
        token_symbol = token_info.get('symbol', 'UNK') if token_info else 'UNK'
        token_decimals = token_info.get('decimals', 6) if token_info else 6
        
        # SOL mint address
        sol_mint = PublicKey.from_string("So11111111111111111111111111111111111111112")
        
        # Convert token amount
        amount_token_raw = int(amount_to_sell * (10 ** token_decimals))
        
        logger.info(f"Attempting to sell {amount_to_sell} {token_symbol}")
        
        # Get quote from Jupiter
        quote_url = f"{jupiter_api_url}/quote"
        quote_params = {
            'inputMint': str(token_pubkey),
            'outputMint': str(sol_mint),
            'amount': amount_token_raw,
            'slippageBps': slippage_bps
        }
        
        async with aiohttp.ClientSession() as session:
            # Get quote
            async with session.get(quote_url, params=quote_params) as response:
                if response.status != 200:
                    logger.error(f"Jupiter quote API error: {response.status}")
                    error_text = await response.text()
                    logger.error(f"Error response: {error_text}")
                    return None
                
                quote_data = await response.json()
                expected_sol_amount = int(quote_data['outAmount'])
                expected_sol_amount_float = expected_sol_amount / 1_000_000_000
                logger.info(f"Expected SOL amount: {expected_sol_amount_float:.6f} SOL")
            
            # Get swap transaction
            swap_url = f"{jupiter_api_url}/swap"
            swap_data = {
                'quoteResponse': quote_data,
                'userPublicKey': str(wallet_keypair.pubkey()),
                'wrapAndUnwrapSol': True,
                'computeUnitPriceMicroLamports': 'auto'
            }
            
            async with session.post(swap_url, json=swap_data) as response:
                if response.status != 200:
                    logger.error(f"Jupiter swap API error: {response.status}")
                    error_text = await response.text()
                    logger.error(f"Error response: {error_text}")
                    return None
                
                swap_response = await response.json()
                
                if 'swapTransaction' not in swap_response:
                    logger.error("No swapTransaction in response")
                    return None
                
                # Process similar to buy_token_solana
                transaction_bytes = base64.b64decode(swap_response['swapTransaction'])
                transaction = Transaction.deserialize(transaction_bytes)
                transaction.sign(wallet_keypair)
                
                # Send transaction
                logger.info(f"Sending sell transaction for {token_symbol}...")
                tx_response = await rpc_client.send_transaction(
                    transaction,
                    commitment=Confirmed,
                    skip_preflight=False,
                    max_retries=3
                )
                
                if tx_response.value:
                    tx_signature = str(tx_response.value)
                    logger.info(f"✅ Sell transaction successful: {tx_signature}")
                    
                    # Calculate sell price in SOL
                    sell_price_sol = expected_sol_amount_float / amount_to_sell if amount_to_sell > 0 else 0
                    
                    return {
                        'token_mint_address': token_address,
                        'token_name': token_name,
                        'token_symbol': token_symbol,
                        'sell_price_sol': sell_price_sol,
                        'amount_sold_token': amount_to_sell,
                        'amount_received_sol': expected_sol_amount_float,
                        'sell_tx_signature': tx_signature,
                        'explorer_url': f"https://solscan.io/tx/{tx_signature}"
                    }
                else:
                    logger.error("Sell transaction failed")
                    return None
    
    except Exception as e:
        logger.error(f"Error in sell_token_solana: {e}", exc_info=True)
        return None

# Utility functions
def get_config_info() -> Dict[str, Any]:
    """
    Get current configuration information
    """
    global wallet_keypair, amount_to_buy_sol, slippage_bps, jupiter_api_url
    
    return {
        'wallet_address': str(wallet_keypair.pubkey()) if wallet_keypair else None,
        'amount_to_buy_sol': amount_to_buy_sol,
        'slippage_bps': slippage_bps,
        'jupiter_api_url': jupiter_api_url,
        'is_initialized': all([rpc_client, wallet_keypair, amount_to_buy_sol, slippage_bps, jupiter_api_url])
    }

async def test_connection() -> bool:
    """
    Test RPC connection and wallet
    """
    global rpc_client, wallet_keypair
    
    if not rpc_client or not wallet_keypair:
        logger.error("Service not initialized")
        return False
    
    try:
        # Test RPC connection
        response = await rpc_client.get_health()
        logger.info("✅ RPC connection successful")
        
        # Test wallet balance
        balance = await get_wallet_balance()
        if balance is not None:
            logger.info(f"✅ Wallet accessible, balance: {balance:.6f} SOL")
            return True
        else:
            logger.error("❌ Could not access wallet")
            return False
            
    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}")
        return False

# Example usage
async def main():
    """
    Example usage of the Solana service
    """
    try:
        # Initialize from environment variables
        init_solana_config_from_env()
        
        # Test connection
        if not await test_connection():
            logger.error("Connection test failed")
            return
        
        # Show configuration
        config = get_config_info()
        logger.info(f"Configuration: {config}")
        
        # Example: Buy a token (replace with actual token address)
        # token_address = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC example
        # result = await buy_token_solana(token_address)
        # if result:
        #     logger.info(f"Buy successful: {result}")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())