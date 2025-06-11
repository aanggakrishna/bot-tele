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
solana_service.init_solana_config(
    rpc_url=RPC_URL,
    private_key_path=PRIVATE_KEY_PATH,
    amount_to_buy_sol=AMOUNT_TO_BUY_SOL, # Kirim AMOUNT_TO_BUY_SOL
    slippage_bps=SLIPPAGE_BPS,
    jupiter_api_url=JUPITER_API_URL,
    solana_private_key_base58=SOLANA_PRIVATE_KEY_BASE58
)

# Initialize Telegram Client
client = TelegramClient('anon', API_ID, API_HASH)

# --- Helper Functions ---
async def send_dm_to_owner(message):
    try:
        await client.send_message(OWNER_ID, message)
        logger.info(f"Sent DM to owner: {message}")
    except Exception as e:
        logger.error(f"Error sending DM to owner: {e}")

def extract_solana_ca(message_text):
    solana_address_pattern = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
    match = re.search(solana_address_pattern, message_text)
    if match:
        try:
            PublicKey(match.group(0))
            return match.group(0)
        except ValueError:
            logger.warning(f"Extracted string '{match.group(0)}' is not a valid Solana Public Key.")
            return None
    return None

# --- Telegram Event Handler ---
@client.on(events.ChatAction)
async def pinned_message_handler(event):
    # Logika pengecekan yang lebih robust
    # Pastikan event memiliki 'action' dan 'pinned' dan 'message'
    if not hasattr(event, 'action') or \
       not hasattr(event.action, 'message') or \
       not hasattr(event, 'pinned') or \
       not event.pinned:
        logger.debug(f"Skipping ChatAction event: Not a relevant pinned message action. Event type: {type(event.action) if hasattr(event, 'action') else 'N/A'}")
        return # Abaikan event yang tidak memenuhi kriteria

    # Pastikan ini adalah event dari grup yang benar
    if event.peer_id.channel_id != abs(GROUP_ID):
        logger.debug(f"Skipping ChatAction event: Not from target group. Event group ID: {event.peer_id.channel_id}")
        return

    # Jika semua pemeriksaan lolos, ini adalah pinned message yang valid
    pinned_message = event.action.message
    message_text = pinned_message.message # Konten teks dari pesan

    logger.info(f"New Pinned Message detected in group {GROUP_ID}: {message_text[:200]}...")
    await send_dm_to_owner(f"New Pinned Message detected: {message_text[:200]}...")

    ca = extract_solana_ca(message_text)
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

# Price Check and Sell Logic (every 30 seconds)
@aiocron.crontab('*/30 * * * * *') # Every 30 seconds
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

    logger.info("Starting Telegram client...")
    await client.start()
    logger.info("Telegram client started.")

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