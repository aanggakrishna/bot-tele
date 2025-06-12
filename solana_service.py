# solana_service.py - Perbaikan untuk validasi token address

import os
import asyncio
import json
import base58
import base64
import aiohttp
from solders.pubkey import Pubkey as PublicKey
from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.transaction import Transaction
from loguru import logger
from typing import Optional, Dict, Any

# Global variables
rpc_client = None
wallet_keypair = None
amount_to_buy_sol = None
slippage_bps = None
jupiter_api_url = None

def init_solana_config(rpc_url: str, private_key_path: str, amount_to_buy_sol: float, 
                      slippage_bps: int, jupiter_api_url: str, solana_private_key_base58: str = None):
    """Initialize Solana configuration"""
    global rpc_client, wallet_keypair, amount_to_buy_sol as global_amount, slippage_bps as global_slippage, jupiter_api_url as global_jupiter_api
    
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
    global_amount = amount_to_buy_sol
    global_slippage = slippage_bps
    global_jupiter_api = jupiter_api_url
    
    logger.info(f"Solana service initialized - Amount: {global_amount} SOL, Slippage: {global_slippage} BPS")

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

async def buy_token_solana(token_address: str) -> Optional[Dict[str, Any]]:
    """
    Buy token using Jupiter swap
    """
    global rpc_client, wallet_keypair, amount_to_buy_sol, slippage_bps, jupiter_api_url
    
    if not all([rpc_client, wallet_keypair, amount_to_buy_sol, slippage_bps, jupiter_api_url]):
        logger.error("Solana service not properly initialized")
        return None
    
    try:
        logger.info(f"Starting buy process for token: {token_address}")
        
        # Validate token address
        token_pubkey = validate_token_address(token_address)
        if not token_pubkey:
            logger.error(f"Invalid token address format: {token_address}")
            return None
        
        # SOL mint address (wrapped SOL)
        sol_mint = PublicKey.from_string("So11111111111111111111111111111111111111112")
        
        # Convert SOL amount to lamports (1 SOL = 1,000,000,000 lamports)
        amount_lamports = int(amount_to_buy_sol * 1_000_000_000)
        
        logger.info(f"Attempting to buy {amount_to_buy_sol} SOL worth of {token_address}")
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
                logger.info(f"Received quote: {json.dumps(quote_data, indent=2)}")
                
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
                logger.info("Sending swap transaction...")
                tx_response = await rpc_client.send_transaction(
                    transaction,
                    commitment=Confirmed,
                    skip_preflight=False,
                    max_retries=3
                )
                
                if tx_response.value:
                    tx_signature = str(tx_response.value)
                    logger.info(f"✅ Buy transaction successful: {tx_signature}")
                    
                    # Calculate actual token amount and price
                    actual_token_amount = expected_token_amount / (10 ** 6)  # Assuming 6 decimals, adjust as needed
                    buy_price_sol = amount_to_buy_sol / actual_token_amount if actual_token_amount > 0 else 0
                    
                    # For now, we'll use a placeholder for wallet_token_account
                    # In a real implementation, you'd need to derive the associated token account
                    wallet_token_account = "placeholder_token_account"
                    
                    return {
                        'token_mint_address': token_address,
                        'buy_price_sol': buy_price_sol,
                        'amount_bought_token': actual_token_amount,
                        'wallet_token_account': wallet_token_account,
                        'buy_tx_signature': tx_signature
                    }
                else:
                    logger.error("Transaction failed - no signature returned")
                    return None
    
    except Exception as e:
        logger.error(f"Error in buy_token_solana: {e}", exc_info=True)
        return None

async def sell_token_solana(token_address: str, amount_to_sell: float, wallet_token_account: str) -> Optional[Dict[str, Any]]:
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
        
        # SOL mint address
        sol_mint = PublicKey.from_string("So11111111111111111111111111111111111111112")
        
        # Convert token amount (assuming 6 decimals)
        amount_token_raw = int(amount_to_sell * (10 ** 6))
        
        logger.info(f"Attempting to sell {amount_to_sell} tokens of {token_address}")
        
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
                    return None
                
                quote_data = await response.json()
                expected_sol_amount = int(quote_data['outAmount'])
                logger.info(f"Expected SOL amount: {expected_sol_amount} lamports")
            
            # Get swap transaction
            swap_url = f"{jupiter_api_url}/swap"
            swap_data = {
                'quoteResponse': quote_data,
                'userPublicKey': str(wallet_keypair.pubkey()),
                'wrapAndUnwrapSol': True
            }
            
            async with session.post(swap_url, json=swap_data) as response:
                if response.status != 200:
                    logger.error(f"Jupiter swap API error: {response.status}")
                    return None
                
                swap_response = await response.json()
                
                # Process similar to buy_token_solana
                transaction_bytes = base64.b64decode(swap_response['swapTransaction'])
                transaction = Transaction.deserialize(transaction_bytes)
                transaction.sign(wallet_keypair)
                
                # Send transaction
                logger.info("Sending sell transaction...")
                tx_response = await rpc_client.send_transaction(
                    transaction,
                    commitment=Confirmed,
                    skip_preflight=False
                )
                
                if tx_response.value:
                    tx_signature = str(tx_response.value)
                    logger.info(f"✅ Sell transaction successful: {tx_signature}")
                    
                    # Calculate sell price in SOL
                    sell_price_sol = (expected_sol_amount / 1_000_000_000) / amount_to_sell if amount_to_sell > 0 else 0
                    
                    return {
                        'sell_price_sol': sell_price_sol,
                        'sell_tx_signature': tx_signature
                    }
                else:
                    logger.error("Sell transaction failed")
                    return None
    
    except Exception as e:
        logger.error(f"Error in sell_token_solana: {e}", exc_info=True)
        return None