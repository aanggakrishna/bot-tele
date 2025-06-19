# Create test_real_trading.py
import asyncio
from solana_service import init_real_trading, buy_token_solana, real_trader

async def test_real_buy():
    """Test real trading functionality"""
    print("🧪 TESTING REAL TRADING")
    print("=" * 50)
    
    # Initialize
    success = await init_real_trading()
    print(f"✅ Initialized: {success}")
    
    if real_trader.keypair:
        balance = await real_trader.get_wallet_balance()
        print(f"💰 Balance: {balance:.6f} SOL")
        print(f"🔴 Real trading: {real_trader.enable_real_trading}")
        
        # Test with BONK
        test_token = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        price = await real_trader.get_token_price_sol(test_token)
        print(f"💰 BONK price: {price:.12f} SOL")
        
        # Test buy
        result = await buy_token_solana(test_token)
        if result:
            if result['buy_tx_signature'].startswith('mock_'):
                print("🟡 MOCK BUY executed")
            else:
                print("🔴 REAL BUY executed!")
                print(f"🔗 TX: https://solscan.io/tx/{result['buy_tx_signature']}")

if __name__ == "__main__":
    asyncio.run(test_real_buy())