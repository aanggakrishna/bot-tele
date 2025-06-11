import config
from jupiter_swap import execute_swap

SOL_MINT = "So11111111111111111111111111111111111111112"

def buy_token(ca):
    print(f"🚀 Buying {ca}")
    amount_sol = 0.01
    amount_lamports = int(amount_sol * 1_000_000_000)
    txid = execute_swap(SOL_MINT, ca, amount_lamports, slippage=3)
    print(f"✅ Buy tx: {txid}")

def sell_token(ca):
    print(f"🔻 Selling {ca}")
    amount = 1
    txid = execute_swap(ca, SOL_MINT, amount, slippage=3)
    print(f"✅ Sell tx: {txid}")
