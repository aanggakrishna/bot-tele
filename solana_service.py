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
    WALLET_PUBKEY = WALLET.public_key
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

async def get_token_price_sol(token_mint_address: PublicKey) -> float | None:
    try:
        # Get quote from token_mint_address to SOL
        input_mint = str(token_mint_address)
        output_mint = "So11111111111111111111111111111111111111112" # SOL
        
        # We need to know the token's decimals to form the correct 'amount' for the quote.
        # Fetching token info to get decimals
        token_info = SOLANA_CLIENT.get_token_supply(token_mint_address).value
        token_decimals = token_info.decimals
        
        # Request quote for 1 unit of the token (1 * 10^decimals)
        amount_in = int(1 * (10**token_decimals))
        if amount_in == 0: # Avoid division by zero if token has 0 decimals and amount is too small
            logger.warning(f"Amount in for quote is zero for token {token_mint_address}. Cannot get price.")
            return None

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{JUPITER_API_URL}/quote?inputMint={input_mint}&outputMint={output_mint}&amount={amount_in}&slippageBps=0") as response:
                response.raise_for_status()
                data = await response.json()
                sol_amount_out = int(data['outAmount']) / (10**9) # SOL has 9 decimals
                if sol_amount_out > 0:
                    logger.info(f"Fetched token {token_mint_address} price: {sol_amount_out:.9f} SOL")
                    return sol_amount_out
                else:
                    logger.warning(f"Jupiter API returned 0 outAmount for {token_mint_address} price.")
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"HTTP error fetching token price from Jupiter: {e}")
    except Exception as e:
        logger.error(f"Error getting token price in SOL for {token_mint_address}: {e}")
    return None

async def buy_token_solana(token_mint_address_str: str) -> dict | None:
    token_mint_address = PublicKey(token_mint_address_str)
    logger.info(f"Attempting to buy token: {token_mint_address_str}")

    # 1. Gunakan AMOUNT_TO_BUY_SOL langsung
    sol_amount_to_buy = AMOUNT_TO_BUY_SOL
    sol_amount_lamports = int(sol_amount_to_buy * 10**9) # SOL has 9 decimal places

    if sol_amount_lamports <= 0:
        logger.error("Calculated SOL amount is zero or negative. Aborting purchase.")
        return None

    logger.info(f"Buying with {sol_amount_to_buy:.6f} SOL ({sol_amount_lamports} lamports).")

    # 2. Get Jupiter Swap Quote (SOL to Token)
    async with aiohttp.ClientSession() as session:
        quote_url = f"{JUPITER_API_URL}/quote?inputMint=So11111111111111111111111111111111111111112&outputMint={token_mint_address_str}&amount={sol_amount_lamports}&slippageBps={SLIPPAGE_BPS}"
        logger.info(f"Getting Jupiter quote: {quote_url}")
        async with session.get(quote_url) as response:
            response.raise_for_status()
            quote_data = await response.json()
            if 'outAmount' not in quote_data:
                logger.error(f"Jupiter quote failed: {quote_data}")
                return None
            logger.info(f"Jupiter quote: {quote_data}")

        # 3. Get Jupiter Swap Instructions
        swap_url = f"{JUPITER_API_URL}/swap"
        swap_payload = {
            "quoteResponse": quote_data,
            "userPublicKey": str(WALLET_PUBKEY),
            "wrapUnwrapSol": True, # Automatically wrap SOL to wSOL if needed
            "autoSlippage": False, # Use the defined slippage
            "computeUnitPriceMicroLamports": "auto" # Or specific value for priority fees
        }
        logger.info(f"Getting Jupiter swap instructions. Payload: {swap_payload}")
        async with session.post(swap_url, json=swap_payload) as response:
            response.raise_for_status()
            swap_data = await response.json()
            logger.info(f"Jupiter swap data: {swap_data}")

            if 'swapTransaction' not in swap_data:
                logger.error(f"Jupiter swap instructions failed: {swap_data}")
                return None

            serialized_tx = swap_data['swapTransaction']

    # 4. Deserialize and sign the transaction
    try:
        transaction = SoldersTransaction.from_bytes(bytes(serialized_tx))
        transaction.sign([WALLET]) # Sign with your wallet

        # 5. Send the transaction
        logger.info("Sending buy transaction...")
        resp = SOLANA_CLIENT.send_transaction(transaction)
        tx_signature = resp.value
        logger.info(f"Buy transaction sent: {tx_signature}")

        # 6. Wait for confirmation
        start_time = time.time()
        timeout = 60 # seconds
        while time.time() - start_time < timeout:
            confirmation = SOLANA_CLIENT.confirm_transaction(tx_signature, commitment="confirmed")
            if confirmation.value.err:
                logger.error(f"Buy transaction {tx_signature} failed: {confirmation.value.err}")
                return None
            if confirmation.value.context.slot > 0: # Confirmed
                logger.info(f"Buy transaction {tx_signature} confirmed!")
                break
            await asyncio.sleep(2) # Poll every 2 seconds
        else:
            logger.warning(f"Buy transaction {tx_signature} not confirmed within {timeout} seconds.")
            return None

        # 7. Get transaction details to extract amount bought
        amount_bought_token = int(quote_data['outAmount']) / (10**quote_data['outputMintDecimals']) # Convert from raw amount to actual units
        
        # Calculate actual token price in SOL (inAmount SOL / outAmount token)
        token_price_sol_at_buy = sol_amount_to_buy / amount_bought_token if amount_bought_token > 0 else 0

        # Determine your ATA for the token
        wallet_token_account = str(get_associated_token_address(WALLET_PUBKEY, token_mint_address))

        return {
            "token_mint_address": token_mint_address_str,
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