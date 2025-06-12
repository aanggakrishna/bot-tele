# solana_service.py
import os
import json
import asyncio
import aiohttp
import time # Tambahkan ini jika belum ada, untuk time.time() dan asyncio.sleep()
from datetime import datetime, timedelta

# IMPOR TERBARU UNTUK SOLANA.PY DAN SOLDERS
from solana.rpc.api import Client # Ini masih dari solana.rpc.api
from solders.keypair import Keypair # Keypair sekarang dari solders
from solders.pubkey import Pubkey as PublicKey # Publickey sekarang dari solders, kita alias sebagai PublicKey
from solders.instruction import Instruction
from solders.message import Message as SoldersMessage
from solders.transaction import Transaction as SoldersTransaction

from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address, create_associated_token_account, close_account
from math import floor
from loguru import logger

# ... (sisa kode seperti sebelumnya)

# Konfigurasi dari environment variables (akan dimuat di main.py)
SOLANA_CLIENT: Client = None
WALLET: Keypair = None
WALLET_PUBKEY: PublicKey = None
AMOUNT_TO_BUY_SOL: float = 0.0 # Ubah dari USD ke SOL
SLIPPAGE_BPS: int = 0
JUPITER_API_URL: str = ""

def init_solana_config(rpc_url: str, private_key_path: str, amount_to_buy_sol: float, slippage_bps: int, jupiter_api_url: str, solana_private_key_base58: str = None):
    global SOLANA_CLIENT, WALLET, WALLET_PUBKEY, AMOUNT_TO_BUY_SOL, SLIPPAGE_BPS, JUPITER_API_URL

    SOLANA_CLIENT = Client(rpc_url)
    AMOUNT_TO_BUY_SOL = amount_to_buy_sol # Ambil nilai SOL
    SLIPPAGE_BPS = slippage_bps
    JUPITER_API_URL = jupiter_api_url

    if solana_private_key_base58:
        WALLET = Keypair.from_base58_string(solana_private_key_base58)
    else:
        WALLET = load_wallet_from_file(private_key_path)
    WALLET_PUBKEY = WALLET.pubkey() # <-- Ubah dari .public_key menjadi .pubkey()
    logger.info(f"Solana config initialized. Wallet: {WALLET_PUBKEY}, RPC: {rpc_url}")

