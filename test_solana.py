import asyncio
from solana_service import trader
from loguru import logger

async def test_solana_functions():
    """Test Solana functions individually"""
    
    logger.info("🧪 Testing Solana Service...")
    
    # Initialize
    if not trader.init_from_config():
        logger.error("❌ Failed to initialize trader")
        return
    
    logger.info("✅ Trader initialized")
    
    # Test wallet balance
    balance = await trader.get_wallet_balance()
    logger.info(f"💰 Wallet balance: {balance} SOL")
    
    # Test price check
    test_tokens = [
        "So11111111111111111111111111111111111111112",  # SOL
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    ]
    
    for token in test_tokens:
        price = await trader.get_token_price_sol(token)
        logger.info(f"💰 {token[:8]}... price: {price} SOL")
    
    # Test mock buy
    logger.info("🧪 Testing mock buy...")
    test_token = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"  # Jupiter token
    
    # Force mock mode for test
    original_real_trading = trader.enable_real_trading
    trader.enable_real_trading = False
    
    buy_result = await trader.buy_token(test_token)
    if buy_result:
        logger.info(f"✅ Mock buy successful: {buy_result}")
    else:
        logger.error("❌ Mock buy failed")
    
    # Test mock sell
    if buy_result:
        sell_result = await trader.sell_token(test_token, 1000, "mock_account")
        if sell_result:
            logger.info(f"✅ Mock sell successful: {sell_result}")
        else:
            logger.error("❌ Mock sell failed")
    
    # Restore original setting
    trader.enable_real_trading = original_real_trading
    
    logger.info("✅ All tests completed")

if __name__ == "__main__":
    asyncio.run(test_solana_functions())