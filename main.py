import asyncio
from loguru import logger
from monitor_bot import TelegramMonitorBot
from config import config

async def main():
    """Main entry point"""
    logger.info("=" * 50)
    logger.info("🚀 Solana CA Monitor Bot")
    logger.info("=" * 50)
    
    # Check if bot is enabled
    if not config.BOT_ENABLED:
        logger.warning("⚠️ Bot is disabled in config. Set BOT_ENABLED=true to enable.")
        return
    
    # Check configuration
    if not config.API_ID or not config.API_HASH:
        logger.error("❌ API_ID and API_HASH must be configured in .env")
        return
        
    if not config.OWNER_ID:
        logger.warning("⚠️ OWNER_ID not configured in .env")
        
    if not config.MONITOR_CHANNELS and not config.MONITOR_GROUPS:
        logger.error("❌ No channels or groups configured to monitor")
        return
    
    # Create and run bot
    bot = TelegramMonitorBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("👋 Goodbye!")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")