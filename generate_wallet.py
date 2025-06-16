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
    
    # Get the secret key (first 32 bytes of the keypair)
    secret_key = bytes(keypair)[:32]
    base58_key = base58.b58encode(secret_key).decode('utf-8')
    
    print("🔑 New Solana Wallet Generated!")
    print(f"📍 Public Key: {keypair.pubkey()}")
    print(f"🔐 Private Key (Base58): {base58_key}")
    
    # Save to wallet.json (64 bytes format)
    with open('wallet.json', 'w') as f:
        json.dump(list(bytes(keypair)), f)
    
    print("💾 Wallet saved to wallet.json")
    print("\n⚠️  IMPORTANT: Keep your private key secure and never share it!")
    print("💰 Fund this wallet with SOL before running the bot")
    print(f"🌐 Check balance: https://solscan.io/account/{keypair.pubkey()}")
    print(f"\n📝 Copy this to your .env file:")
    print(f"SOLANA_PRIVATE_KEY_BASE58={base58_key}")

def convert_wallet_json_to_base58():
    """Convert existing wallet.json to base58 format"""
    if not os.path.exists('wallet.json'):
        print("❌ wallet.json not found!")
        return
    
    try:
        with open('wallet.json', 'r') as f:
            wallet_data = json.load(f)
        
        # Check if it's 32 bytes (secret key only) or 64 bytes (full keypair)
        if len(wallet_data) == 32:
            # It's just the secret key
            secret_key_bytes = bytes(wallet_data)
            keypair = Keypair.from_bytes(secret_key_bytes)
        elif len(wallet_data) == 64:
            # It's the full keypair, take first 32 bytes as secret key
            full_keypair_bytes = bytes(wallet_data)
            secret_key_bytes = full_keypair_bytes[:32]
            keypair = Keypair.from_bytes(secret_key_bytes)
        else:
            raise ValueError(f"Invalid wallet data length: {len(wallet_data)}. Expected 32 or 64 bytes.")
        
        base58_key = base58.b58encode(secret_key_bytes).decode('utf-8')
        
        print("🔄 Wallet.json converted!")
        print(f"📍 Public Key: {keypair.pubkey()}")
        print(f"🔐 Private Key (Base58): {base58_key}")
        print(f"🌐 Check balance: https://solscan.io/account/{keypair.pubkey()}")
        print("\n📝 Copy this to your .env file:")
        print(f"SOLANA_PRIVATE_KEY_BASE58={base58_key}")
        
    except Exception as e:
        print(f"❌ Error converting wallet: {e}")

def create_from_base58():
    """Create keypair from base58 private key for testing"""
    base58_key = input("Enter your base58 private key: ").strip()
    
    try:
        secret_key_bytes = base58.b58decode(base58_key)
        if len(secret_key_bytes) != 32:
            raise ValueError(f"Invalid secret key length: {len(secret_key_bytes)}. Expected 32 bytes.")
        
        keypair = Keypair.from_bytes(secret_key_bytes)
        
        print("✅ Keypair created successfully!")
        print(f"📍 Public Key: {keypair.pubkey()}")
        print(f"🌐 Check balance: https://solscan.io/account/{keypair.pubkey()}")
        
    except Exception as e:
        print(f"❌ Error creating keypair: {e}")

if __name__ == "__main__":
    print("🚀 Solana Wallet Generator")
    print("1. Generate new wallet")
    print("2. Convert existing wallet.json to base58")
    print("3. Test base58 private key")
    
    choice = input("\nChoose option (1, 2, or 3): ").strip()
    
    if choice == "1":
        generate_new_wallet()
    elif choice == "2":
        convert_wallet_json_to_base58()
    elif choice == "3":
        create_from_base58()
    else:
        print("❌ Invalid choice!")