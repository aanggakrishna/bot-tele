# Create test_simple_services.py
import asyncio
from solana_service import solana_service, init_solana_config_from_env
from trading_service import extract_solana_ca_enhanced, MultiPlatformTradingService

async def test_services():
    print("🧪 Testing Simplified Services")
    print("=" * 50)
    
    # Initialize
    init_solana_config_from_env()
    trading_service = MultiPlatformTradingService(solana_service)
    
    # Test CA extraction
    test_message = "Check this token: 8f2zKNBNH7M4vS9cknsfgzBWZU6vKhp3TvNVJdjLpump from pump.fun"
    ca = extract_solana_ca_enhanced(test_message)
    print(f"📝 Test message: {test_message[:50]}...")
    print(f"🪙 Extracted CA: {ca}")
    
    if ca:
        # Test price
        price = await solana_service.get_token_price_sol(ca)
        print(f"💰 Token price: {price} SOL")
        
        # Test buy
        buy_result = await trading_service.buy_token_multi_platform(ca, test_message)
        print(f"🚀 Buy result: {buy_result}")
        
        if buy_result:
            # Test sell
            sell_result = await trading_service.sell_token_multi_platform(
                ca, 1000, buy_result['wallet_token_account'], buy_result['platform']
            )
            print(f"💰 Sell result: {sell_result}")
    
    print("✅ Test completed!")

if __name__ == "__main__":
    asyncio.run(test_services())