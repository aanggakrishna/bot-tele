"""
Script to generate Solana wallet and get base58 private key
Run this to generate a new wallet or convert existing wallet.json to base58
"""

import json
import base58
from solders.keypair import Keypair
import os
import secrets

def generate_new_wallet():
    """Generate a new Solana wallet using solders"""
    # Generate a random 32-byte seed
    seed = secrets.token_bytes(32)
    keypair = Keypair.from_bytes(seed)
    
    # For solders, we store the full keypair bytes
    keypair_bytes = bytes(keypair)
    base58_key = base58.b58encode(keypair_bytes).decode('utf-8')
    
    print("🔑 New Solana Wallet Generated!")
    print(f"📍 Public Key: {keypair.pubkey()}")
    print(f"🔐 Private Key (Base58): {base58_key}")
    print(f"🔢 Keypair Length: {len(keypair_bytes)} bytes")
    
    # Save to wallet.json (as array of bytes)
    with open('wallet.json', 'w') as f:
        json.dump(list(keypair_bytes), f)
    
    print("💾 Wallet saved to wallet.json")
    print("\n⚠️  IMPORTANT: Keep your private key secure and never share it!")
    print("💰 Fund this wallet with SOL before running the bot")
    print(f"🌐 Check balance: https://solscan.io/account/{keypair.pubkey()}")
    print(f"\n📝 Copy this to your .env file:")
    print(f"SOLANA_PRIVATE_KEY_BASE58={base58_key}")

def generate_simple_wallet():
    """Generate wallet with simple method"""
    keypair = Keypair()
    keypair_bytes = bytes(keypair)
    base58_key = base58.b58encode(keypair_bytes).decode('utf-8')
    
    print("🔑 Simple Wallet Generated!")
    print(f"📍 Public Key: {keypair.pubkey()}")
    print(f"🔐 Private Key (Base58): {base58_key}")
    print(f"🔢 Length: {len(keypair_bytes)} bytes")
    
    # Test the key immediately
    try:
        test_keypair = Keypair.from_bytes(base58.b58decode(base58_key))
        print(f"✅ Key validation successful: {test_keypair.pubkey()}")
    except Exception as e:
        print(f"❌ Key validation failed: {e}")
    
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
        
        print(f"🔍 Wallet data length: {len(wallet_data)} bytes")
        
        # Convert to bytes and create keypair
        keypair_bytes = bytes(wallet_data)
        
        # Handle different formats
        if len(keypair_bytes) == 64:
            # Full keypair (64 bytes)
            keypair = Keypair.from_bytes(keypair_bytes)
            base58_key = base58.b58encode(keypair_bytes).decode('utf-8')
        elif len(keypair_bytes) == 32:
            # Secret key only (32 bytes) - create keypair and get full bytes
            keypair = Keypair.from_bytes(keypair_bytes)
            full_keypair_bytes = bytes(keypair)
            base58_key = base58.b58encode(full_keypair_bytes).decode('utf-8')
        else:
            raise ValueError(f"Invalid wallet data length: {len(keypair_bytes)}. Expected 32 or 64 bytes.")
        
        print("🔄 Wallet.json converted!")
        print(f"📍 Public Key: {keypair.pubkey()}")
        print(f"🔐 Private Key (Base58): {base58_key}")
        print(f"🌐 Check balance: https://solscan.io/account/{keypair.pubkey()}")
        print("\n📝 Copy this to your .env file:")
        print(f"SOLANA_PRIVATE_KEY_BASE58={base58_key}")
        
    except Exception as e:
        print(f"❌ Error converting wallet: {e}")

def test_base58_key():
    """Test a base58 private key"""
    base58_key = input("Enter your base58 private key: ").strip()
    
    try:
        keypair_bytes = base58.b58decode(base58_key)
        print(f"🔍 Decoded length: {len(keypair_bytes)} bytes")
        
        keypair = Keypair.from_bytes(keypair_bytes)
        
        print("✅ Keypair created successfully!")
        print(f"📍 Public Key: {keypair.pubkey()}")
        print(f"🌐 Check balance: https://solscan.io/account/{keypair.pubkey()}")
        
    except Exception as e:
        print(f"❌ Error creating keypair: {e}")

if __name__ == "__main__":
    print("🚀 Solana Wallet Generator for solders")
    print("1. Generate new wallet (recommended)")
    print("2. Generate simple wallet")
    print("3. Convert existing wallet.json")
    print("4. Test base58 private key")
    
    choice = input("\nChoose option (1-4): ").strip()
    
    if choice == "1":
        generate_new_wallet()
    elif choice == "2":
        generate_simple_wallet()
    elif choice == "3":
        convert_wallet_json_to_base58()
    elif choice == "4":
        test_base58_key()
    else:
        print("❌ Invalid choice!")