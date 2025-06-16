import os
import re
import asyncio
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest
from dotenv import load_dotenv
from loguru import logger
import aiohttp

# Local imports
from db_manager import init_db, get_db, add_trade, get_active_trades, update_trade_status, get_total_active_trades_count, Trade
import solana_service
from trading_service import MultiPlatformTradingService, extract_solana_ca_enhanced
from solders.pubkey import Pubkey as PublicKey

# --- Logging Configuration ---
logger.add("bot.log", rotation="10 MB", level="INFO")
logger.add("debug.log", rotation="10 MB", level="DEBUG")
logger.info("🚀 Starting Solana Multi-Platform Trading Bot...")

# --- Load Environment Variables ---
load_dotenv()

# --- Telegram Configuration ---
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
OWNER_ID = int(os.getenv('OWNER_ID'))
GROUP_ID = int(os.getenv('GROUP_ID'))

# --- Solana Configuration ---
RPC_URL = os.getenv('RPC_URL', 'https://api.mainnet-beta.solana.com')
SOLANA_PRIVATE_KEY_BASE58 = os.getenv('SOLANA_PRIVATE_KEY_BASE58')
AMOUNT_TO_BUY_SOL = float(os.getenv('AMOUNT_TO_BUY_SOL', '0.01'))
SLIPPAGE_BPS = int(os.getenv('SLIPPAGE_BPS', '300'))
STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '0.20'))
TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '0.50'))
MAX_PURCHASES_ALLOWED = int(os.getenv('MAX_PURCHASES_ALLOWED', '2'))
JUPITER_API_URL = os.getenv('JUPITER_API_URL', 'https://quote-api.jup.ag/v6')

# --- Initialize Services ---
logger.info("Initializing Solana service...")
solana_service.init_solana_config_from_env()

logger.info("Initializing multi-platform trading service...")
multi_platform_service = MultiPlatformTradingService(solana_service)

# Initialize Telegram Client
client = TelegramClient('solana_bot', API_ID, API_HASH)

# --- Helper Functions ---
async def get_group_info(group_id):
    """Get group information including name"""
    try:
        # Convert to absolute value if negative
        actual_group_id = -abs(group_id) if group_id > 0 else group_id
        
        # Get group entity
        group_entity = await client.get_entity(actual_group_id)
        
        # Safely get participants count
        participants_count = getattr(group_entity, 'participants_count', None)
        if participants_count is None:
            participants_count = 0
        
        group_info = {
            'id': actual_group_id,
            'title': getattr(group_entity, 'title', 'Unknown Group'),
            'username': getattr(group_entity, 'username', None),
            'participants_count': participants_count
        }
        
        return group_info
        
    except Exception as e:
        logger.error(f"❌ Error getting group info for {group_id}: {e}")
        return {
            'id': group_id,
            'title': 'Unknown Group',
            'username': None,
            'participants_count': 0
        }

async def send_dm_to_owner(message):
    """Send direct message to bot owner"""
    try:
        await client.send_message(OWNER_ID, message, parse_mode='markdown')
        logger.info(f"📱 Sent DM to owner: {message[:100]}...")
    except Exception as e:
        logger.error(f"❌ Error sending DM to owner: {e}")

async def test_jupiter_api():
    """Test Jupiter API connectivity"""
    try:
        logger.info("Testing Jupiter API connectivity...")
        jupiter_url = os.getenv('JUPITER_API_URL', 'https://quote-api.jup.ag/v6')
        
        async with aiohttp.ClientSession() as session:
            # Test simple quote request
            url = f"{jupiter_url}/quote"
            params = {
                'inputMint': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',  # BONK
                'outputMint': 'So11111111111111111111111111111111111111112',   # WSOL
                'amount': 1000000,  # 1 BONK (6 decimals)
                'slippageBps': 500
            }
            
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Jupiter API is working - Quote: {data.get('outAmount', 'unknown')} lamports")
                    return True
                else:
                    logger.warning(f"⚠️ Jupiter API returned status: {response.status}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Jupiter API test failed: {e}")
        return False

