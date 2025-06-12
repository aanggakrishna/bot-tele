# main.py
import os
import re
import asyncio
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from dotenv import load_dotenv
from loguru import logger
import aiocron

# Local imports
from db_manager import init_db, get_db, add_trade, get_active_trades, update_trade_status, get_total_active_trades_count
import db_manager # Import penuh untuk Trade class
import solana_service
# OLD: from solana.publickey import PublicKey
from solders.pubkey import Pubkey as PublicKey # Import PublicKey dari solders

# --- Logging Configuration ---
logger.add("bot.log", rotation="10 MB")
logger.info("Starting bot application...")

# --- Load Environment Variables ---
load_dotenv()

# --- Telegram Configuration ---
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
OWNER_ID = int(os.getenv('OWNER_ID'))
GROUP_ID = int(os.getenv('GROUP_ID'))

# --- Solana Configuration ---
RPC_URL = os.getenv('RPC_URL')
PRIVATE_KEY_PATH = os.getenv('PRIVATE_KEY_PATH')
SOLANA_PRIVATE_KEY_BASE58 = os.getenv('SOLANA_PRIVATE_KEY_BASE58')
AMOUNT_TO_BUY_SOL = float(os.getenv('AMOUNT_TO_BUY_SOL')) # Ubah ke SOL
SLIPPAGE_BPS = int(os.getenv('SLIPPAGE_BPS'))
STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT'))
TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT'))
MAX_PURCHASES_ALLOWED = int(os.getenv('MAX_PURCHASES_ALLOWED'))
JUPITER_API_URL = os.getenv('JUPITER_API_URL')

# --- Initialize Services ---
# Initialize Solana Service
solana_service.init_solana_config_from_env()


# --- Heartbeat Function ---
async def heartbeat():
    while True:
        db = next(get_db())
        try:
            active_trades = get_total_active_trades_count(db)
            logger.info(f"Bot is running... Active trades: {active_trades}")
        except Exception as e:
            logger.error(f"Error in heartbeat: {e}")
        finally:
            db.close()
        await asyncio.sleep(5)

# Start heartbeat
async def start_heartbeat():
    asyncio.create_task(heartbeat())

# Initialize Telegram Client
client = TelegramClient('anon', API_ID, API_HASH)

# --- Helper Functions ---
async def send_dm_to_owner(message):
    try:
        await client.send_message(OWNER_ID, message)
        logger.info(f"Sent DM to owner: {message}")
    except Exception as e:
        logger.error(f"Error sending DM to owner: {e}")

# Ganti fungsi extract_solana_ca dengan yang ini:

# Ganti fungsi extract_solana_ca dengan yang ini di main.py:

def extract_solana_ca(message_text):
    """
    Ekstrak Solana CA dengan validasi yang lebih robust
    """
    # Pattern untuk Solana address (32-44 karakter, base58)
    solana_address_pattern = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
    matches = re.findall(solana_address_pattern, message_text)
    
    if not matches:
        logger.info("No potential Solana addresses found in message")
        return None
    
    logger.info(f"Found {len(matches)} potential addresses: {matches}")
    
    # Filter matches yang BUKAN alamat Solana yang valid
    # Lebih spesifik - hanya filter jika SELURUH string adalah kata yang dikecualikan
    excluded_full_words = ['www', 'http', 'https']  # Hanya kata-kata yang pasti bukan alamat
    
    for match in matches:
        logger.debug(f"Checking potential address: {match}")
        
        # Skip jika seluruh string adalah kata yang dikecualikan
        # if match.lower() in [word.lower() for word in excluded_full_words]:
        #     logger.debug(f"Skipping '{match}' - is excluded word")
        #     continue
        
        # Skip jika mengandung karakter yang jelas bukan alamat Solana
        if any(char in match for char in ['.', '/', ':', '@', '#']):
            logger.debug(f"Skipping '{match}' - contains invalid characters")
            continue
            
        # Validasi panjang (Solana address standar adalah 32-44 karakter)
        if not (32 <= len(match) <= 44):
            logger.debug(f"Skipping '{match}' - invalid length: {len(match)}")
            continue
        
        # Validasi karakter base58
        valid_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
        if not all(c in valid_chars for c in match):
            logger.debug(f"Skipping '{match}' - contains invalid base58 characters")
            continue
        
        # Validasi dengan library jika tersedia
        try:
            # Coba dengan solders
            from solders.pubkey import Pubkey
            validated_pubkey = Pubkey.from_string(match)
            logger.info(f"✅ Valid Solana address confirmed with solders: {match}")
            return match
        except Exception as e:
            logger.debug(f"solders validation failed for '{match}': {e}")
            
            # Fallback ke solana-py
            try:
                from solana.publickey import PublicKey as SolanaPublicKey
                SolanaPublicKey(match)
                logger.info(f"✅ Valid Solana address confirmed with solana-py: {match}")
                return match
            except Exception as e2:
                logger.debug(f"solana-py validation failed for '{match}': {e2}")
                
                # Fallback ke base58 manual
                try:
                    import base58
                    decoded = base58.b58decode(match)
                    if len(decoded) == 32:  # Solana address harus 32 bytes
                        logger.info(f"✅ Valid Solana address confirmed with base58: {match}")
                        return match
                    else:
                        logger.debug(f"base58 decode length mismatch for '{match}': {len(decoded)} bytes (expected 32)")
                except Exception as e3:
                    logger.debug(f"base58 validation failed for '{match}': {e3}")
                    continue
    
    logger.info("No valid Solana CA found after validation")
    return None


