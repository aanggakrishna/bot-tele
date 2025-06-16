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

# --- Multiple Sources Support ---
def parse_sources(env_var):
    """Parse comma-separated sources from environment variable"""
    sources_str = os.getenv(env_var, '')
    if not sources_str:
        return []
    
    sources = []
    for source in sources_str.split(','):
        source = source.strip()
        if source:
            try:
                # Convert to int (can be positive or negative)
                source_id = int(source)
                sources.append(source_id)
            except ValueError:
                logger.warning(f"⚠️ Invalid source ID: {source}")
    
    return sources

# Support for multiple groups and channels
MONITOR_GROUPS = parse_sources('MONITOR_GROUPS')  # Comma-separated group IDs
MONITOR_CHANNELS = parse_sources('MONITOR_CHANNELS')  # Comma-separated channel IDs

# Legacy support - if old GROUP_ID exists, add it to groups
if os.getenv('GROUP_ID'):
    legacy_group_id = int(os.getenv('GROUP_ID'))
    if legacy_group_id not in MONITOR_GROUPS:
        MONITOR_GROUPS.append(legacy_group_id)

# Combine all sources
ALL_MONITOR_SOURCES = MONITOR_GROUPS + MONITOR_CHANNELS

if not ALL_MONITOR_SOURCES:
    logger.error("❌ No monitoring sources configured! Please set MONITOR_GROUPS and/or MONITOR_CHANNELS in .env")
    exit(1)

logger.info(f"📺 Configured to monitor {len(MONITOR_GROUPS)} group(s) and {len(MONITOR_CHANNELS)} channel(s)")

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
client = TelegramClient('solana_bot_multi', API_ID, API_HASH)

# --- Helper Functions ---
async def get_source_info(source_id):
    """Get source information (group or channel)"""
    try:
        # Convert to absolute value if needed
        actual_source_id = -abs(source_id) if source_id > 0 else source_id
        
        # Get entity
        source_entity = await client.get_entity(actual_source_id)
        
        # Determine source type
        source_type = "Unknown"
        if hasattr(source_entity, 'megagroup') and source_entity.megagroup:
            source_type = "Supergroup"
        elif hasattr(source_entity, 'broadcast') and source_entity.broadcast:
            source_type = "Channel"
        elif hasattr(source_entity, 'chat'):
            source_type = "Group"
        
        # Safely get participants count
        participants_count = getattr(source_entity, 'participants_count', None)
        if participants_count is None:
            participants_count = 0
        
        source_info = {
            'id': actual_source_id,
            'title': getattr(source_entity, 'title', 'Unknown'),
            'username': getattr(source_entity, 'username', None),
            'participants_count': participants_count,
            'type': source_type
        }
        
        return source_info
        
    except Exception as e:
        logger.error(f"❌ Error getting source info for {source_id}: {e}")
        return {
            'id': source_id,
            'title': 'Unknown',
            'username': None,
            'participants_count': 0,
            'type': 'Error'
        }

async def get_all_sources_info():
    """Get information for all monitored sources"""
    all_sources_info = []
    
    for source_id in ALL_MONITOR_SOURCES:
        source_info = await get_source_info(source_id)
        all_sources_info.append(source_info)
        
    return all_sources_info

async def send_dm_to_owner(message):
    """Send direct message to bot owner"""
    try:
        await client.send_message(OWNER_ID, message, parse_mode='markdown')
        logger.info(f"📱 Sent DM to owner: {message[:100]}...")
    except Exception as e:
        logger.error(f"❌ Error sending DM to owner: {e}")

# ... keep all other helper functions (test_jupiter_api, debug_solana_service) ...

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

# --- Background Task Functions ---
async def dm_heartbeat():
    """Send heartbeat DM to owner"""
    db = next(get_db())
    try:
        active_count = get_total_active_trades_count(db)
        
        # Get fresh sources info for heartbeat
        sources_info = await get_all_sources_info()
        
        heartbeat_message = (
            f"💓 **Bot Heartbeat**\n\n"
            f"Status: `Online`\n"
            f"📊 Active trades: `{active_count}/{MAX_PURCHASES_ALLOWED}`\n"
            f"⏰ Time: `{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC`\n\n"
            f"📺 **Monitoring Sources:**\n"
        )
        
        for source_info in sources_info:
            source_emoji = {
                'Channel': '📢',
                'Supergroup': '👥',
                'Group': '👥',
                'Unknown': '❓'
            }.get(source_info['type'], '📺')
            
            heartbeat_message += f"{source_emoji} `{source_info['title']}` ({source_info['type']})\n"
        
        await send_dm_to_owner(heartbeat_message)
        logger.info(f"📱 Sent DM Heartbeat for {len(sources_info)} sources")
    except Exception as e:
        logger.error(f"❌ Error in DM heartbeat: {e}")
    finally:
        db.close()