async def debug_solana_service():
    """Debug function to test solana service"""
    try:
        # Test with a known valid token address (not WSOL)
        # Using BONK token as example (common Solana token)
        test_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # BONK token
        
        logger.info(f"Testing solana service with token address: {test_address}")
        
        # Skip the price test if wallet is not initialized
        if not solana_service.solana_service_instance.keypair:
            logger.info("⚠️ Wallet not initialized - skipping price test")
            logger.info("✅ Solana service initialized in monitoring mode")
            return True
        
        # Test price fetch only if wallet is available
        try:
            price = await solana_service.get_token_price_sol(PublicKey.from_string(test_address))
            if price:
                logger.info(f"✅ Price fetch successful: {price} SOL per token")
            else:
                logger.warning("⚠️ Could not fetch price")
        except Exception as price_e:
            logger.warning(f"⚠️ Price test failed: {price_e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Debug test failed: {e}")
        return False

# --- Background Task Functions (without decorators) ---
async def dm_heartbeat():
    """Send heartbeat DM to owner"""
    db = next(get_db())
    try:
        active_count = get_total_active_trades_count(db)
        
        # Get fresh group info for heartbeat with safe checking
        group_info = await get_group_info(GROUP_ID)
        
        heartbeat_message = (
            f"💓 **Bot Heartbeat**\n\n"
            f"Status: `Online`\n"
            f"📺 Monitoring: `{group_info['title']}`\n"
            f"🆔 Group ID: `{group_info['id']}`\n"
            f"📊 Active trades: `{active_count}/{MAX_PURCHASES_ALLOWED}`\n"
            f"⏰ Time: `{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC`"
        )
        
        # Add optional info if available
        if group_info.get('username'):
            heartbeat_message += f"\n🔗 @{group_info['username']}"
        
        participants_count = group_info.get('participants_count', 0)
        if participants_count and participants_count > 0:
            heartbeat_message += f"\n👥 {participants_count} members"
        
        await send_dm_to_owner(heartbeat_message)
        logger.info(f"📱 Sent DM Heartbeat for group: {group_info['title']}")
    except Exception as e:
        logger.error(f"❌ Error in DM heartbeat: {e}")
    finally:
        db.close()


