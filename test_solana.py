# Create test_fixes.py
import asyncio
from trading_service import is_valid_solana_address, extract_solana_ca_enhanced
from solana_service import solana_service, init_solana_config_from_env, get_token_price_sol

async def test_fixes():
    print("🧪 Testing Fixed Functions")
    print("=" * 50)
    
    # Test address validation
    test_addresses = [
        "8f2zKNBNH7M4vS9cknsfgzBWZU6vKhp3TvNVJdjLpump",
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "invalid_address"
    ]
    
    for addr in test_addresses:
        is_valid = is_valid_solana_address(addr)
        print(f"📍 {addr[:20]}... - Valid: {'✅' if is_valid else '❌'}")
    
    # Test CA extraction
    test_message = "Check this token: 8f2zKNBNH7M4vS9cknsfgzBWZU6vKhp3TvNVJdjLpump"
    extracted = extract_solana_ca_enhanced(test_message)
    print(f"🔍 Extracted CA: {extracted}")
    
    # Test Solana service
    init_solana_config_from_env()
    print(f"🔑 Wallet loaded: {'✅' if solana_service.keypair else '❌'}")
    
    # Test price function
    if extracted:
        price = await get_token_price_sol(extracted)
        print(f"💰 Price: {price} SOL")
    
    print("✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(test_fixes())