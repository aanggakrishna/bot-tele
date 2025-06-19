import asyncio
import re
from datetime import datetime, timedelta
from typing import List
from loguru import logger
from telethon import TelegramClient, events
from telethon.tl.types import UpdatePinnedMessages

from config import config
from database import init_db, get_db, save_signal, save_trade, get_active_trades, update_trade_status, get_trade_stats
from solana_service import trader
from utils import extract_solana_addresses, detect_platform, format_pnl, truncate_address

# Initialize Telegram client
client = TelegramClient('trading_bot', config.API_ID, config.API_HASH)

class TradingBot:
    def __init__(self):
        self.heartbeat_count = 0
        
    async def start(self):
        """Start the trading bot"""
        logger.info("🚀 Starting Solana Trading Bot...")
        
        # Validate configuration
        if not config.validate():
            logger.error("❌ Configuration validation failed!")
            return
        
        # Initialize database
        init_db()
        
        # Initialize Solana trader
        success = trader.init_from_config()
        if not success:
            logger.error("❌ Failed to initialize Solana trader!")
            return
        
        # Show wallet info
        if trader.keypair:
            balance = await trader.get_wallet_balance()
            logger.info(f"💎 Wallet: {trader.keypair.pubkey()}")
            logger.info(f"💰 Balance: {balance:.6f} SOL")
            
            if trader.enable_real_trading:
                logger.warning("🔴 REAL TRADING ENABLED - MONEY AT RISK!")
            else:
                logger.info("🟡 MOCK TRADING MODE")
        
        # Start Telegram client
        await client.start()
        logger.info("📱 Telegram client connected")
        
        # Setup handlers
        self.setup_handlers()
        
        # Start background tasks
        asyncio.create_task(self.heartbeat())
        asyncio.create_task(self.monitor_trades())
        
        logger.info("✅ Bot is running and monitoring...")
        logger.info(f"👁️ Monitoring Groups: {config.MONITOR_GROUPS}")
        logger.info(f"👁️ Monitoring Channels: {config.MONITOR_CHANNELS}")
        
        # Run until disconnected
        await client.run_until_disconnected()
    
    def setup_handlers(self):
        """Setup Telegram event handlers"""
        
        # Handle new messages in monitored channels
        @client.on(events.NewMessage(chats=config.MONITOR_CHANNELS))
        async def handle_channel_message(event):
            try:
                await self.process_message(event, 'channel')
            except Exception as e:
                logger.error(f"❌ Channel message handler error: {e}")
        
        # Handle pinned messages in monitored groups (using Raw updates)
        @client.on(events.Raw)
        async def handle_raw_updates(event):
            try:
                if isinstance(event, UpdatePinnedMessages):
                    # Get the pinned message
                    chat_id = getattr(event, 'peer', None)
                    if chat_id and hasattr(chat_id, 'channel_id'):
                        full_chat_id = -int(f"100{chat_id.channel_id}")
                        if full_chat_id in config.MONITOR_GROUPS:
                            # Get the actual message
                            messages = await client.get_messages(full_chat_id, ids=event.messages)
                            for message in messages:
                                if message:
                                    await self.process_message_content(message.message or "", 'pin', full_chat_id)
            except Exception as e:
                logger.error(f"❌ Pin handler error: {e}")
        
        # Owner commands
        @client.on(events.NewMessage(pattern='/status', chats=[config.OWNER_ID]))
        async def handle_status(event):
            await self.send_status_report(event)
        
        @client.on(events.NewMessage(pattern='/balance', chats=[config.OWNER_ID]))
        async def handle_balance(event):
            balance = await trader.get_wallet_balance()
            await event.reply(f"💰 **Wallet Balance**: {balance:.6f} SOL")
        
        @client.on(events.NewMessage(pattern='/trades', chats=[config.OWNER_ID]))
        async def handle_trades(event):
            await self.send_active_trades(event)
        
        @client.on(events.NewMessage(pattern='/stats', chats=[config.OWNER_ID]))
        async def handle_stats(event):
            await self.send_trading_stats(event)
        
        logger.info("✅ Event handlers registered")
    
    async def process_message(self, event, source_type: str):
        """Process incoming message"""
        try:
            message_text = event.raw_text
            if not message_text or len(message_text) < 20:
                return
            
            chat_id = event.chat_id
            await self.process_message_content(message_text, source_type, chat_id)
            
        except Exception as e:
            logger.error(f"❌ Process message error: {e}")
    
    async def process_message_content(self, message_text: str, source_type: str, source_id: int):
        """Process message content for CA detection"""
        try:
            logger.debug(f"📨 {source_type.upper()}: {message_text[:100]}...")
            
            # Extract Solana addresses
            addresses = extract_solana_addresses(message_text)
            if not addresses:
                return
            
            # Detect platform
            platform = detect_platform(message_text)
            
            # Process each valid address
            for address in addresses:
                if trader.is_valid_solana_address(address):
                    # Check if it's not a common token (SOL, USDC, etc.)
                    if self.is_excluded_address(address):
                        continue
                    
                    logger.info(f"🎯 CA DETECTED: {truncate_address(address)} on {platform.upper()}")
                    
                    # Save signal to database
                    with get_db() as db:
                        save_signal(db, address, platform, source_type, source_id, message_text)
                    
                    # Send notification to owner
                    await self.notify_ca_detected(address, platform, source_type, message_text)
                    
                    # Process buy signal
                    await self.process_buy_signal(address, platform, message_text)
            
        except Exception as e:
            logger.error(f"❌ Process message content error: {e}")
    
    def is_excluded_address(self, address: str) -> bool:
        """Check if address should be excluded"""
        excluded = [
            'So11111111111111111111111111111111111111112',  # SOL
            'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',  # USDT
        ]
        return address in excluded
    
    async def notify_ca_detected(self, token_mint: str, platform: str, source_type: str, message_text: str):
        """Send CA detected notification to owner"""
        try:
            notification = f"""
🎯 **CA DETECTED**

🪙 **Token**: `{token_mint}`
🏷️ **Platform**: {platform.upper()}
📍 **Source**: {source_type.upper()}
💰 **Price**: Checking...

📝 **Message**:
{message_text[:300]}...
"""
            
            await client.send_message(config.OWNER_ID, notification)
            logger.info(f"📤 CA notification sent to owner")
            
        except Exception as e:
            logger.error(f"❌ CA notification error: {e}")
    
    async def process_buy_signal(self, token_mint: str, platform: str, message_text: str):
        """Process buy signal for detected CA"""
        try:
            logger.info(f"🔄 Processing buy signal: {truncate_address(token_mint)}")
            
            # Check current active trades
            with get_db() as db:
                active_trades = get_active_trades(db)
            
            # Check if already have this token
            for trade in active_trades:
                if trade.token_mint_address == token_mint:
                    logger.info(f"⚠️ Already have active trade for {truncate_address(token_mint)}")
                    return
            
            # Check max purchases limit (2 sessions)
            if len(active_trades) >= config.MAX_PURCHASES_ALLOWED:
                logger.warning(f"⚠️ Max purchases limit reached ({config.MAX_PURCHASES_ALLOWED})")
                await self.notify_max_limit_reached(token_mint)
                return
            
            # Get token price
            current_price = await trader.get_token_price_sol(token_mint)
            if not current_price:
                logger.error(f"❌ Could not get price for {truncate_address(token_mint)}")
                return
            
            logger.info(f"💰 Token price: {current_price:.12f} SOL")
            
            # Execute buy
            logger.warning(f"🔴 EXECUTING BUY: {truncate_address(token_mint)}")
            buy_result = await trader.buy_token(token_mint)
            
            if not buy_result:
                logger.error(f"❌ Buy failed for {truncate_address(token_mint)}")
                await self.notify_buy_failed(token_mint, platform)
                return
            
            # Save trade to database
            with get_db() as db:
                trade_id = save_trade(
                    db=db,
                    token_mint_address=token_mint,
                    buy_price_sol=buy_result['buy_price_sol'],
                    amount_bought_token=buy_result['amount_bought_token'],
                    wallet_token_account=buy_result['wallet_token_account'],
                    buy_tx_signature=buy_result['buy_tx_signature'],
                    platform=platform
                )
            
            logger.info(f"✅ Trade saved with ID: {trade_id}")
            
            # Send buy notification
            await self.notify_buy_executed(buy_result, platform, message_text)
            
        except Exception as e:
            logger.error(f"❌ Buy signal processing error: {e}")
    
    async def notify_max_limit_reached(self, token_mint: str):
        """Notify when max purchase limit is reached"""
        try:
            notification = f"""
⚠️ **MAX PURCHASE LIMIT REACHED**

🔢 **Limit**: {config.MAX_PURCHASES_ALLOWED} active trades
🪙 **Skipped Token**: `{truncate_address(token_mint)}`

💡 **Action**: Wait for current trades to sell before new purchases.
"""
            await client.send_message(config.OWNER_ID, notification)
        except Exception as e:
            logger.error(f"❌ Max limit notification error: {e}")
    
    async def notify_buy_failed(self, token_mint: str, platform: str):
        """Notify when buy fails"""
        try:
            notification = f"""
❌ **BUY FAILED**

🪙 **Token**: `{truncate_address(token_mint)}`
🏷️ **Platform**: {platform.upper()}
⚠️ **Reason**: Check logs for details
"""
            await client.send_message(config.OWNER_ID, notification)
        except Exception as e:
            logger.error(f"❌ Buy failed notification error: {e}")
    
    async def notify_buy_executed(self, buy_result: dict, platform: str, original_message: str):
        """Notify when buy is executed"""
        try:
            is_real = not buy_result['buy_tx_signature'].startswith('mock_')
            status_emoji = "🔴" if is_real else "🟡"
            status_text = "REAL TRADE" if is_real else "MOCK TRADE"
            
            # Calculate total cost
            total_cost = buy_result['buy_price_sol'] * buy_result['amount_bought_token']
            
            # Explorer URL
            tx_signature = buy_result['buy_tx_signature']
            explorer_url = f"https://solscan.io/tx/{tx_signature}" if is_real else "N/A (Mock)"
            
            notification = f"""
{status_emoji} **{status_text} - BUY EXECUTED**

🪙 **Token**: `{truncate_address(buy_result['token_mint_address'])}`
🏷️ **Platform**: {platform.upper()}
💰 **Price**: {buy_result['buy_price_sol']:.12f} SOL
📊 **Amount**: {buy_result['amount_bought_token']:,.0f}
💵 **Total Cost**: {total_cost:.6f} SOL
🔗 **TX**: [View on Solscan]({explorer_url})

📝 **Original Signal**:
{original_message[:200]}...
"""
            
            await client.send_message(config.OWNER_ID, notification)
            logger.info(f"📤 Buy notification sent")
            
        except Exception as e:
            logger.error(f"❌ Buy notification error: {e}")
    
    async def monitor_trades(self):
        """Monitor active trades for sell conditions"""
        logger.info("👁️ Starting trade monitoring...")
        
        while True:
            try:
                with get_db() as db:
                    active_trades = get_active_trades(db)
                
                if not active_trades:
                    await asyncio.sleep(30)
                    continue
                
                logger.debug(f"📊 Monitoring {len(active_trades)} active trades")
                
                for trade in active_trades:
                    await self.check_sell_conditions(trade)
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"❌ Monitor trades error: {e}")
                await asyncio.sleep(30)
    
    async def check_sell_conditions(self, trade):
        """Check if trade should be sold"""
        try:
            # Get current price
            current_price = await trader.get_token_price_sol(trade.token_mint_address)
            if not current_price:
                return
            
            # Calculate P&L
            pnl_percent = (current_price - trade.buy_price_sol) / trade.buy_price_sol
            
            should_sell = False
            sell_reason = ""
            
            # Take profit check
            if pnl_percent >= config.TAKE_PROFIT_PERCENT:
                should_sell = True
                sell_reason = f"Take Profit ({config.TAKE_PROFIT_PERCENT*100:.0f}%)"
            
            # Stop loss check
            elif pnl_percent <= -config.STOP_LOSS_PERCENT:
                should_sell = True
                sell_reason = f"Stop Loss ({config.STOP_LOSS_PERCENT*100:.0f}%)"
            
            # Time-based sell (24 hours)
            elif trade.created_at and (datetime.utcnow() - trade.created_at) > timedelta(hours=24):
                if abs(pnl_percent) < 0.05:  # Less than 5% movement
                    should_sell = True
                    sell_reason = "Time-based (24h, <5% movement)"
            
            if should_sell:
                await self.execute_sell(trade, sell_reason, current_price, pnl_percent)
            
        except Exception as e:
            logger.error(f"❌ Check sell conditions error: {e}")
    
    async def execute_sell(self, trade, reason: str, current_price: float, pnl_percent: float):
        """Execute sell order"""
        try:
            logger.warning(f"🔴 EXECUTING SELL: {truncate_address(trade.token_mint_address)} - {reason}")
            
            # Execute sell
            sell_result = await trader.sell_token(
                trade.token_mint_address,
                trade.amount_bought_token,
                trade.wallet_token_account
            )
            
            if not sell_result:
                logger.error(f"❌ Sell failed for {truncate_address(trade.token_mint_address)}")
                return
            
            # Update database
            status = "sold_profit" if pnl_percent > 0 else "sold_loss"
            with get_db() as db:
                update_trade_status(
                    db, trade.id,
                    status=status,
                    sell_price_sol=sell_result['sell_price_sol'],
                    sell_tx_signature=sell_result['sell_tx_signature'],
                    pnl_percent=pnl_percent * 100
                )
            
            # Send notification
            await self.notify_sell_executed(trade, sell_result, reason, pnl_percent)
            
            logger.info(f"✅ Sell completed: {reason} - P&L: {pnl_percent*100:.2f}%")
            
        except Exception as e:
            logger.error(f"❌ Sell execution error: {e}")
    
    async def notify_sell_executed(self, trade, sell_result: dict, reason: str, pnl_percent: float):
        """Notify when sell is executed"""
        try:
            is_real = not sell_result['sell_tx_signature'].startswith('mock_')
            status_emoji = "🔴" if is_real else "🟡"
            pnl_formatted = format_pnl(pnl_percent * 100)
            
            # Explorer URL
            tx_signature = sell_result['sell_tx_signature']
            explorer_url = f"https://solscan.io/tx/{tx_signature}" if is_real else "N/A (Mock)"
            
            notification = f"""
{status_emoji} **SELL EXECUTED** {pnl_formatted}

🪙 **Token**: `{truncate_address(trade.token_mint_address)}`
🏷️ **Platform**: {trade.platform.upper()}
🎯 **Reason**: {reason}

💰 **Buy Price**: {trade.buy_price_sol:.12f} SOL
💰 **Sell Price**: {sell_result['sell_price_sol']:.12f} SOL
📊 **P&L**: {pnl_percent*100:.2f}%

🔗 **TX**: [View on Solscan]({explorer_url})
"""
            
            await client.send_message(config.OWNER_ID, notification)
            logger.info(f"📤 Sell notification sent")
            
        except Exception as e:
            logger.error(f"❌ Sell notification error: {e}")
    
    async def heartbeat(self):
        """Heartbeat to show bot is alive"""
        while True:
            try:
                self.heartbeat_count += 1
                logger.info(f"💓 Heartbeat #{self.heartbeat_count} - Bot is alive")
                
                # Show current status every 10 heartbeats
                if self.heartbeat_count % 10 == 0:
                    with get_db() as db:
                        active_trades = get_active_trades(db)
                    
                    balance = await trader.get_wallet_balance()
                    logger.info(f"📊 Status: {balance:.6f} SOL, {len(active_trades)} active trades")
                
                await asyncio.sleep(300)  # Every 5 minutes
                
            except Exception as e:
                logger.error(f"❌ Heartbeat error: {e}")
                await asyncio.sleep(300)
    
    async def send_status_report(self, event):
        """Send comprehensive status report"""
        try:
            with get_db() as db:
                active_trades = get_active_trades(db)
                stats = get_trade_stats(db)
            
            balance = await trader.get_wallet_balance()
            
            status = f"""
📊 **BOT STATUS REPORT**

💎 **Wallet**: {truncate_address(str(trader.keypair.pubkey())) if trader.keypair else 'Not loaded'}
💰 **Balance**: {balance:.6f} SOL
🔴 **Real Trading**: {'ON' if trader.enable_real_trading else 'OFF'}
📈 **Active Trades**: {len(active_trades)}/{config.MAX_PURCHASES_ALLOWED}

📊 **Trading Stats**:
• Total Trades: {stats.get('total_trades', 0)}
• Profitable: {stats.get('profitable_trades', 0)}
• Losses: {stats.get('loss_trades', 0)}
• Win Rate: {stats.get('win_rate', 0):.1f}%
• Avg P&L: {stats.get('avg_pnl', 0):.2f}%

🎯 **Settings**:
• Buy Amount: {config.AMOUNT_TO_BUY_SOL} SOL
• Take Profit: {config.TAKE_PROFIT_PERCENT*100:.0f}%
• Stop Loss: {config.STOP_LOSS_PERCENT*100:.0f}%
• Slippage: {config.SLIPPAGE_BPS/100:.1f}%

🏷️ **Monitoring**:
• Groups: {len(config.MONITOR_GROUPS)}
• Channels: {len(config.MONITOR_CHANNELS)}
"""
            
            await event.reply(status)
            
        except Exception as e:
            logger.error(f"❌ Status report error: {e}")
            await event.reply(f"❌ Error: {e}")
    
    async def send_active_trades(self, event):
        """Send active trades list"""
        try:
            with get_db() as db:
                active_trades = get_active_trades(db)
            
            if not active_trades:
                await event.reply("📊 No active trades")
                return
            
            trades_text = "📊 **ACTIVE TRADES**:\n\n"
            
            for i, trade in enumerate(active_trades[:5], 1):
                current_price = await trader.get_token_price_sol(trade.token_mint_address)
                if current_price:
                    pnl = (current_price - trade.buy_price_sol) / trade.buy_price_sol * 100
                    pnl_formatted = format_pnl(pnl)
                else:
                    pnl_formatted = "❓ Unknown"
                
                trades_text += f"""
{i}. **{trade.platform.upper()}**
🪙 `{truncate_address(trade.token_mint_address)}`
💰 Buy: {trade.buy_price_sol:.8f} SOL
{pnl_formatted}
"""
            
            await event.reply(trades_text)
            
        except Exception as e:
            logger.error(f"❌ Active trades error: {e}")
            await event.reply(f"❌ Error: {e}")
    
    async def send_trading_stats(self, event):
        """Send trading statistics"""
        try:
            with get_db() as db:
                stats = get_trade_stats(db)
            
            stats_text = f"""
📊 **TRADING STATISTICS**

📈 **Performance**:
• Total Trades: {stats.get('total_trades', 0)}
• Active: {stats.get('active_trades', 0)}
• Profitable: {stats.get('profitable_trades', 0)}
• Losses: {stats.get('loss_trades', 0)}
• Win Rate: {stats.get('win_rate', 0):.1f}%
• Average P&L: {stats.get('avg_pnl', 0):.2f}%

💰 **Settings**:
• Buy Amount: {config.AMOUNT_TO_BUY_SOL} SOL
• Max Active: {config.MAX_PURCHASES_ALLOWED}
• Take Profit: {config.TAKE_PROFIT_PERCENT*100:.0f}%
• Stop Loss: {config.STOP_LOSS_PERCENT*100:.0f}%
"""
            
            await event.reply(stats_text)
            
        except Exception as e:
            logger.error(f"❌ Stats error: {e}")
            await event.reply(f"❌ Error: {e}")

# Main function
async def main():
    bot = TradingBot()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())