async def monitor_trades_and_sell():
    """Monitor active trades and execute sell logic"""
    db = next(get_db())
    try:
        active_trades = get_active_trades(db)
        if not active_trades:
            return

        logger.info(f"📊 Monitoring {len(active_trades)} active trades...")

        for trade in active_trades:
            token_mint_address = trade.token_mint_address
            amount_bought_token = trade.amount_bought_token
            buy_price_sol = trade.buy_price_sol
            buy_timestamp = trade.buy_timestamp
            wallet_token_account = trade.wallet_token_account
            platform = trade.platform or 'unknown'

            logger.debug(f"🔍 Checking trade: {token_mint_address} ({platform})")

            # Get current price
            try:
                current_token_price_sol = await solana_service.get_token_price_sol(PublicKey(token_mint_address))
                if current_token_price_sol is None:
                    logger.warning(f"⚠️ Could not fetch current price for {token_mint_address}. Skipping.")
                    continue
            except Exception as e:
                logger.error(f"❌ Error fetching price for {token_mint_address}: {e}")
                continue

            # Calculate profit/loss percentage
            if buy_price_sol <= 0:
                logger.warning(f"⚠️ Invalid buy price for {token_mint_address}: {buy_price_sol}")
                continue
                
            profit_loss_percent = (current_token_price_sol - buy_price_sol) / buy_price_sol

            logger.info(f"📈 {platform.upper()} {token_mint_address}: Buy={buy_price_sol:.8f} SOL, Current={current_token_price_sol:.8f} SOL, P/L={profit_loss_percent*100:.2f}%")

            should_sell = False
            sell_reason = ""

            # 1. Take Profit Check
            if profit_loss_percent >= TAKE_PROFIT_PERCENT:
                should_sell = True
                sell_reason = f"Take Profit ({TAKE_PROFIT_PERCENT*100:.1f}%)"
                logger.info(f"🎯 Take profit triggered for {token_mint_address}: {profit_loss_percent*100:.2f}% >= {TAKE_PROFIT_PERCENT*100:.1f}%")
            
            # 2. Stop Loss Check
            elif profit_loss_percent <= -STOP_LOSS_PERCENT:
                should_sell = True
                sell_reason = f"Stop Loss ({STOP_LOSS_PERCENT*100:.1f}%)"
                logger.info(f"🛑 Stop loss triggered for {token_mint_address}: {profit_loss_percent*100:.2f}% <= -{STOP_LOSS_PERCENT*100:.1f}%")
            
            # 3. Time-based Sell (1 day with no significant movement)
            elif (datetime.utcnow() - buy_timestamp) > timedelta(days=1):
                # Define "significant movement" - e.g., price hasn't moved +/- 5% in 24h
                if abs(profit_loss_percent) < 0.05:  # Less than 5% movement
                    should_sell = True
                    sell_reason = "Time-based Sell (1 day, no significant movement)"
                    logger.info(f"⏰ Time-based sell triggered for {token_mint_address}: 1 day elapsed, minimal movement")

            if should_sell:
                logger.warning(f"🚨 Initiating sell for {token_mint_address} due to: {sell_reason}")
                
                platform_emoji = {
                    'pumpfun': '🚀',
                    'moonshot': '🌙', 
                    'raydium': '⚡',
                    'jupiter': '🪐',
                    'generic': '🔄'
                }.get(platform, '🔄')
                
                await send_dm_to_owner(
                    f"🚨 **Initiating Sell**\n\n"
                    f"{platform_emoji} Platform: `{platform.upper()}`\n"
                    f"🪙 Token: `{token_mint_address}`\n"
                    f"📊 Reason: `{sell_reason}`\n"
                    f"📈 P/L: `{profit_loss_percent*100:.2f}%`"
                )

                try:
                    sell_result = await multi_platform_service.sell_token_multi_platform(
                        token_mint_address, amount_bought_token, wallet_token_account, platform
                    )

                    if sell_result:
                        # Determine status based on sell reason
                        if "Profit" in sell_reason:
                            status = "sold_profit"
                        elif "Loss" in sell_reason:
                            status = "sold_sl"
                        else:
                            status = "sold_time"

                        updated_trade = update_trade_status(
                            db,
                            trade.id,
                            status=status,
                            sell_price_sol=sell_result['sell_price_sol'],
                            sell_tx_signature=sell_result['sell_tx_signature']
                        )
                        
                        # Calculate final profit/loss
                        final_profit_percent = ((updated_trade.sell_price_sol - updated_trade.buy_price_sol) / updated_trade.buy_price_sol) * 100 if updated_trade.buy_price_sol else 0
                        profit_sol = (updated_trade.sell_price_sol - updated_trade.buy_price_sol) * amount_bought_token if updated_trade.sell_price_sol and updated_trade.buy_price_sol else 0

                        explorer_url = f"https://solscan.io/tx/{sell_result['sell_tx_signature']}"
                        if 'devnet' in RPC_URL:
                            explorer_url += "?cluster=devnet"

                        await send_dm_to_owner(
                            f"✅ **Sell Successful!**\n\n"
                            f"{platform_emoji} Platform: `{platform.upper()}`\n"
                            f"🪙 Token: `{token_mint_address}`\n"
                            f"📊 Reason: `{sell_reason}`\n"
                            f"💰 Sell Price: `{sell_result['sell_price_sol']:.8f} SOL`\n"
                            f"📈 Final P/L: `{final_profit_percent:.2f}%`\n"
                            f"💎 SOL P/L: `{profit_sol:.6f} SOL`\n"
                            f"🔗 [View Transaction]({explorer_url})\n"
                            f"📊 Active Trades: `{get_total_active_trades_count(db)}/{MAX_PURCHASES_ALLOWED}`"
                        )
                        logger.info(f"✅ Successfully sold {token_mint_address}. Status: {updated_trade.status}")
                    else:
                        await send_dm_to_owner(
                            f"❌ **Sell Failed**\n\n"
                            f"{platform_emoji} Platform: `{platform.upper()}`\n"
                            f"🪙 Token: `{token_mint_address}`\n"
                            f"Check bot logs for details."
                        )
                        logger.error(f"❌ Failed to sell token: {token_mint_address}")
                        
                except Exception as e:
                    logger.error(f"❌ Error selling {token_mint_address}: {e}", exc_info=True)
                    await send_dm_to_owner(f"🚨 **Sell Error**\n\nToken: `{token_mint_address}`\nError: `{str(e)[:200]}`")

    except Exception as e:
        logger.error(f"❌ Error in monitor_trades_and_sell: {e}", exc_info=True)
    finally:
        db.close()

# --- Background Tasks Runner ---
async def background_tasks():
    """Run background tasks manually with asyncio"""
    async def periodic_monitoring():
        """Monitor trades every 30 seconds"""
        while True:
            try:
                await monitor_trades_and_sell()
            except Exception as e:
                logger.error(f"❌ Error in periodic monitoring: {e}")
            await asyncio.sleep(30)  # 30 seconds
    
    async def periodic_heartbeat():
        """Send heartbeat every 30 minutes"""
        while True:
            try:
                await dm_heartbeat()
            except Exception as e:
                logger.error(f"❌ Error in periodic heartbeat: {e}")
            await asyncio.sleep(1800)  # 30 minutes
    
    # Start both tasks concurrently
    await asyncio.gather(
        periodic_monitoring(),
        periodic_heartbeat()
    )

