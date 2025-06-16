"""
Script to generate Solana wallet and get base58 private key
Run this to generate a new wallet or convert existing wallet.json to base58
"""

import json
import base58
from solders.keypair import Keypair
import os

def generate_new_wallet():
    """Generate a new Solana wallet"""
    keypair = Keypair()
    
    print("🔑 New Solana Wallet Generated!")
    print(f"📍 Public Key: {keypair.pubkey()}")
    print(f"🔐 Private Key (Base58): {base58.b58encode(bytes(keypair)).decode('utf-8')}")
    
    # Save to wallet.json
    with open('wallet.json', 'w') as f:
        json.dump(list(bytes(keypair)), f)
    
    print("💾 Wallet saved to wallet.json")
    print("\n⚠️  IMPORTANT: Keep your private key secure and never share it!")
    print("💰 Fund this wallet with SOL before running the bot")
    print(f"🌐 Check balance: https://solscan.io/account/{keypair.pubkey()}")

def convert_wallet_json_to_base58():
    """Convert existing wallet.json to base58 format"""
    if not os.path.exists('wallet.json'):
        print("❌ wallet.json not found!")
        return
    
    try:
        with open('wallet.json', 'r') as f:
            wallet_data = json.load(f)
        
        private_key_bytes = bytes(wallet_data)
        keypair = Keypair.from_bytes(private_key_bytes)
        base58_key = base58.b58encode(bytes(keypair)).decode('utf-8')
        
        print("🔄 Wallet.json converted!")
        print(f"📍 Public Key: {keypair.pubkey()}")
        print(f"🔐 Private Key (Base58): {base58_key}")
        print(f"🌐 Check balance: https://solscan.io/account/{keypair.pubkey()}")
        print("\n📝 Copy the Base58 private key to your .env file:")
        print(f"SOLANA_PRIVATE_KEY_BASE58={base58_key}")
        
    except Exception as e:
        print(f"❌ Error converting wallet: {e}")

if __name__ == "__main__":
    print("🚀 Solana Wallet Generator")
    print("1. Generate new wallet")
    print("2. Convert existing wallet.json to base58")
    
    choice = input("\nChoose option (1 or 2): ").strip()
    
    if choice == "1":
        generate_new_wallet()
    elif choice == "2":
        convert_wallet_json_to_base58()
    else:
        print("❌ Invalid choice!")