# ... keep all other background task functions (monitor_trades_and_sell, background_tasks) ...

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

@client.on(events.NewMessage)
async def new_message_handler(event):
    """Handle new messages in monitored channels (not groups)"""
    
    # Only process if it has chat_id
    if not hasattr(event, 'chat_id'):
        return
    
    # Get basic info for logging
    log_chat_id = event.chat_id
    log_source_name = "Unknown Channel"
    log_source_type = "Unknown"
    is_monitored_channel = False
    
    try:
        chat_entity = await event.get_chat()
        if chat_entity and hasattr(chat_entity, 'title'):
            log_source_name = chat_entity.title
            
            # Only process CHANNELS (not groups) for new messages
            if hasattr(chat_entity, 'broadcast') and chat_entity.broadcast:
                log_source_type = "Channel"
                # Check if it's in our monitored channels
                actual_chat_id = -abs(event.chat_id) if event.chat_id > 0 else event.chat_id
                if actual_chat_id in MONITOR_CHANNELS:
                    is_monitored_channel = True
    except Exception as e:
        logger.debug(f"Error getting chat info: {e}")
        return

    # Skip if not a monitored channel
    if not is_monitored_channel:
        return

    # Skip if message is too old (more than 2 minutes to avoid processing old messages)
    if hasattr(event.message, 'date'):
        from datetime import datetime, timezone
        message_age = (datetime.now(timezone.utc) - event.message.date).total_seconds()
        if message_age > 120:  # 2 minutes
            logger.debug(f"⏭️ Skipping old message from {log_source_name} (age: {message_age:.0f}s)")
            return

    # Get message text
    message_text = None
    if hasattr(event.message, 'message') and event.message.message:
        message_text = event.message.message
    elif hasattr(event.message, 'text') and event.message.text:
        message_text = event.message.text
    
    if not message_text:
        logger.debug(f"⏭️ No text content in message from {log_source_name}")
        return

    logger.info(f"📢 New message from channel '{log_source_name}': {message_text[:100]}...")
    
    # Send notification to owner
    await send_dm_to_owner(f"📢 **New Channel Message**\n\n📢 Channel: `{log_source_name}`\nContent: `{message_text[:200]}...`")

    # Extract Solana CA using enhanced detection
    ca = extract_solana_ca_enhanced(message_text)
    if ca:
        logger.info(f"🪙 Detected potential Solana CA from channel '{log_source_name}': {ca}")
        await send_dm_to_owner(f"🔍 **Solana CA Detected**\n\n📢 Channel: `{log_source_name}`\nToken: `{ca}`\nProcessing purchase...")

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
            logger.info(f"🚀 Attempting to buy token from channel: {ca}")
            await send_dm_to_owner(f"🔄 **Starting Purchase**\n\nToken: `{ca}`\nAmount: `{AMOUNT_TO_BUY_SOL} SOL`\nSource: 📢 `{log_source_name}`")
            
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
                    f"📍 Source: 📢 `{log_source_name}`\n"
                    f"🔗 [View Transaction]({explorer_url})\n"
                    f"📊 Active Trades: `{get_total_active_trades_count(db)}/{MAX_PURCHASES_ALLOWED}`"
                )
                logger.info(f"✅ Successfully bought {ca} from {buy_result.get('platform', 'unknown')}. Source: {log_source_name}")
            else:
                await send_dm_to_owner(
                    f"❌ **Purchase Failed**\n\n"
                    f"Token: `{ca}`\n"
                    f"Source: 📢 `{log_source_name}`\n"
                    f"Check bot logs for details."
                )
                logger.error(f"❌ Failed to buy token: {ca}")
                
        except Exception as e:
            logger.error(f"❌ Error in buy process: {e}", exc_info=True)
            await send_dm_to_owner(f"🚨 **Error in Purchase Process**\n\nToken: `{ca}`\nSource: 📢 `{log_source_name}`\nError: `{str(e)[:200]}`")
        finally:
            db.close()
    else:
        logger.debug(f"ℹ️ No valid Solana CA found in channel message from '{log_source_name}'")