# --- Telegram Event Handler ---
@client.on(events.ChatAction)
async def pinned_message_handler(event):
    """Handle pinned message events in target group"""
    
    # Event logging variables
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

    # Check if this is a pin event in our target group
    if hasattr(event, 'new_pin') and event.new_pin:
        log_event_description = "Pin Action"
        if hasattr(event, 'action_message') and event.action_message and hasattr(event.action_message, 'message'):
            log_content_preview = str(event.action_message.message)[:100]
        
        # Check if it's the target group
        if hasattr(event, 'chat_id') and event.chat_id == -abs(GROUP_ID):
            is_target_pin_event = True

    # Enhanced logging with group name
    logger.debug(f"📝 Processing event - Group: '{log_group_name}' (ID: {log_chat_id}), Event Type: {log_event_description}")

    if not is_target_pin_event:
        logger.debug(f"⏭️ Skipping event: Not a pin action in target group '{log_group_name}' (Expected: {GROUP_ID})")
        return

    logger.info(f"📌 Pin event detected in target group '{log_group_name}' (ID: {log_chat_id})")

    # --- Get Pinned Message Content ---
    message_text = None
    
    # Method 1: Try to get from event.pinned_message
    if hasattr(event, 'pinned_message') and event.pinned_message:
        actual_pinned_message_object = event.pinned_message
        
        if hasattr(actual_pinned_message_object, 'message') and actual_pinned_message_object.message:
            message_text = actual_pinned_message_object.message
        elif hasattr(actual_pinned_message_object, 'text') and actual_pinned_message_object.text:
            message_text = actual_pinned_message_object.text
    
    # Method 2: Manually fetch pinned message from chat
    if not message_text:
        logger.warning(f"⚠️ event.pinned_message is None. Fetching pinned message manually from chat {log_chat_id}")
        
        try:
            # Get chat entity and pinned message ID
            chat_entity = await client.get_entity(log_chat_id)
            full_chat = await client(GetFullChatRequest(chat_entity))
            
            pinned_msg_id = None
            if hasattr(full_chat, 'pinned_msg_id') and full_chat.pinned_msg_id:
                pinned_msg_id = full_chat.pinned_msg_id
            elif hasattr(full_chat, 'full_chat') and hasattr(full_chat.full_chat, 'pinned_msg_id'):
                pinned_msg_id = full_chat.full_chat.pinned_msg_id
            
            if pinned_msg_id:
                logger.info(f"🔍 Found pinned message ID: {pinned_msg_id}")
                
                # Get message by ID
                pinned_messages = await client.get_messages(log_chat_id, ids=[pinned_msg_id])
                if pinned_messages and len(pinned_messages) > 0:
                    pinned_msg = pinned_messages[0]
                    if hasattr(pinned_msg, 'message') and pinned_msg.message:
                        message_text = pinned_msg.message
                        logger.info(f"✅ Successfully retrieved pinned message")
                    elif hasattr(pinned_msg, 'text') and pinned_msg.text:
                        message_text = pinned_msg.text
                        logger.info(f"✅ Successfully retrieved pinned message")
            
        except Exception as e:
            logger.error(f"❌ Error fetching pinned message manually: {e}")
    
    # Method 3: Fallback - get recent pinned messages
    if not message_text:
        logger.warning("⚠️ All methods failed. Trying to get recent pinned messages...")
        
        try:
            recent_messages = await client.get_messages(log_chat_id, limit=50)
            
            for msg in recent_messages:
                if hasattr(msg, 'pinned') and msg.pinned:
                    if hasattr(msg, 'message') and msg.message:
                        message_text = msg.message
                        logger.info(f"✅ Found pinned message in recent messages")
                        break
                    elif hasattr(msg, 'text') and msg.text:
                        message_text = msg.text
                        logger.info(f"✅ Found pinned message in recent messages")
                        break
                        
        except Exception as e:
            logger.error(f"❌ Error fetching recent pinned messages: {e}")
    
    # Final check
    if not message_text:
        logger.error(f"❌ FAILED to retrieve pinned message text from group {log_group_name}")
        await send_dm_to_owner(f"⚠️ **Pin Event Detected**\n\nGroup: `{log_group_name}`\n❌ Could not retrieve message content. Please check manually.")
        return

    # Continue with normal logic
    logger.info(f"📄 New Pinned Message detected: {message_text[:200]}...")
    await send_dm_to_owner(f"📌 **New Pinned Message**\n\nGroup: `{log_group_name}`\nContent: `{message_text[:200]}...`")

    # Extract Solana CA using enhanced detection
    ca = extract_solana_ca_enhanced(message_text)
    if ca:
        logger.info(f"🪙 Detected potential Solana CA in '{log_group_name}': {ca}")
        await send_dm_to_owner(f"🔍 **Solana CA Detected**\n\nGroup: `{log_group_name}`\nToken: `{ca}`\nProcessing purchase...")

        db = next(get_db())
        try:
            # Check purchase limits
            active_trades_count = get_total_active_trades_count(db)
            if active_trades_count >= MAX_PURCHASES_ALLOWED:
                await send_dm_to_owner(
                    f"⛔ **Purchase Limit Reached**\n\n"
                    f"Active trades: {active_trades_count}/{MAX_PURCHASES_ALLOWED}\n"
                    f"Cannot buy more until existing positions are sold."
                )
                logger.warning("Purchase limit reached. Skipping purchase.")
                return

            # Check if token already exists
            existing_trade = db.query(Trade).filter(Trade.token_mint_address == ca).first()
            if existing_trade and existing_trade.status == "active":
                await send_dm_to_owner(
                    f"⚠️ **Token Already Active**\n\n"
                    f"Token: `{ca}`\n"
                    f"Platform: `{existing_trade.platform or 'Unknown'}`\n"
                    f"Status: `{existing_trade.status}`"
                )
                logger.warning(f"Token {ca} is already an active trade. Skipping purchase.")
                return

            # --- Initiate Multi-Platform Buy Logic ---
            logger.info(f"🚀 Attempting to buy token: {ca}")
            await send_dm_to_owner(f"🔄 **Starting Purchase**\n\nToken: `{ca}`\nAmount: `{AMOUNT_TO_BUY_SOL} SOL`")
            
            buy_result = await multi_platform_service.buy_token_multi_platform(ca, message_text)

            if buy_result:
                # Add trade to database with platform info
                add_trade(
                    db,
                    token_mint_address=buy_result['token_mint_address'],
                    buy_price_sol=buy_result['buy_price_sol'],
                    amount_bought_token=buy_result['amount_bought_token'],
                    wallet_token_account=buy_result['wallet_token_account'],
                    buy_tx_signature=buy_result['buy_tx_signature'],
                    platform=buy_result.get('platform', 'unknown'),
                    bonding_curve_complete=buy_result.get('bonding_curve_complete')
                )
                
                # Send success notification
                platform_emoji = {
                    'pumpfun': '🚀',
                    'moonshot': '🌙', 
                    'raydium': '⚡',
                    'jupiter': '🪐',
                    'generic': '🔄'
                }.get(buy_result.get('platform', 'generic'), '🔄')
                
                explorer_url = f"https://solscan.io/tx/{buy_result['buy_tx_signature']}"
                if 'devnet' in RPC_URL:
                    explorer_url += "?cluster=devnet"
                
                await send_dm_to_owner(
                    f"✅ **Purchase Successful!**\n\n"
                    f"{platform_emoji} Platform: `{buy_result.get('platform', 'Unknown').upper()}`\n"
                    f"🪙 Token: `{buy_result['token_mint_address']}`\n"
                    f"💰 Amount: `{buy_result['amount_bought_token']:.6f} tokens`\n"
                    f"💎 Price: `{buy_result['buy_price_sol']:.8f} SOL`\n"
                    f"🔗 [View Transaction]({explorer_url})\n"
                    f"📊 Active Trades: `{get_total_active_trades_count(db)}/{MAX_PURCHASES_ALLOWED}`"
                )
                logger.info(f"✅ Successfully bought {ca} from {buy_result.get('platform', 'unknown')}. Added to DB.")
            else:
                await send_dm_to_owner(
                    f"❌ **Purchase Failed**\n\n"
                    f"Token: `{ca}`\n"
                    f"Check bot logs for details."
                )
                logger.error(f"❌ Failed to buy token: {ca}")
                
        except Exception as e:
            logger.error(f"❌ Error in buy process: {e}", exc_info=True)
            await send_dm_to_owner(f"🚨 **Error in Purchase Process**\n\nToken: `{ca}`\nError: `{str(e)[:200]}`")
        finally:
            db.close()
    else:
        logger.info(f"ℹ️ No valid Solana CA found in pinned message from '{log_group_name}'")
        await send_dm_to_owner(f"ℹ️ **No Solana CA Found**\n\nGroup: `{log_group_name}`\nNo valid contract address found in the pinned message.")
