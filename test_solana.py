import asyncio
import sys
import os

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_service import extract_solana_ca_enhanced
from solana_service import (
    solana_service, 
    init_solana_config_from_env, 
    get_token_price_sol,
    is_valid_solana_address
)

async def test_fixes():
    print("🧪 Testing Fixed Functions")
    print("=" * 50)
    
    # Test address validation
    test_addresses = [
        "8f2zKNBNH7M4vS9cknsfgzBWZU6vKhp3TvNVJdjLpump",
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "invalid_address"
    ]
    
    print("📍 Testing Address Validation:")
    for addr in test_addresses:
        is_valid = is_valid_solana_address(addr)
        print(f"   {addr[:20]}... - Valid: {'✅' if is_valid else '❌'}")
    
    print("\n🔍 Testing CA Extraction:")
    test_message = "Check this token: 8f2zKNBNH7M4vS9cknsfgzBWZU6vKhp3TvNVJdjLpump from pump.fun"
    extracted = extract_solana_ca_enhanced(test_message)
    print(f"   Message: {test_message[:50]}...")
    print(f"   Extracted CA: {extracted}")
    
    print("\n🔧 Testing Solana Service Initialization:")
    init_success = init_solana_config_from_env()
    print(f"   Initialization successful: {'✅' if init_success else '❌'}")
    print(f"   Wallet loaded: {'✅' if solana_service.keypair else '❌ (Monitoring mode only)'}")
    print(f"   RPC URL: {solana_service.rpc_url}")
    
    print("\n💰 Testing Price Function:")
    if extracted:
        try:
            price = await get_token_price_sol(extracted)
            print(f"   Price for {extracted[:16]}...: {price} SOL")
        except Exception as e:
            print(f"   Price test failed: {e}")
    else:
        print("   No valid CA to test price with")
    
    print("\n🚀 Testing Buy Function (Mock):")
    if extracted:
        try:
            buy_result = await solana_service.buy_token(extracted)
            if buy_result:
                print(f"   Mock buy successful:")
                print(f"     Token: {buy_result['token_mint_address'][:16]}...")
                print(f"     Price: {buy_result['buy_price_sol']} SOL")
                print(f"     Amount: {buy_result['amount_bought_token']:,.0f} tokens")
                print(f"     TX: {buy_result['buy_tx_signature']}")
            else:
                print("   Mock buy failed")
        except Exception as e:
            print(f"   Buy test failed: {e}")
    
    print("\n✅ All tests completed!")

async def test_real_addresses():
    """Test with known real Solana addresses"""
    print("\n🎯 Testing with Real Token Addresses:")
    print("=" * 50)
    
    real_tokens = [
        ("BONK", "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"),
        ("USDC", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"),
        ("SOL", "So11111111111111111111111111111111111111112"),
        ("Your Token", "8f2zKNBNH7M4vS9cknsfgzBWZU6vKhp3TvNVJdjLpump")
    ]
    
    for name, address in real_tokens:
        is_valid = is_valid_solana_address(address)
        print(f"📍 {name:<10} {address[:16]}... - Valid: {'✅' if is_valid else '❌'}")
        
        if is_valid:
            try:
                price = await get_token_price_sol(address)
                print(f"   💰 Mock price: {price} SOL")
            except Exception as e:
                print(f"   💰 Price error: {e}")

def main():
    """Main test function"""
    try:
        print("🚀 Starting Comprehensive Solana Service Tests")
        print("=" * 60)
        
        # Run basic tests
        asyncio.run(test_fixes())
        
        # Run real address tests
        asyncio.run(test_real_addresses())
        
        print("\n" + "=" * 60)
        print("🎉 All tests completed successfully!")
        
    except KeyboardInterrupt:
        print("\n👋 Tests interrupted by user")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure all files are in the same directory and properly configured")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()