def load_wallet_from_file(private_key_path: str) -> Keypair:
    try:
        with open(private_key_path, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                # Ubah cara membuat Keypair dari list byte.
                # solders.keypair.Keypair dapat dibuat langsung dari bytes secret key.
                secret_key_bytes = bytes(data)
                if len(secret_key_bytes) != 64: # Secret key harus 64 byte
                    raise ValueError(f"Invalid secret key length: {len(secret_key_bytes)} bytes. Expected 64 bytes for a full secret key.")
                return Keypair.from_bytes(secret_key_bytes) # <-- BARIS INI YANG BENAR UNTUK SOLDERS
            elif isinstance(data, str):
                return Keypair.from_base58_string(data)
            else:
                raise ValueError("Unsupported private key format in wallet.json")
    except FileNotFoundError:
        logger.error(f"Error: {private_key_path} not found. Ensure wallet.json is in the correct path or use SOLANA_PRIVATE_KEY_BASE58.")
        raise
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON from {private_key_path}. Check file format.")
        raise
    except Exception as e:
        logger.error(f"Error loading wallet from file: {e}")
        raise

# Hapus fungsi get_sol_price_usd() karena kita tidak lagi menggunakan USD

def get_latest_blockhash() -> str | None:
    try:
        response = SOLANA_CLIENT.get_latest_blockhash()
        return response.value.blockhash
    except Exception as e:
        logger.error(f"Error getting latest blockhash: {e}")
        return None

async def get_token_price_sol(token_mint_address: PublicKey, max_retries: int = 3) -> float | None:
    for attempt in range(max_retries):
        try:
            # Get quote from token_mint_address to SOL
            input_mint = str(token_mint_address)
            output_mint = "So11111111111111111111111111111111111111112" # SOL
            
            # Validate token info and check if it's a valid SPL token
            token_info_response = SOLANA_CLIENT.get_token_supply(token_mint_address)
            if not token_info_response.value:
                logger.error(f"Invalid token or cannot fetch token info for {token_mint_address}")
                return None
                
            token_info = token_info_response.value
            token_decimals = token_info.decimals
            
            # Basic token validation
            if token_decimals > 18 or token_decimals < 0:
                logger.warning(f"Suspicious token decimals ({token_decimals}) for {token_mint_address}")
                return None
            
            # Request quote for 1 unit of the token (1 * 10^decimals)
            amount_in = int(1 * (10**token_decimals))
            if amount_in == 0:
                logger.warning(f"Amount in for quote is zero for token {token_mint_address}. Cannot get price.")
                return None

        async with aiohttp.ClientSession() as session:
                try:
                    # Add timeout for API request
                    async with session.get(
                        f"{JUPITER_API_URL}/quote?inputMint={input_mint}&outputMint={output_mint}&amount={amount_in}&slippageBps=0",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()
                        
                        # Validate response data
                        if not all(key in data for key in ['outAmount', 'priceImpactPct']):
                            logger.error(f"Invalid Jupiter API response format for {token_mint_address}")
                            return None
                        
                        sol_amount_out = int(data['outAmount']) / (10**9) # SOL has 9 decimals
                        price_impact = float(data['priceImpactPct'])
                        
                        # Check liquidity (price impact)
                        if price_impact > 1.0:  # More than 1% price impact
                            logger.warning(f"High price impact ({price_impact}%) for {token_mint_address}")
                            return None
                            
                        if sol_amount_out > 0:
                            logger.info(f"Fetched token {token_mint_address} price: {sol_amount_out:.9f} SOL (Impact: {price_impact}%)")
                            return sol_amount_out
                        else:
                            logger.warning(f"Jupiter API returned 0 outAmount for {token_mint_address} price.")
                            return None
                            
                except asyncio.TimeoutError:
                    logger.error(f"Timeout fetching price for {token_mint_address}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # Wait before retry
                        continue
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"HTTP error fetching token price from Jupiter: {e}")
        if attempt < max_retries - 1:
            await asyncio.sleep(1)  # Wait before retry
            continue
    except Exception as e:
        logger.error(f"Error getting token price in SOL for {token_mint_address}: {e}")
        if attempt < max_retries - 1:
            await asyncio.sleep(1)  # Wait before retry
            continue
    return None

# Rate limiting untuk API calls
_last_api_call = 0
async def _rate_limit_wait():
    global _last_api_call
    now = time.time()
    if _last_api_call > 0:
        elapsed = now - _last_api_call
        if elapsed < 0.2:  # Maximum 5 requests per second
            await asyncio.sleep(0.2 - elapsed)
    _last_api_call = time.time()

async def buy_token_solana(token_mint_address_str: str, max_retries: int = 3) -> dict | None:
    try:
        token_mint_address = PublicKey(token_mint_address_str)
    except ValueError:
        logger.error(f"Invalid token address format: {token_mint_address_str}")
        return None

    logger.info(f"Attempting to buy token: {token_mint_address_str}")

    # Validasi saldo wallet
    try:
        balance = SOLANA_CLIENT.get_balance(WALLET_PUBKEY).value
        min_required_balance = (AMOUNT_TO_BUY_SOL + 0.01) * 10**9  # Tambah 0.01 SOL untuk fee
        if balance < min_required_balance:
            logger.error(f"Insufficient balance. Required: {min_required_balance/10**9} SOL, Got: {balance/10**9} SOL")
            return None
    except Exception as e:
        logger.error(f"Failed to check wallet balance: {e}")
        return None

    # Validasi token sebelum membeli
    token_price = await get_token_price_sol(token_mint_address)
    if token_price is None:
        logger.error("Failed to validate token price and liquidity")
        return None

    sol_amount_to_buy = AMOUNT_TO_BUY_SOL
    sol_amount_lamports = int(sol_amount_to_buy * 10**9)

    if sol_amount_lamports <= 0:
        logger.error("Calculated SOL amount is zero or negative. Aborting purchase.")
        return None

    logger.info(f"Buying with {sol_amount_to_buy:.6f} SOL ({sol_amount_lamports} lamports).")

    for attempt in range(max_retries):
        try:
            await _rate_limit_wait()  # Implement rate limiting
            
            # Get Jupiter Swap Quote
            async with aiohttp.ClientSession() as session:
                quote_url = f"{JUPITER_API_URL}/quote?inputMint=So11111111111111111111111111111111111111112&outputMint={token_mint_address_str}&amount={sol_amount_lamports}&slippageBps={SLIPPAGE_BPS}"
                logger.info(f"Getting Jupiter quote: {quote_url}")
                
                async with session.get(quote_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response.raise_for_status()
                    quote_data = await response.json()
                    
                    if not all(key in quote_data for key in ['outAmount', 'priceImpactPct']):
                        logger.error(f"Invalid Jupiter quote response format")
                        continue

                    # Validate price impact
                    price_impact = float(quote_data['priceImpactPct'])
                    if price_impact > 1.0:
                        logger.error(f"Price impact too high: {price_impact}%")
                        return None

                    logger.info(f"Jupiter quote received with price impact: {price_impact}%")

                await _rate_limit_wait()  # Rate limit between requests
                
                # Get Jupiter Swap Instructions
                swap_url = f"{JUPITER_API_URL}/swap"
                swap_payload = {
                    "quoteResponse": quote_data,
                    "userPublicKey": str(WALLET_PUBKEY),
                    "wrapUnwrapSol": True,
                    "autoSlippage": False,
                    "computeUnitPriceMicroLamports": "auto"
                }
                
                async with session.post(swap_url, json=swap_payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response.raise_for_status()
                    swap_data = await response.json()

                    if 'swapTransaction' not in swap_data:
                        logger.error(f"Jupiter swap instructions failed: {swap_data}")
                        continue

                    serialized_tx = swap_data['swapTransaction']

                    # Deserialize dan sign transaksi
                    try:
                        transaction = SoldersTransaction.from_bytes(bytes(serialized_tx))
                        transaction.sign([WALLET])

                        # Kirim transaksi dengan retry logic
                        logger.info("Sending buy transaction...")
                        resp = SOLANA_CLIENT.send_transaction(transaction)
                        tx_signature = resp.value
                        logger.info(f"Buy transaction sent: {tx_signature}")

                        # Tunggu konfirmasi dengan timeout yang lebih baik
                        start_time = time.time()
                        timeout = 60  # seconds
                        confirmation_count = 0
                        max_confirmation_attempts = 30

                        while time.time() - start_time < timeout and confirmation_count < max_confirmation_attempts:
                            try:
                                confirmation = SOLANA_CLIENT.confirm_transaction(tx_signature, commitment="confirmed")
                                
                                if confirmation.value.err:
                                    error_msg = confirmation.value.err
                                    logger.error(f"Buy transaction {tx_signature} failed: {error_msg}")
                                    return None
                                    
                                if confirmation.value.context.slot > 0:
                                    logger.info(f"Buy transaction {tx_signature} confirmed!")
                                    
                                    # Validasi transaksi setelah konfirmasi
                                    amount_bought_token = int(quote_data['outAmount']) / (10**quote_data['outputMintDecimals'])
                                    if amount_bought_token <= 0:
                                        logger.error("Transaction confirmed but received 0 tokens")
                                        return None

                                    # Hitung harga aktual dalam SOL
                                    token_price_sol_at_buy = sol_amount_to_buy / amount_bought_token
                                    
                                    # Dapatkan alamat ATA
                                    wallet_token_account = str(get_associated_token_address(WALLET_PUBKEY, token_mint_address))
                                    
                                    # Validasi balance setelah pembelian
                                    try:
                                        token_balance = SOLANA_CLIENT.get_token_account_balance(wallet_token_account).value.amount
                                        if int(token_balance) < int(quote_data['outAmount']):
                                            logger.error(f"Received fewer tokens than expected. Expected: {quote_data['outAmount']}, Got: {token_balance}")
                                            return None
                                    except Exception as e:
                                        logger.error(f"Failed to validate final token balance: {e}")
                                        return None

                                    break
                                    
                            except Exception as e:
                                logger.warning(f"Error checking transaction confirmation: {e}")
                                
                            confirmation_count += 1
                            await asyncio.sleep(2)
                            
                        else:
                            logger.error(f"Buy transaction {tx_signature} confirmation timeout or max attempts reached")
                            return None

        return {
                            "token_mint_address": token_mint_address_str,
                            "buy_price_sol": token_price_sol_at_buy,
                            "amount_bought_token": amount_bought_token,
                            "wallet_token_account": wallet_token_account,
                            "buy_tx_signature": tx_signature
                        }
                    except Exception as e:
                        logger.error(f"Error processing transaction: {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2)
                            continue
                        return None

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error during buy process: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
        except Exception as e:
            logger.error(f"Unexpected error during buy process: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue

    logger.error("All buy attempts failed")
    return None
            "buy_price_sol": token_price_sol_at_buy, # Hanya harga dalam SOL
            "amount_bought_token": amount_bought_token,
            "wallet_token_account": wallet_token_account,
            "buy_tx_signature": str(tx_signature)
        }

    except Exception as e:
        logger.error(f"Error during Solana buy transaction: {e}")
        return None

async def sell_token_solana(token_mint_address_str: str, amount_to_sell: float, wallet_token_account_str: str) -> dict | None:
    token_mint_address = PublicKey(token_mint_address_str)
    wallet_token_account = PublicKey(wallet_token_account_str)
    logger.info(f"Attempting to sell {amount_to_sell} of token: {token_mint_address_str} from {wallet_token_account_str}")

    # Get token decimals for calculation
    try:
        token_info = SOLANA_CLIENT.get_token_supply(token_mint_address).value
        token_decimals = token_info.decimals
    except Exception as e:
        logger.error(f"Failed to get token decimals for {token_mint_address_str}: {e}")
        return None

    amount_to_sell_raw = int(amount_to_sell * (10**token_decimals))
    if amount_to_sell_raw <= 0:
        logger.warning(f"Calculated amount to sell is zero or negative ({amount_to_sell}). Aborting sell.")
        return None

    # 1. Get Jupiter Swap Quote (Token to SOL)
    async with aiohttp.ClientSession() as session:
        quote_url = f"{JUPITER_API_URL}/quote?inputMint={token_mint_address_str}&outputMint=So11111111111111111111111111111111111111112&amount={amount_to_sell_raw}&slippageBps={SLIPPAGE_BPS}"
        logger.info(f"Getting Jupiter sell quote: {quote_url}")
        async with session.get(quote_url) as response:
            response.raise_for_status()
            quote_data = await response.json()
            if 'outAmount' not in quote_data:
                logger.error(f"Jupiter sell quote failed: {quote_data}")
                return None
            logger.info(f"Jupiter sell quote: {quote_data}")

        # 2. Get Jupiter Swap Instructions
        swap_url = f"{JUPITER_API_URL}/swap"
        swap_payload = {
            "quoteResponse": quote_data,
            "userPublicKey": str(WALLET_PUBKEY),
            "wrapUnwrapSol": True,
            "autoSlippage": False,
            "computeUnitPriceMicroLamports": "auto"
        }
        logger.info(f"Getting Jupiter sell instructions. Payload: {swap_payload}")
        async with session.post(swap_url, json=swap_payload) as response:
            response.raise_for_status()
            swap_data = await response.json()
            logger.info(f"Jupiter sell data: {swap_data}")

            if 'swapTransaction' not in swap_data:
                logger.error(f"Jupiter sell instructions failed: {swap_data}")
                return None

            serialized_tx = swap_data['swapTransaction']

    # 3. Deserialize and sign the transaction
    try:
        transaction = SoldersTransaction.from_bytes(bytes(serialized_tx))
        transaction.sign([WALLET])

        # 4. Send the transaction
        logger.info("Sending sell transaction...")
        resp = SOLANA_CLIENT.send_transaction(transaction)
        tx_signature = resp.value
        logger.info(f"Sell transaction sent: {tx_signature}")

        # 5. Wait for confirmation
        start_time = time.time()
        timeout = 60 # seconds
        while time.time() - start_time < timeout:
            confirmation = SOLANA_CLIENT.confirm_transaction(tx_signature, commitment="confirmed")
            if confirmation.value.err:
                logger.error(f"Sell transaction {tx_signature} failed: {confirmation.value.err}")
                return None
            if confirmation.value.context.slot > 0: # Confirmed
                logger.info(f"Sell transaction {tx_signature} confirmed!")
                break
            await asyncio.sleep(2) # Poll every 2 seconds
        else:
            logger.warning(f"Sell transaction {tx_signature} not confirmed within {timeout} seconds.")
            return None

        # 6. Get transaction details to extract amount sold
        amount_received_sol = int(quote_data['outAmount']) / (10**9) # SOL has 9 decimals
        
        # Calculate actual token price in SOL at sell
        sell_price_sol = amount_received_sol / amount_to_sell if amount_to_sell > 0 else 0

        # Close ATA if 0 balance after sell (optional, saves rent)
        try:
            account_info = SOLANA_CLIENT.get_token_account_balance(wallet_token_account).value
            if int(account_info.amount) == 0:
                logger.info(f"Token account {wallet_token_account_str} balance is 0. Attempting to close ATA.")
                close_ix = close_account(
                    owner=WALLET_PUBKEY,
                    account=wallet_token_account,
                    destination=WALLET_PUBKEY, # Refund rent to main wallet
                    delegate=WALLET_PUBKEY, # Can be wallet itself
                    signer_or_multi_signer=[]
                )
                recent_blockhash = get_latest_blockhash()
                if recent_blockhash:
                    close_tx = SoldersTransaction([WALLET], SoldersMessage.new_with_blockhash([close_ix], WALLET_PUBKEY, recent_blockhash), recent_blockhash)
                    close_tx.sign([WALLET])
                    close_resp = SOLANA_CLIENT.send_transaction(close_tx)
                    logger.info(f"Close ATA transaction sent: {close_resp.value}")
                    await asyncio.sleep(5) # Wait for a bit
                    close_conf = SOLANA_CLIENT.confirm_transaction(close_resp.value, commitment="confirmed")
                    if not close_conf.value.err:
                        logger.info(f"ATA {wallet_token_account_str} closed successfully.")
                    else:
                        logger.warning(f"Failed to close ATA {wallet_token_account_str}: {close_conf.value.err}")
                else:
                    logger.warning("Could not get blockhash to close ATA.")
        except Exception as e:
            logger.warning(f"Error checking/closing ATA: {e}")

        return {
            "sell_price_sol": sell_price_sol, # Hanya harga dalam SOL
            "sell_tx_signature": str(tx_signature)
        }

    except Exception as e:
        logger.error(f"Error during Solana sell transaction: {e}")
        return None

async def get_token_balance(token_account_address: PublicKey) -> float | None:
    try:
        response = SOLANA_CLIENT.get_token_account_balance(token_account_address)
        if response.value:
            balance_raw = int(response.value.amount)
            decimals = response.value.decimals
            balance = balance_raw / (10**decimals)
            return balance
        return 0.0
    except Exception as e:
        logger.error(f"Error getting token balance for {token_account_address}: {e}")
        return None