# Alternatif yang lebih sederhana - hanya validasi format tanpa filter kata
def extract_solana_ca_simple(message_text):
    """
    Ekstrak Solana CA dengan validasi sederhana tanpa filter kata yang berlebihan
    """
    # Pattern untuk Solana address
    solana_address_pattern = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
    matches = re.findall(solana_address_pattern, message_text)
    
    if not matches:
        logger.info("No potential Solana addresses found in message")
        return None
    
    logger.info(f"Found {len(matches)} potential addresses: {matches}")
    
    for match in matches:
        logger.debug(f"Checking potential address: {match}")
        
        # Skip jika mengandung karakter yang jelas bukan alamat Solana
        if any(char in match for char in ['.', '/', ':', '@', '#', ' ']):
            logger.debug(f"Skipping '{match}' - contains invalid characters")
            continue
            
        # Validasi panjang (Solana address biasanya 32-44 karakter)
        if 32 <= len(match) <= 44:
            # Validasi karakter (hanya base58)
            valid_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
            if all(c in valid_chars for c in match):
                logger.info(f"✅ Valid Solana address found: {match}")
                return match
            else:
                logger.debug(f"String '{match}' contains invalid base58 characters")
        else:
            logger.debug(f"String '{match}' has invalid length: {len(match)}")
    
    logger.info("No valid Solana CA found in the message.")
    return None
async def debug_solana_service():
    """Debug function to test solana service"""
    try:
        # Test dengan alamat yang valid
        test_address = "HLcVBPMpALNGMvixanRNxiL1NQ4rdXJaaExwaBCkpump"
        
        logger.info(f"Testing solana service with address: {test_address}")
        
        # Test validasi address
        from solana_service import validate_token_address
        validated = validate_token_address(test_address)
        
        if validated:
            logger.info(f"✅ Address validation successful: {validated}")
        else:
            logger.error("❌ Address validation failed")
            
        # Test price fetch
        if validated:
            price = await solana_service.get_token_price_sol(validated)
            if price:
                logger.info(f"✅ Price fetch successful: {price} SOL")
            else:
                logger.warning("⚠️ Could not fetch price (may be normal for new tokens)")
        
    except Exception as e:
        logger.error(f"Debug test failed: {e}", exc_info=True)

        # Ubah bagian dalam pinned_message_handler setelah mendapatkan CA:

        # --- Initiate Solana Buy Logic ---
        logger.info(f"Attempting to buy token: {ca}")
        
        # Debug: Test solana service first
        await debug_solana_service()
        
        buy_result = await solana_service.buy_token_solana(ca)

        if buy_result:
            logger.info(f"✅ Buy successful: {buy_result}")
            add_trade(
                db,
                token_mint_address=buy_result['token_mint_address'],
                buy_price_sol=buy_result['buy_price_sol'],
                amount_bought_token=buy_result['amount_bought_token'],
                wallet_token_account=buy_result['wallet_token_account'],
                buy_tx_signature=buy_result['buy_tx_signature']
            )
            await send_dm_to_owner(
                f"✅ **Beli Berhasil!**\n"
                f"Token: `{buy_result['token_mint_address']}`\n"
                f"Jumlah Dibeli: `{buy_result['amount_bought_token']:.6f}`\n"
                f"Harga Beli (SOL): `{buy_result['buy_price_sol']:.8f}`\n"
                f"Tx Sig: `{buy_result['buy_tx_signature'][:10]}...` [explorer](https://solscan.io/tx/{buy_result['buy_tx_signature']}{'?cluster=devnet' if RPC_URL == 'https://api.devnet.solana.com' else ''})\n"
                f"Total Pembelian Aktif: {get_total_active_trades_count(db)}/{MAX_PURCHASES_ALLOWED}"
            )
            logger.info(f"Successfully bought {ca}. Added to DB. Current active trades: {get_total_active_trades_count(db)}")
        else:
            await send_dm_to_owner(f"❌ **Pembelian Gagal** untuk token: `{ca}`. Cek log bot untuk detail lebih lanjut.")
            logger.error(f"Failed to buy token: {ca}")