# --- Helper Functions ---
async def get_group_info(group_id):
    """Get group information including name"""
    try:
        # Convert to absolute value if negative
        actual_group_id = -abs(group_id) if group_id > 0 else group_id
        
        # Get group entity
        group_entity = await client.get_entity(actual_group_id)
        
        # Safely get participants count
        participants_count = getattr(group_entity, 'participants_count', None)
        if participants_count is None:
            participants_count = 0
        
        group_info = {
            'id': actual_group_id,
            'title': getattr(group_entity, 'title', 'Unknown Group'),
            'username': getattr(group_entity, 'username', None),
            'participants_count': participants_count
        }
        
        return group_info
        
    except Exception as e:
        logger.error(f"❌ Error getting group info for {group_id}: {e}")
        return {
            'id': group_id,
            'title': 'Unknown Group',
            'username': None,
            'participants_count': 0
        }
# --- Main Function ---
async def main():
    """Main function"""
    try:
        logger.info("🚀 Starting Solana Trading Bot...")
        
        # Test Jupiter API first
        jupiter_working = await test_jupiter_api()
        if not jupiter_working:
            logger.warning("⚠️ Jupiter API test failed, but continuing...")
        
        # Initialize database
        init_db()
        logger.info("✅ Database initialized")
        
        # Initialize Solana service
        try:
            solana_service.init_solana_config_from_env()
            logger.info("✅ Solana service initialized")
        except Exception as e:
            logger.warning(f"⚠️ Solana service initialization had issues: {e}")
            logger.info("🔄 Continuing in monitoring mode...")
        
        # Test Solana service
        logger.info("🧪 Testing Solana service...")
        solana_test_success = await debug_solana_service()
        
        if not solana_test_success:
            logger.warning("⚠️ Solana service test failed")
        
        # Start the client
        await client.start()
        logger.info("✅ Telegram client started")
        
        # Get me info
        me = await client.get_me()
        logger.info(f"👤 Logged in as: {me.first_name} (@{me.username})")
        
        # Get group information
        logger.info("🔍 Getting group information...")
        group_info = await get_group_info(GROUP_ID)
        
        logger.info("🎯 Bot is running and monitoring...")
        logger.info(f"📺 Monitoring group: {group_info['title']} (ID: {group_info['id']})")
        
        # Show additional group info if available - with safe checking
        if group_info.get('username'):
            logger.info(f"🔗 Group username: @{group_info['username']}")
        
        # Safe participants count check
        participants_count = group_info.get('participants_count', 0)
        if participants_count and participants_count > 0:
            logger.info(f"👥 Participants: {participants_count}")
        else:
            logger.info("👥 Participants: Unknown/Private")
        
        # Send startup notification to owner
        startup_message = (
            f"🚀 **Bot Started Successfully!**\n\n"
            f"📺 Monitoring: `{group_info['title']}`\n"
            f"🆔 Group ID: `{group_info['id']}`\n"
            f"👤 Bot Account: `{me.first_name}`\n"
            f"📊 Max Trades: `{MAX_PURCHASES_ALLOWED}`\n"
            f"💰 Buy Amount: `{AMOUNT_TO_BUY_SOL} SOL`\n"
            f"📈 Take Profit: `{TAKE_PROFIT_PERCENT*100:.1f}%`\n"
            f"🛑 Stop Loss: `{STOP_LOSS_PERCENT*100:.1f}%`\n"
            f"🚀 **Pump.fun Ready!**"
        )
        
        # Add optional info to startup message
        if group_info.get('username'):
            startup_message += f"\n🔗 Group: @{group_info['username']}"
        
        if participants_count and participants_count > 0:
            startup_message += f"\n👥 Members: {participants_count}"
            
        await send_dm_to_owner(startup_message)
        
        # Start background tasks
        background_task = asyncio.create_task(background_tasks())
        
        # Keep the client running
        try:
            await client.run_until_disconnected()
        finally:
            background_task.cancel()
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    asyncio.run(main())