import asyncio
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional
from loguru import logger
from telethon import TelegramClient, events
from dotenv import load_dotenv

# Import our services
from solana_service import (
    init_real_trading, buy_token_solana, sell_token_solana, 
    get_token_price_sol, is_valid_solana_address, real_trader
)
from database import (
    init_db, get_db, save_trade, get_active_trades, 
    update_trade_status, get_trade_by_id
)

load_dotenv()

# Telegram client
client = TelegramClient(
    'trading_bot',
    int(os.getenv('API_ID')),
    os.getenv('API_HASH')
)

# Configuration
OWNER_ID = int(os.getenv('OWNER_ID'))
MONITOR_GROUPS = [int(x.strip()) for x in os.getenv('MONITOR_GROUPS', '').split(',') if x.strip()]
MONITOR_CHANNELS = [int(x.strip()) for x in os.getenv('MONITOR_CHANNELS', '').split(',') if x.strip()]
MAX_PURCHASES = int(os.getenv('MAX_PURCHASES_ALLOWED', '3'))

class RealTradingBot:
    def __init__(self):
        self.active_trades = {}
        self.price_cache = {}
        
    async def start(self):
        """Start the real trading bot"""
        logger.info("🚀 Starting Real Trading Bot...")
        
        # Initialize database
        init_db()
        
        # Initialize real trading
        success = await init_real_trading()
        if not success:
            logger.error("❌ Failed to initialize real trading!")
            return
        
        # Show wallet info
        if real_trader.keypair:
            balance = await real_trader.get_wallet_balance()
            logger.info(f"💎 Wallet: {real_trader.keypair.pubkey()}")
            logger.info(f"💰 Balance: {balance:.6f} SOL")
            
            if real_trader.enable_real_trading:
                logger.warning("🔴 REAL TRADING ENABLED - MONEY AT RISK!")
            else:
                logger.info("🟡 MOCK TRADING MODE")
        
        # Start Telegram client
        await client.start()
        logger.info("📱 Telegram client started")
        
        # Start monitoring task
        asyncio.create_task(self.monitor_trades())
        
        # Setup message handlers
        self.setup_handlers()
        
        logger.info("✅ Bot is running and monitoring...")
        await client.run_until_disconnected()
    
    def setup_handlers(self):
        """Setup Telegram message handlers"""
        
        @client.on(events.NewMessage(chats=MONITOR_GROUPS + MONITOR_CHANNELS))
        async def handle_message(event):
            try:
                message_text = event.raw_text
                if not message_text:
                    return
                
                logger.debug(f"📨 New message: {message_text[:100]}...")
                
                # Detect token addresses
                tokens = self.extract_token_addresses(message_text)
                if not tokens:
                    return
                
                # Detect platform
                platform = self.detect_platform(message_text)
                
                # Process each token
                for token in tokens:
                    if is_valid_solana_address(token):
                        logger.info(f"🎯 Token detected: {token} on {platform}")
                        await self.process_buy_signal(token, platform, message_text)
                
            except Exception as e:
                logger.error(f"❌ Message handler error: {e}")
        
        @client.on(events.NewMessage(pattern='/status', chats=[OWNER_ID]))
        async def handle_status(event):
            await self.send_status_report(event)
        
        @client.on(events.NewMessage(pattern='/balance', chats=[OWNER_ID]))
        async def handle_balance(event):
            balance = await real_trader.get_wallet_balance()
            await event.reply(f"💰 Wallet Balance: {balance:.6f} SOL")
        
        @client.on(events.NewMessage(pattern='/trades', chats=[OWNER_ID]))
        async def handle_trades(event):
            await self.send_active_trades(event)
    
    def extract_token_addresses(self, text: str) -> List[str]:
        """Extract Solana token addresses from text"""
        # Multiple patterns for token detection
        patterns = [
            r'[A-Za-z0-9]{40,50}',  # General base58 pattern
            r'[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{44}',  # Specific base58
            r'Address:\s*([A-Za-z0-9]{40,50})',  # Address: format
            r'CA:\s*([A-Za-z0-9]{40,50})',  # CA: format
            r'Token:\s*([A-Za-z0-9]{40,50})',  # Token: format
        ]
        
        tokens = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if len(match) >= 40 and is_valid_solana_address(match):
                    tokens.add(match)
        
        return list(tokens)
    
    def detect_platform(self, text: str) -> str:
        """Detect trading platform from message"""
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in ['pump.fun', 'pumpfun', 'pump fun']):
            return 'pumpfun'
        elif any(keyword in text_lower for keyword in ['moonshot', 'moon shot']):
            return 'moonshot'
        elif any(keyword in text_lower for keyword in ['raydium', 'ray']):
            return 'raydium'
        elif any(keyword in text_lower for keyword in ['jupiter', 'jup']):
            return 'jupiter'
        else:
            return 'unknown'
    
    async def process_buy_signal(self, token_mint: str, platform: str, message: str):
        """Process buy signal for token"""
        try:
            logger.info(f"🔄 Processing buy signal: {token_mint}")
            
            # Check if we already have this token
            db = next(get_db())
            existing_trades = get_active_trades(db)
            
            for trade in existing_trades:
                if trade.token_mint_address == token_mint:
                    logger.info(f"⚠️ Already have active trade for {token_mint}")
                    return
            
            # Check max purchases limit
            if len(existing_trades) >= MAX_PURCHASES:
                logger.warning(f"⚠️ Max purchases limit reached ({MAX_PURCHASES})")
                await self.send_dm_to_owner(
                    f"⚠️ **Max Purchases Limit Reached**\n"
                    f"🔢 Current: {len(existing_trades)}/{MAX_PURCHASES}\n"
                    f"🪙 Skipped token: `{token_mint}`"
                )
                return
            
            # Get token price
            current_price = await get_token_price_sol(token_mint)
            if not current_price:
                logger.error(f"❌ Could not get price for {token_mint}")
                return
            
            logger.info(f"💰 Token price: {current_price:.12f} SOL")
            
            # Execute buy
            logger.warning(f"🔴 EXECUTING BUY FOR: {token_mint}")
            buy_result = await buy_token_solana(token_mint)
            
            if not buy_result:
                logger.error(f"❌ Buy failed for {token_mint}")
                await self.send_dm_to_owner(
                    f"❌ **Buy Failed**\n"
                    f"🪙 Token: `{token_mint}`\n"
                    f"🏷️ Platform: {platform}"
                )
                return
            
            # Check if real or mock
            is_real = not buy_result['buy_tx_signature'].startswith('mock_')
            
            # Save to database
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
            
            # Send notification
            await self.send_buy_notification(buy_result, platform, is_real, message)
            
        except Exception as e:
            logger.error(f"❌ Buy signal processing error: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
    
    async def send_buy_notification(self, buy_result: dict, platform: str, is_real: bool, original_message: str):
        """Send buy notification to owner"""
        try:
            status_emoji = "🔴" if is_real else "🟡"
            status_text = "REAL TRADE" if is_real else "MOCK TRADE"
            
            # Build explorer URL
            tx_signature = buy_result['buy_tx_signature']
            explorer_url = f"https://solscan.io/tx/{tx_signature}" if is_real else "N/A (Mock)"
            
            notification = f"""
{status_emoji} **{status_text} - BUY EXECUTED**

🪙 **Token**: `{buy_result['token_mint_address']}`
🏷️ **Platform**: {platform.upper()}
💰 **Buy Price**: {buy_result['buy_price_sol']:.12f} SOL
📊 **Amount**: {buy_result['amount_bought_token']:,.0f} tokens
💵 **Total Cost**: {buy_result['buy_price_sol'] * buy_result['amount_bought_token']:.6f} SOL
🔗 **Transaction**: [View on Solscan]({explorer_url})

📝 **Original Signal**:
{original_message[:200]}...
"""
            
            await self.send_dm_to_owner(notification)
            
        except Exception as e:
            logger.error(f"❌ Notification error: {e}")
    
    async def monitor_trades(self):
        """Monitor active trades for sell conditions"""
        logger.info("👁️ Starting trade monitoring...")
        
        while True:
            try:
                db = next(get_db())
                active_trades = get_active_trades(db)
                
                if not active_trades:
                    await asyncio.sleep(30)
                    continue
                
                logger.debug(f"📊 Monitoring {len(active_trades)} active trades")
                
                for trade in active_trades:
                    await self.check_sell_conditions(trade, db)
                
                await asyncio.sleep(5)  # Check every 5 seconds for responsiveness
                
            except Exception as e:
                logger.error(f"❌ Monitor error: {e}")
                await asyncio.sleep(30)
    
    async def check_sell_conditions(self, trade, db):
        """Check if trade should be sold"""
        try:
            token_mint = trade.token_mint_address
            
            # Get current price
            current_price = await get_token_price_sol(token_mint)
            if not current_price:
                return
            
            # Calculate profit/loss
            profit_loss_percent = (current_price - trade.buy_price_sol) / trade.buy_price_sol
            
            # Get settings
            take_profit = float(os.getenv('TAKE_PROFIT_PERCENT', '3.0'))  # 300%
            stop_loss = float(os.getenv('STOP_LOSS_PERCENT', '0.4'))     # 40%
            
            should_sell = False
            sell_reason = ""
            
            # Take profit check
            if profit_loss_percent >= take_profit:
                should_sell = True
                sell_reason = f"Take Profit ({take_profit*100:.0f}%)"
            
            # Stop loss check
            elif profit_loss_percent <= -stop_loss:
                should_sell = True
                sell_reason = f"Stop Loss ({stop_loss*100:.0f}%)"
            
            # Time-based sell (24 hours with <5% movement)
            elif (datetime.utcnow() - trade.created_at) > timedelta(hours=24):
                if abs(profit_loss_percent) < 0.05:
                    should_sell = True
                    sell_reason = "Time-based (24h, <5% movement)"
            
            if should_sell:
                await self.execute_sell(trade, sell_reason, current_price, db)
            
        except Exception as e:
            logger.error(f"❌ Sell condition check error: {e}")
    
    async def execute_sell(self, trade, reason: str, current_price: float, db):
        """Execute sell order"""
        try:
            logger.warning(f"🔴 EXECUTING SELL: {trade.token_mint_address} - {reason}")
            
            # Execute sell
            sell_result = await sell_token_solana(
                trade.token_mint_address,
                trade.amount_bought_token,
                trade.wallet_token_account
            )
            
            if not sell_result:
                logger.error(f"❌ Sell failed for {trade.token_mint_address}")
                return
            
            # Calculate final P&L
            profit_loss_percent = (current_price - trade.buy_price_sol) / trade.buy_price_sol
            is_real = not sell_result['sell_tx_signature'].startswith('mock_')
            
            # Update database
            status = "sold_profit" if profit_loss_percent > 0 else "sold_loss"
            update_trade_status(
                db, trade.id,
                status=status,
                sell_price_sol=sell_result['sell_price_sol'],
                sell_tx_signature=sell_result['sell_tx_signature']
            )
            
            # Send notification
            await self.send_sell_notification(trade, sell_result, reason, profit_loss_percent, is_real)
            
            logger.info(f"✅ Sell completed: {reason} - P&L: {profit_loss_percent*100:.2f}%")
            
        except Exception as e:
            logger.error(f"❌ Sell execution error: {e}")
    
    async def send_sell_notification(self, trade, sell_result: dict, reason: str, profit_percent: float, is_real: bool):
        """Send sell notification"""
        try:
            status_emoji = "🔴" if is_real else "🟡"
            profit_emoji = "📈" if profit_percent > 0 else "📉"
            
            tx_signature = sell_result['sell_tx_signature']
            explorer_url = f"https://solscan.io/tx/{tx_signature}" if is_real else "N/A (Mock)"
            
            notification = f"""
{status_emoji} **SELL EXECUTED** {profit_emoji}

🪙 **Token**: `{trade.token_mint_address}`
🏷️ **Platform**: {trade.platform.upper()}
🎯 **Reason**: {reason}

💰 **Buy Price**: {trade.buy_price_sol:.12f} SOL
💰 **Sell Price**: {sell_result['sell_price_sol']:.12f} SOL
📊 **P&L**: {profit_percent*100:.2f}%

🔗 **Transaction**: [View on Solscan]({explorer_url})
"""
            
            await self.send_dm_to_owner(notification)
            
        except Exception as e:
            logger.error(f"❌ Sell notification error: {e}")
    
    async def send_dm_to_owner(self, message: str):
        """Send DM to bot owner"""
        try:
            await client.send_message(OWNER_ID, message)
        except Exception as e:
            logger.error(f"❌ DM send error: {e}")
    
    async def send_status_report(self, event):
        """Send status report"""
        try:
            db = next(get_db())
            active_trades = get_active_trades(db)
            
            balance = await real_trader.get_wallet_balance()
            
            status = f"""
📊 **Bot Status Report**

💎 **Wallet**: {real_trader.keypair.pubkey() if real_trader.keypair else 'Not loaded'}
💰 **Balance**: {balance:.6f} SOL
🔴 **Real Trading**: {real_trader.enable_real_trading}
📈 **Active Trades**: {len(active_trades)}/{MAX_PURCHASES}

🎯 **Settings**:
• Buy Amount: {os.getenv('AMOUNT_TO_BUY_SOL')} SOL
• Take Profit: {float(os.getenv('TAKE_PROFIT_PERCENT', '3.0'))*100:.0f}%
• Stop Loss: {float(os.getenv('STOP_LOSS_PERCENT', '0.4'))*100:.0f}%
• Slippage: {int(os.getenv('SLIPPAGE_BPS', '1500'))/100:.1f}%
"""
            
            await event.reply(status)
            
        except Exception as e:
            logger.error(f"❌ Status report error: {e}")
    
    async def send_active_trades(self, event):
        """Send active trades list"""
        try:
            db = next(get_db())
            active_trades = get_active_trades(db)
            
            if not active_trades:
                await event.reply("📊 No active trades")
                return
            
            trades_text = "📊 **Active Trades**:\n\n"
            
            for i, trade in enumerate(active_trades[:5], 1):  # Show max 5
                current_price = await get_token_price_sol(trade.token_mint_address)
                if current_price:
                    pnl = (current_price - trade.buy_price_sol) / trade.buy_price_sol * 100
                    pnl_emoji = "📈" if pnl > 0 else "📉"
                else:
                    pnl = 0
                    pnl_emoji = "❓"
                
                trades_text += f"""
{i}. **{trade.platform.upper()}**
🪙 `{trade.token_mint_address[:16]}...`
💰 Buy: {trade.buy_price_sol:.8f} SOL
{pnl_emoji} P&L: {pnl:.1f}%
"""
            
            await event.reply(trades_text)
            
        except Exception as e:
            logger.error(f"❌ Active trades error: {e}")

# Run the bot
async def main():
    bot = RealTradingBot()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())