# Tambahkan juga fungsi untuk test Jupiter API:

async def test_jupiter_api():
    """Test Jupiter API connectivity"""
    try:
        import aiohttp
        url = f"{JUPITER_API_URL}/tokens"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    logger.info("✅ Jupiter API is accessible")
                    return True
                else:
                    logger.error(f"❌ Jupiter API error: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"❌ Jupiter API test failed: {e}")
        return False


# --- Telegram Event Handler ---
# Ganti fungsi pinned_message_handler dengan yang ini:

@client.on(events.ChatAction)
async def pinned_message_handler(event):
    is_target_pin_event = False
    log_chat_id = "N/A"
    log_event_description = "Unknown ChatAction"
    log_content_preview = "N/A"
    log_group_name = "Unknown Group"

    if hasattr(event, 'chat_id'):
        log_chat_id = event.chat_id
        try:
            chat_entity_for_log = await event.get_chat()
            if chat_entity_for_log and hasattr(chat_entity_for_log, 'title'):
                log_group_name = chat_entity_for_log.title
        except Exception:
            pass

    if hasattr(event, 'new_pin') and event.new_pin:
        log_event_description = "Pin Action"
        if hasattr(event, 'action_message') and event.action_message and hasattr(event.action_message, 'message'):
            log_content_preview = str(event.action_message.message)[:100]
        
        # Check if it's the target group
        if hasattr(event, 'chat_id') and event.chat_id == -abs(GROUP_ID):
            is_target_pin_event = True
    elif hasattr(event, 'action_message') and event.action_message:
        log_event_description = f"Other ChatAction ({type(event.action_message.action).__name__ if hasattr(event.action_message, 'action') else 'Generic'})"
        if hasattr(event.action_message, 'message') and event.action_message.message:
            log_content_preview = str(event.action_message.message)[:100]
        else:
            log_content_preview = str(event.action_message)[:100]
    elif hasattr(event, 'original_update') and hasattr(event.original_update, 'message'):
        log_content_preview = str(event.original_update.message)[:100]
        if "pin" in log_content_preview.lower():
            log_event_description = "Possible Pin (from original_update)"

    # Log event details for debugging
    logger.debug(f"Processing event - Group: {log_group_name} (ID: {log_chat_id}), Event Type: {log_event_description}, Content: {log_content_preview}")

    if not is_target_pin_event:
        logger.debug(
            f"Skipping ChatAction event: Not a pin action in target group {GROUP_ID}. "
            f"Current group: {log_group_name} (ID: {log_chat_id}), "
            f"Event type: {log_event_description}, "
            f"Content: {log_content_preview}")
        return

    logger.info(f"Pin event detected in target group {log_group_name} (ID: {log_chat_id})")

    # --- PERBAIKAN: Ambil pesan yang di-pin secara manual ---
    message_text = None
    
    # Method 1: Coba ambil dari event.pinned_message jika ada
    if hasattr(event, 'pinned_message') and event.pinned_message:
        actual_pinned_message_object = event.pinned_message
        
        # Check if it's a MessageService object
        if hasattr(actual_pinned_message_object, '__class__') and actual_pinned_message_object.__class__.__name__ == 'MessageService':
            if hasattr(actual_pinned_message_object, 'action') and hasattr(actual_pinned_message_object.action, 'message'):
                message_text = actual_pinned_message_object.action.message
        else:
            # Try regular message attributes
            if hasattr(actual_pinned_message_object, 'message') and actual_pinned_message_object.message:
                message_text = actual_pinned_message_object.message
            elif hasattr(actual_pinned_message_object, 'text') and actual_pinned_message_object.text:
                message_text = actual_pinned_message_object.text
    
    # Method 2: Jika Method 1 gagal, ambil pesan yang di-pin dari chat
    if not message_text:
        logger.warning(f"event.pinned_message is None or empty. Trying to fetch pinned message manually from chat {log_chat_id}")
        
        try:
            # Ambil pesan yang di-pin dari chat
            chat_entity = await client.get_entity(log_chat_id)
            full_chat = await client.get_entity(chat_entity)
            
            # Cek apakah ada pinned_msg_id di full chat
            pinned_msg_id = None
            if hasattr(full_chat, 'pinned_msg_id') and full_chat.pinned_msg_id:
                pinned_msg_id = full_chat.pinned_msg_id
            elif hasattr(full_chat, 'full_chat') and hasattr(full_chat.full_chat, 'pinned_msg_id'):
                pinned_msg_id = full_chat.full_chat.pinned_msg_id
            
            if pinned_msg_id:
                logger.info(f"Found pinned message ID: {pinned_msg_id}")
                
                # Ambil pesan berdasarkan ID
                pinned_messages = await client.get_messages(log_chat_id, ids=[pinned_msg_id])
                if pinned_messages and len(pinned_messages) > 0:
                    pinned_msg = pinned_messages[0]
                    if hasattr(pinned_msg, 'message') and pinned_msg.message:
                        message_text = pinned_msg.message
                        logger.info(f"Successfully retrieved pinned message text: {message_text[:100]}...")
                    elif hasattr(pinned_msg, 'text') and pinned_msg.text:
                        message_text = pinned_msg.text
                        logger.info(f"Successfully retrieved pinned message text: {message_text[:100]}...")
                else:
                    logger.warning(f"Could not retrieve message with ID {pinned_msg_id}")
            else:
                logger.warning(f"No pinned message ID found in chat {log_chat_id}")
                
        except Exception as e:
            logger.error(f"Error fetching pinned message manually: {e}")
    
    # Method 3: Jika semua method gagal, coba ambil pesan terbaru yang di-pin
    if not message_text:
        logger.warning("All methods failed. Trying to get recent pinned messages...")
        
        try:
            # Ambil beberapa pesan terbaru dan cari yang di-pin
            recent_messages = await client.get_messages(log_chat_id, limit=50)
            
            for msg in recent_messages:
                if hasattr(msg, 'pinned') and msg.pinned:
                    if hasattr(msg, 'message') and msg.message:
                        message_text = msg.message
                        logger.info(f"Found pinned message in recent messages: {message_text[:100]}...")
                        break
                    elif hasattr(msg, 'text') and msg.text:
                        message_text = msg.text
                        logger.info(f"Found pinned message in recent messages: {message_text[:100]}...")
                        break
                        
        except Exception as e:
            logger.error(f"Error fetching recent pinned messages: {e}")
    
    # Jika masih tidak ada message_text, beri peringatan
    if not message_text:
        logger.error(f"FAILED to retrieve pinned message text from group {log_group_name} (ID: {log_chat_id}) after trying all methods")
        await send_dm_to_owner(f"⚠️ Pin event detected in {log_group_name}, but couldn't retrieve message content. Please check manually.")
        return

    # Lanjutkan dengan logika normal
    logger.info(f"New Pinned Message detected in group {log_group_name} (ID: {log_chat_id}): {message_text[:200]}...")
    await send_dm_to_owner(f"New Pinned Message detected in {log_group_name}: {message_text[:200]}...")

    ca = extract_solana_ca_simple(message_text[:200])
    if ca:
        logger.info(f"Detected potential Solana CA: {ca}")
        await send_dm_to_owner(f"Detected Solana CA: {ca}")

        db = next(get_db())
        try:
            active_trades_count = get_total_active_trades_count(db)
            if active_trades_count >= MAX_PURCHASES_ALLOWED:
                await send_dm_to_owner(f"Purchase limit reached ({MAX_PURCHASES_ALLOWED} active purchases). Cannot buy more until existing positions are sold or cleared.")
                logger.warning("Purchase limit reached. Skipping purchase.")
                return

            existing_trade = db.query(db_manager.Trade).filter(db_manager.Trade.token_mint_address == ca).first()
            if existing_trade and existing_trade.status == "active":
                await send_dm_to_owner(f"Token {ca} is already an active trade. Skipping purchase.")
                logger.warning(f"Token {ca} is already an active trade. Skipping purchase.")
                return

            # --- Initiate Solana Buy Logic ---
            buy_result = await solana_service.buy_token_solana(ca)

            if buy_result:
                add_trade(
                    db,
                    token_mint_address=buy_result['token_mint_address'],
                    buy_price_sol=buy_result['buy_price_sol'],
                    amount_bought_token=buy_result['amount_bought_token'],
                    wallet_token_account=buy_result['wallet_token_account'],
                    buy_tx_signature=buy_result['buy_tx_signature']
                )
                await send_dm_to_owner(
                    f"✅ **Beli Berhasil!**\n"
                    f"Token: `{buy_result['token_mint_address']}`\n"
                    f"Jumlah Dibeli: `{buy_result['amount_bought_token']:.6f}`\n"
                    f"Harga Beli (SOL): `{buy_result['buy_price_sol']:.8f}`\n"
                    f"Tx Sig: `{buy_result['buy_tx_signature'][:10]}...` [explorer](https://solscan.io/tx/{buy_result['buy_tx_signature']}{'?cluster=devnet' if RPC_URL == 'https://api.devnet.solana.com' else ''})\n"
                    f"Total Pembelian Aktif: {get_total_active_trades_count(db)}/{MAX_PURCHASES_ALLOWED}"
                )
                logger.info(f"Successfully bought {ca}. Added to DB. Current active trades: {get_total_active_trades_count(db)}")
            else:
                await send_dm_to_owner(f"❌ **Pembelian Gagal** untuk token: `{ca}`. Cek log bot.")
                logger.error(f"Failed to buy token: {ca}")
        finally:
            db.close()
    else:
        logger.info("No Solana CA found in the pinned message.")
        await send_dm_to_owner("No Solana CA found in the pinned message.")

# --- Scheduled Tasks (using aiocron) ---

# Heartbeat (every 10 minutes)
@aiocron.crontab('*/10 * * * *')
async def dm_heartbeat():
    db = next(get_db())
    try:
        active_count = get_total_active_trades_count(db)
        await send_dm_to_owner(f"❤️ Heartbeat: Bot is running. Active trades: {active_count}/{MAX_PURCHASES_ALLOWED}.")
        logger.info("Sent DM Heartbeat.")
    finally:
        db.close()

# Price Check and Sell Logic (every x seconds)
@aiocron.crontab('*/5 * * * * *') # Every x seconds
async def monitor_trades_and_sell():
    db = next(get_db())
    try:
        active_trades = get_active_trades(db)
        if not active_trades:
            logger.info("No active trades to monitor.")
            return

        logger.info(f"Monitoring {len(active_trades)} active trades...")

        for trade in active_trades:
            token_mint_address = trade.token_mint_address
            amount_bought_token = trade.amount_bought_token
            buy_price_sol = trade.buy_price_sol # Ambil harga beli dalam SOL
            buy_timestamp = trade.buy_timestamp
            wallet_token_account = trade.wallet_token_account

            logger.info(f"Checking trade: {token_mint_address}")

            current_token_price_sol = await solana_service.get_token_price_sol(PublicKey(token_mint_address))
            if current_token_price_sol is None:
                logger.warning(f"Could not fetch current price for {token_mint_address}. Skipping.")
                continue

            # Hitung profit/loss dalam SOL
            profit_loss_sol_percent = ((current_token_price_sol - buy_price_sol) / buy_price_sol)

            logger.info(f"Trade {token_mint_address}: Buy SOL={buy_price_sol:.8f}, Current SOL={current_token_price_sol:.8f}, P/L: {profit_loss_sol_percent*100:.2f}%")

            should_sell = False
            sell_reason = ""

            # 1. Take Profit
            if profit_loss_sol_percent >= TAKE_PROFIT_PERCENT:
                should_sell = True
                sell_reason = f"Take Profit ({TAKE_PROFIT_PERCENT*100:.2f}%)"
                logger.info(f"Triggering TP for {token_mint_address}: {profit_loss_sol_percent*100:.2f}% >= {TAKE_PROFIT_PERCENT*100:.2f}%")
            # 2. Stop Loss
            elif profit_loss_sol_percent <= -STOP_LOSS_PERCENT: # Note the negative sign for stop loss
                should_sell = True
                sell_reason = f"Stop Loss ({STOP_LOSS_PERCENT*100:.2f}%)"
                logger.info(f"Triggering SL for {token_mint_address}: {profit_loss_sol_percent*100:.2f}% <= -{STOP_LOSS_PERCENT*100:.2f}%")
            # 3. Time-based Sell (1 day with no significant movement)
            elif (datetime.utcnow() - buy_timestamp) > timedelta(days=1):
                # Define "significant movement" - e.g., price hasn't moved +/- 5% in 24h
                if abs(profit_loss_sol_percent) < 0.05: # Less than 5% movement either way
                    should_sell = True
                    sell_reason = "Time-based Sell (1 day, no significant movement)"
                    logger.info(f"Triggering time-based sell for {token_mint_address}: 1 day elapsed, no significant movement.")


            if should_sell:
                logger.warning(f"Initiating sell for {token_mint_address} due to: {sell_reason}")
                await send_dm_to_owner(f"🚨 **Mulai Jual!**\nToken: `{token_mint_address}`\nAlasan: `{sell_reason}`")

                sell_result = await solana_service.sell_token_solana(token_mint_address, amount_bought_token, wallet_token_account)

                if sell_result:
                    updated_trade = update_trade_status(
                        db,
                        trade.id,
                        status="sold_profit" if "Profit" in sell_reason else ("sold_sl" if "Loss" in sell_reason else "sold_time"),
                        sell_price_sol=sell_result['sell_price_sol'], # Hanya harga SOL
                        sell_tx_signature=sell_result['sell_tx_signature']
                    )
                    # Hitung profit akhir dalam SOL
                    profit_final_sol_percent = ((updated_trade.sell_price_sol - updated_trade.buy_price_sol) / updated_trade.buy_price_sol) if updated_trade.buy_price_sol else 0

                    await send_dm_to_owner(
                        f"✅ **Jual Berhasil!**\n"
                        f"Token: `{token_mint_address}`\n"
                        f"Alasan: `{sell_reason}`\n"
                        f"Harga Jual (SOL): `{sell_result['sell_price_sol']:.8f}`\n"
                        f"P/L Akhir (SOL): `{profit_final_sol_percent*100:.2f}%`\n"
                        f"Tx Sig: `{sell_result['sell_tx_signature'][:10]}...` [explorer](https://solscan.io/tx/{sell_result['sell_tx_signature']}{'?cluster=devnet' if RPC_URL == 'https://api.devnet.solana.com' else ''})"
                    )
                    logger.info(f"Successfully sold {token_mint_address}. Status updated to {updated_trade.status}.")
                else:
                    await send_dm_to_owner(f"❌ **Gagal Jual** untuk token: `{token_mint_address}`. Cek log bot.")
                    logger.error(f"Failed to sell token: {token_mint_address}")
    except Exception as e:
        logger.error(f"Error in monitor_trades_and_sell: {e}", exc_info=True)
    finally:
        db.close()


async def main():
    logger.info("Initializing database...")
    init_db()

    # Test Jupiter API
    logger.info("Testing Jupiter API connectivity...")
    jupiter_ok = await test_jupiter_api()
    if not jupiter_ok:
        logger.warning("Jupiter API test failed - trading may not work properly")

    logger.info("Starting Telegram client...")
    await client.start()
    logger.info("Telegram client started.")

    # Start heartbeat
    await start_heartbeat()
    logger.info("Heartbeat started.")

    try:
        entity = await client.get_entity(GROUP_ID)
        logger.info(f"Connected to group: {entity.title} ({entity.id})")
    except Exception as e:
        logger.error(f"Error getting group entity for {GROUP_ID}: {e}. Ensure bot is in group.")
        await send_dm_to_owner(f"‼️ **Error:** Bot tidak dapat terhubung ke grup `{GROUP_ID}`. Pastikan bot adalah anggota grup tersebut.")
        exit(1)

    if not os.path.exists('anon.session'):
        logger.warning("Telethon session file not found. First run, please follow authentication prompt.")
        await send_dm_to_owner("👋 Bot pertama kali dijalankan! Silakan ikuti instruksi di konsol untuk otentikasi Telegram Anda.")

    logger.info("Bot is fully initialized and listening for events and running scheduled tasks...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"An unhandled critical error occurred: {e}", exc_info=True)
        asyncio.run(send_dm_to_owner(f"🚨 **CRITICAL ERROR!** Bot berhenti karena error tak terduga: `{e}`. Cek log server!"))