# --- Enhanced Telegram Event Handler for Multiple Sources ---
@client.on(events.ChatAction)
async def pinned_message_handler(event):
    """Handle pinned message events in target sources (groups and channels)"""
    
    # Event logging variables
    is_target_pin_event = False
    log_chat_id = "N/A"
    log_event_description = "Unknown ChatAction"
    log_content_preview = "N/A"
    log_source_name = "Unknown Source"
    log_source_type = "Unknown"

    if hasattr(event, 'chat_id'):
        log_chat_id = event.chat_id
        try:
            chat_entity_for_log = await event.get_chat()
            if chat_entity_for_log and hasattr(chat_entity_for_log, 'title'):
                log_source_name = chat_entity_for_log.title
                
                # Determine source type
                if hasattr(chat_entity_for_log, 'megagroup') and chat_entity_for_log.megagroup:
                    log_source_type = "Supergroup"
                elif hasattr(chat_entity_for_log, 'broadcast') and chat_entity_for_log.broadcast:
                    log_source_type = "Channel"
                else:
                    log_source_type = "Group"
        except Exception:
            pass

    # Check if this is a pin event in any of our target sources
    if hasattr(event, 'new_pin') and event.new_pin:
        log_event_description = "Pin Action"
        if hasattr(event, 'action_message') and event.action_message and hasattr(event.action_message, 'message'):
            log_content_preview = str(event.action_message.message)[:100]
        
        # Check if it's any of our monitored sources
        if hasattr(event, 'chat_id'):
            actual_chat_id = -abs(event.chat_id) if event.chat_id > 0 else event.chat_id
            if actual_chat_id in ALL_MONITOR_SOURCES:
                is_target_pin_event = True

    # Enhanced logging with source info
    logger.debug(f"📝 Processing event - {log_source_type}: '{log_source_name}' (ID: {log_chat_id}), Event Type: {log_event_description}")

    if not is_target_pin_event:
        logger.debug(f"⏭️ Skipping event: Not a pin action in monitored sources")
        return

    logger.info(f"📌 Pin event detected in {log_source_type}: '{log_source_name}' (ID: {log_chat_id})")

    # --- Get Pinned Message Content (Same logic as before but with enhanced logging) ---
    message_text = None
    
    # Method 1: Try to get from event.pinned_message
    if hasattr(event, 'pinned_message') and event.pinned_message:
        actual_pinned_message_object = event.pinned_message
        
        if hasattr(actual_pinned_message_object, 'message') and actual_pinned_message_object.message:
            message_text = actual_pinned_message_object.message
            logger.info("✅ Retrieved pinned message from event.pinned_message")
        elif hasattr(actual_pinned_message_object, 'text') and actual_pinned_message_object.text:
            message_text = actual_pinned_message_object.text
            logger.info("✅ Retrieved pinned message from event.pinned_message (text)")
    
    # Method 2: Fallback - get recent pinned messages (PRIORITIZED)
    if not message_text:
        logger.info(f"🔍 Fetching recent messages from {log_source_type}: {log_source_name}...")
        
        try:
            recent_messages = await client.get_messages(log_chat_id, limit=100)
            
            for msg in recent_messages:
                if hasattr(msg, 'pinned') and msg.pinned:
                    if hasattr(msg, 'message') and msg.message:
                        message_text = msg.message
                        logger.info(f"✅ Found pinned message in recent messages from {log_source_type}")
                        break
                    elif hasattr(msg, 'text') and msg.text:
                        message_text = msg.text
                        logger.info(f"✅ Found pinned message in recent messages from {log_source_type}")
                        break
                        
        except Exception as e:
            logger.error(f"❌ Error fetching recent pinned messages from {log_source_type}: {e}")
    
    # Method 3: Manual fetch via chat info (as backup)
    if not message_text:
        logger.warning(f"⚠️ Trying manual fetch from {log_source_type} info for {log_chat_id}")
        
        try:
            chat_entity = await client.get_entity(log_chat_id)
            
            # Handle different chat types
            if hasattr(chat_entity, 'megagroup') or hasattr(chat_entity, 'broadcast'):
                # It's a channel (supergroup or broadcast)
                full_chat_info = await client(GetFullChannelRequest(chat_entity))
                pinned_msg_id = getattr(full_chat_info.full_chat, 'pinned_msg_id', None)
            else:
                # It's a regular group
                full_chat_info = await client(GetFullChatRequest(chat_entity.id))
                pinned_msg_id = getattr(full_chat_info.full_chat, 'pinned_msg_id', None)
            
            if pinned_msg_id:
                logger.info(f"🔍 Found pinned message ID: {pinned_msg_id}")
                
                pinned_messages = await client.get_messages(log_chat_id, ids=[pinned_msg_id])
                if pinned_messages and len(pinned_messages) > 0:
                    pinned_msg = pinned_messages[0]
                    if hasattr(pinned_msg, 'message') and pinned_msg.message:
                        message_text = pinned_msg.message
                        logger.info(f"✅ Retrieved pinned message via manual fetch from {log_source_type}")
                    elif hasattr(pinned_msg, 'text') and pinned_msg.text:
                        message_text = pinned_msg.text
                        logger.info(f"✅ Retrieved pinned message via manual fetch from {log_source_type}")
            
        except Exception as e:
            logger.error(f"❌ Error in manual fetch from {log_source_type}: {e}")
    
    # Final check
    if not message_text:
        logger.error(f"❌ FAILED to retrieve pinned message text from {log_source_type}: {log_source_name}")
        await send_dm_to_owner(f"⚠️ **Pin Event Detected**\n\n{log_source_type}: `{log_source_name}`\n❌ Could not retrieve message content. Please check manually.")
        return

    # Continue with normal logic
    logger.info(f"📄 New Pinned Message detected from {log_source_type}: {message_text[:200]}...")
    
    source_emoji = {
        'Channel': '📢',
        'Supergroup': '👥',
        'Group': '👥'
    }.get(log_source_type, '📺')
    
    await send_dm_to_owner(f"📌 **New Pinned Message**\n\n{source_emoji} {log_source_type}: `{log_source_name}`\nContent: `{message_text[:200]}...`")

    # Extract Solana CA using enhanced detection
    ca = extract_solana_ca_enhanced(message_text)
    if ca:
        logger.info(f"🪙 Detected potential Solana CA from {log_source_type} '{log_source_name}': {ca}")
        await send_dm_to_owner(f"🔍 **Solana CA Detected**\n\n{source_emoji} {log_source_type}: `{log_source_name}`\nToken: `{ca}`\nProcessing purchase...")

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
            await send_dm_to_owner(f"🔄 **Starting Purchase**\n\nToken: `{ca}`\nAmount: `{AMOUNT_TO_BUY_SOL} SOL`\nSource: {source_emoji} `{log_source_name}`")
            
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
                    f"📍 Source: {source_emoji} `{log_source_name}`\n"
                    f"🔗 [View Transaction]({explorer_url})\n"
                    f"📊 Active Trades: `{get_total_active_trades_count(db)}/{MAX_PURCHASES_ALLOWED}`"
                )
                logger.info(f"✅ Successfully bought {ca} from {buy_result.get('platform', 'unknown')}. Source: {log_source_name}")
            else:
                await send_dm_to_owner(
                    f"❌ **Purchase Failed**\n\n"
                    f"Token: `{ca}`\n"
                    f"Source: {source_emoji} `{log_source_name}`\n"
                    f"Check bot logs for details."
                )
                logger.error(f"❌ Failed to buy token: {ca}")
                
        except Exception as e:
            logger.error(f"❌ Error in buy process: {e}", exc_info=True)
            await send_dm_to_owner(f"🚨 **Error in Purchase Process**\n\nToken: `{ca}`\nSource: {source_emoji} `{log_source_name}`\nError: `{str(e)[:200]}`")
        finally:
            db.close()
    else:
        logger.info(f"ℹ️ No valid Solana CA found in pinned message from {log_source_type}: '{log_source_name}'")
        await send_dm_to_owner(f"ℹ️ **No Solana CA Found**\n\n{source_emoji} {log_source_type}: `{log_source_name}`\nNo valid contract address found in the pinned message.")

