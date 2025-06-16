# Create test_real_buy_comprehensive.py
import asyncio
import os
from dotenv import load_dotenv
from solana_service import solana_service, init_solana_config_from_env

load_dotenv()

async def comprehensive_test():
    """Comprehensive test untuk real trading"""
    print("🚀 COMPREHENSIVE REAL TRADING TEST")
    print("=" * 60)
    
    # Initialize
    success = init_solana_config_from_env()
    print(f"🔧 Service initialized: {'✅' if success else '❌'}")
    
    # Show current settings
    print(f"🔴 Real trading enabled: {solana_service.enable_real_trading}")
    print(f"🔑 Wallet loaded: {'✅' if solana_service.keypair else '❌'}")
    print(f"🌐 RPC URL: {solana_service.rpc_url}")
    print(f"💰 Buy amount: {os.getenv('AMOUNT_TO_BUY_SOL', '0.01')} SOL")
    print(f"📊 Slippage: {int(os.getenv('SLIPPAGE_BPS', '500'))/100:.1f}%")
    
    # Test wallet balance
    if solana_service.keypair:
        balance = await solana_service.get_wallet_balance()
        print(f"💎 Wallet balance: {balance:.6f} SOL" if balance else "❌ Could not get balance")
    
    print("\n" + "=" * 60)
    print("🧪 TESTING PRICE APIS")
    print("=" * 60)
    
    # Test tokens
    test_tokens = [
        ("BONK", "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"),
        ("USDC", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"),
        ("Test Token", "8f2zKNBNH7M4vS9cknsfgzBWZU6vKhp3TvNVJdjLpump")
    ]
    
    for name, address in test_tokens:
        print(f"\n🪙 Testing {name}: {address[:16]}...")
        
        # Test price
        price = await solana_service.get_token_price_sol(address)
        print(f"   💰 Price: {price} SOL" if price else "   ❌ No price")
        
        # Test Jupiter quote
        try:
            buy_amount_sol = 0.001  # Very small test amount
            amount_lamports = int(buy_amount_sol * 1_000_000_000)
            
            quote = await solana_service._get_jupiter_quote(
                input_mint='So11111111111111111111111111111111111111112',  # SOL
                output_mint=address,
                amount=amount_lamports,
                slippage_bps=500
            )
            
            if quote:
                expected_tokens = int(quote.get('outAmount', 0))
                print(f"   💱 Jupiter quote: {expected_tokens:,} tokens for {buy_amount_sol} SOL")
            else:
                print(f"   ❌ Jupiter quote failed")
                
        except Exception as e:
            print(f"   ❌ Quote error: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 TESTING BUY FUNCTION")
    print("=" * 60)
    
    # Test buy with BONK (well-known token)
    test_token = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # BONK
    print(f"🚀 Testing buy with BONK: {test_token}")
    
    try:
        result = await solana_service.buy_token(test_token)
        
        if result:
            print(f"✅ Buy test result:")
            print(f"   🪙 Token: {result['token_mint_address'][:16]}...")
            print(f"   💰 Price: {result['buy_price_sol']:.8f} SOL per token")
            print(f"   📊 Amount: {result['amount_bought_token']:,.0f} tokens")
            print(f"   📝 TX: {result['buy_tx_signature']}")
            
            if result['buy_tx_signature'].startswith('mock_'):
                print(f"   🟡 This was a MOCK transaction (safe)")
            else:
                print(f"   🔴 This was a REAL transaction!")
                print(f"   🔗 Solscan: https://solscan.io/tx/{result['buy_tx_signature']}")
        else:
            print(f"❌ Buy test failed")
            
    except Exception as e:
        print(f"❌ Buy test error: {e}")
    
    print("\n" + "=" * 60)
    
    if solana_service.enable_real_trading:
        print("🔴 REAL TRADING IS ENABLED!")
        print("⚠️  Transactions will use real SOL!")
        print("💡 To disable: Set ENABLE_REAL_TRADING=false in .env")
    else:
        print("🟡 MOCK TRADING MODE")
        print("✅ Safe for testing - no real money used")
        print("💡 To enable real trading: Set ENABLE_REAL_TRADING=true in .env")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(comprehensive_test())