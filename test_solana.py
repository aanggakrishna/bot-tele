# Create test_real_trading_safety.py
import asyncio
import os
from dotenv import load_dotenv
from solana_service import solana_service, init_solana_config_from_env

load_dotenv()

async def safety_checklist():
    """Comprehensive safety checklist before enabling real trading"""
    print("🚨 REAL TRADING SAFETY CHECKLIST")
    print("=" * 60)
    
    # Initialize service
    init_solana_config_from_env()
    
    # Check 1: Trading flag
    real_trading = os.getenv('ENABLE_REAL_TRADING', 'false').lower() == 'true'
    print(f"🔴 Real trading enabled: {'YES ⚠️' if real_trading else 'NO ✅'}")
    
    # Check 2: Wallet balance
    if solana_service.keypair:
        balance = await solana_service.get_wallet_balance()
        buy_amount = float(os.getenv('AMOUNT_TO_BUY_SOL', '0.01'))
        print(f"💰 Wallet balance: {balance:.6f} SOL")
        print(f"🛒 Buy amount: {buy_amount:.6f} SOL")
        
        if balance and balance >= buy_amount + 0.001:
            print(f"✅ Sufficient balance for trading")
        else:
            print(f"❌ INSUFFICIENT BALANCE - Need at least {buy_amount + 0.001:.6f} SOL")
    else:
        print("❌ NO WALLET LOADED")
    
    # Check 3: Safety settings
    stop_loss = float(os.getenv('STOP_LOSS_PERCENT', '0.20'))
    take_profit = float(os.getenv('TAKE_PROFIT_PERCENT', '0.50'))
    slippage = int(os.getenv('SLIPPAGE_BPS', '300'))
    
    print(f"🛑 Stop loss: {stop_loss*100:.1f}%")
    print(f"🎯 Take profit: {take_profit*100:.1f}%")
    print(f"📊 Slippage: {slippage/100:.1f}%")
    
    # Check 4: Network
    print(f"🌐 RPC URL: {solana_service.rpc_url}")
    is_mainnet = 'mainnet' in solana_service.rpc_url
    print(f"⚠️ Network: {'MAINNET (REAL MONEY!)' if is_mainnet else 'Devnet/Testnet'}")
    
    print("\n" + "=" * 60)
    print("⚠️ FINAL WARNING:")
    print("- Real trading = Real money at risk!")
    print("- Start with VERY small amounts (0.001 SOL)")
    print("- Monitor closely for first few trades")
    print("- Many tokens are scams/rugs - be careful!")
    print("=" * 60)
    
    if real_trading:
        print("🔴 REAL TRADING IS ENABLED!")
        print("💡 To disable: Set ENABLE_REAL_TRADING=false in .env")
    else:
        print("🟡 Real trading is DISABLED (safe mode)")
        print("💡 To enable: Set ENABLE_REAL_TRADING=true in .env")

if __name__ == "__main__":
    asyncio.run(safety_checklist())