# --- Main Function ---
async def main():
    """Main function"""
    try:
        logger.info("🚀 Starting Solana Multi-Source Trading Bot...")
        
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
        
        # Get all sources information
        logger.info("🔍 Getting sources information...")
        sources_info = await get_all_sources_info()
        
        logger.info("🎯 Bot is running and monitoring...")
        logger.info(f"📺 Monitoring {len(sources_info)} sources:")
        
        for source_info in sources_info:
            source_emoji = {
                'Channel': '📢',
                'Supergroup': '👥',
                'Group': '👥',
                'Unknown': '❓'
            }.get(source_info['type'], '📺')
            
            logger.info(f"  {source_emoji} {source_info['type']}: {source_info['title']} (ID: {source_info['id']})")
            
            if source_info.get('username'):
                logger.info(f"    🔗 @{source_info['username']}")
            
            participants_count = source_info.get('participants_count', 0)
            if participants_count and participants_count > 0:
                logger.info(f"    👥 {participants_count} members")
        
        # Send startup notification to owner
        startup_message = (
            f"🚀 **Multi-Source Bot Started!**\n\n"
            f"👤 Bot Account: `{me.first_name}`\n"
            f"📊 Max Trades: `{MAX_PURCHASES_ALLOWED}`\n"
            f"💰 Buy Amount: `{AMOUNT_TO_BUY_SOL} SOL`\n"
            f"📈 Take Profit: `{TAKE_PROFIT_PERCENT*100:.1f}%`\n"
            f"🛑 Stop Loss: `{STOP_LOSS_PERCENT*100:.1f}%`\n\n"
            f"📺 **Monitoring {len(sources_info)} Sources:**\n"
        )
        
        for source_info in sources_info:
            source_emoji = {
                'Channel': '📢',
                'Supergroup': '👥',
                'Group': '👥'
            }.get(source_info['type'], '📺')
            
            startup_message += f"{source_emoji} `{source_info['title']}`"
            if source_info.get('username'):
                startup_message += f" (@{source_info['username']})"
            startup_message += "\n"
        
        startup_message += f"\n🚀 **Pump.fun Ready!**"
            
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