"""
Script to generate Solana wallet and get base58 private key
Run this to generate a new wallet or convert existing wallet.json to base58
"""

import json
import base58
from solders.keypair import Keypair
from solders.pubkey import Pubkey
import os
import secrets

def generate_new_wallet():
    """Generate a new Solana wallet using solders - Method 1"""
    try:
        # Method 1: Use Keypair() constructor which generates a random keypair
        keypair = Keypair()
        
        # Get the full keypair bytes (64 bytes: 32 secret + 32 public)
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
        
        # Test the generated key
        test_keypair = Keypair.from_bytes(base58.b58decode(base58_key))
        if str(test_keypair.pubkey()) == str(keypair.pubkey()):
            print("✅ Key validation successful!")
        else:
            print("❌ Key validation failed!")
            
    except Exception as e:
        print(f"❌ Error generating wallet: {e}")

def generate_wallet_from_seed():
    """Generate wallet from 32-byte seed - Method 2"""
    try:
        # Generate 32-byte seed
        seed = secrets.token_bytes(32)
        print(f"🌱 Generated 32-byte seed: {len(seed)} bytes")
        
        # Create a 64-byte array: 32 bytes seed + 32 bytes derived public key
        # For solders, we need to use a different approach
        
        # Method: Create keypair and extract bytes
        temp_keypair = Keypair()
        temp_bytes = bytes(temp_keypair)
        
        # Replace first 32 bytes with our seed
        full_keypair_bytes = bytearray(temp_bytes)
        full_keypair_bytes[:32] = seed
        
        # Try to create keypair from the modified bytes
        try:
            keypair = Keypair.from_bytes(bytes(full_keypair_bytes))
        except:
            # If that fails, just use the temp_keypair
            keypair = temp_keypair
            full_keypair_bytes = bytes(keypair)
        
        base58_key = base58.b58encode(full_keypair_bytes).decode('utf-8')
        
        print("🔑 Wallet Generated from Seed!")
        print(f"📍 Public Key: {keypair.pubkey()}")
        print(f"🔐 Private Key (Base58): {base58_key}")
        print(f"🔢 Keypair Length: {len(full_keypair_bytes)} bytes")
        
        # Save to wallet.json
        with open('wallet_seed.json', 'w') as f:
            json.dump(list(full_keypair_bytes), f)
        
        print("💾 Wallet saved to wallet_seed.json")
        print(f"\n📝 Copy this to your .env file:")
        print(f"SOLANA_PRIVATE_KEY_BASE58={base58_key}")
        
    except Exception as e:
        print(f"❌ Error generating wallet from seed: {e}")

def generate_simple_wallet():
    """Generate wallet with simple method"""
    try:
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
            if str(test_keypair.pubkey()) == str(keypair.pubkey()):
                print(f"✅ Key validation successful: {test_keypair.pubkey()}")
            else:
                print(f"❌ Key validation failed: public keys don't match")
        except Exception as e:
            print(f"❌ Key validation failed: {e}")
        
        print(f"\n📝 Copy this to your .env file:")
        print(f"SOLANA_PRIVATE_KEY_BASE58={base58_key}")
        
    except Exception as e:
        print(f"❌ Error generating simple wallet: {e}")

def convert_wallet_json_to_base58():
    """Convert existing wallet.json to base58 format"""
    if not os.path.exists('wallet.json'):
        print("❌ wallet.json not found!")
        return
    
    try:
        with open('wallet.json', 'r') as f:
            wallet_data = json.load(f)
        
        print(f"🔍 Wallet data length: {len(wallet_data)} bytes")
        
        # Convert to bytes
        wallet_bytes = bytes(wallet_data)
        
        # Handle different formats
        if len(wallet_bytes) == 64:
            # Full keypair (64 bytes)
            keypair = Keypair.from_bytes(wallet_bytes)
            base58_key = base58.b58encode(wallet_bytes).decode('utf-8')
        elif len(wallet_bytes) == 32:
            # Secret key only (32 bytes) - need to pad to 64 bytes
            print("⚠️  32-byte secret key detected, converting to 64-byte format...")
            
            # Create a new keypair and replace the secret key part
            temp_keypair = Keypair()
            temp_bytes = bytearray(bytes(temp_keypair))
            temp_bytes[:32] = wallet_bytes
            
            try:
                keypair = Keypair.from_bytes(bytes(temp_bytes))
                base58_key = base58.b58encode(temp_bytes).decode('utf-8')
            except:
                # If conversion fails, generate new keypair
                print("❌ Conversion failed, generating new keypair...")
                keypair = Keypair()
                keypair_bytes = bytes(keypair)
                base58_key = base58.b58encode(keypair_bytes).decode('utf-8')
        else:
            raise ValueError(f"Invalid wallet data length: {len(wallet_bytes)}. Expected 32 or 64 bytes.")
        
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
        
        if len(keypair_bytes) == 64:
            keypair = Keypair.from_bytes(keypair_bytes)
            print("✅ Keypair created successfully!")
            print(f"📍 Public Key: {keypair.pubkey()}")
            print(f"🌐 Check balance: https://solscan.io/account/{keypair.pubkey()}")
        else:
            print(f"❌ Invalid key length: {len(keypair_bytes)}. Expected 64 bytes.")
            
    except Exception as e:
        print(f"❌ Error creating keypair: {e}")

def debug_keypair_structure():
    """Debug function to understand keypair structure"""
    try:
        print("🔍 Debugging keypair structure...")
        
        # Generate a keypair
        keypair = Keypair()
        keypair_bytes = bytes(keypair)
        
        print(f"📊 Keypair info:")
        print(f"   Total length: {len(keypair_bytes)} bytes")
        print(f"   Public key: {keypair.pubkey()}")
        print(f"   Public key length: {len(str(keypair.pubkey()))} chars")
        
        # Show byte structure
        print(f"   First 8 bytes: {keypair_bytes[:8].hex()}")
        print(f"   Last 8 bytes: {keypair_bytes[-8:].hex()}")
        
        # Test base58 encoding
        base58_key = base58.b58encode(keypair_bytes).decode('utf-8')
        print(f"   Base58 length: {len(base58_key)} chars")
        print(f"   Base58 key: {base58_key[:20]}...{base58_key[-20:]}")
        
        # Test decoding
        decoded = base58.b58decode(base58_key)
        print(f"   Decoded length: {len(decoded)} bytes")
        print(f"   Decode successful: {decoded == keypair_bytes}")
        
        # Test keypair recreation
        new_keypair = Keypair.from_bytes(decoded)
        print(f"   Recreation successful: {str(new_keypair.pubkey()) == str(keypair.pubkey())}")
        
    except Exception as e:
        print(f"❌ Debug error: {e}")

if __name__ == "__main__":
    print("🚀 Solana Wallet Generator for solders")
    print("1. Generate new wallet (recommended)")
    print("2. Generate simple wallet")
    print("3. Generate wallet from seed")
    print("4. Convert existing wallet.json")
    print("5. Test base58 private key")
    print("6. Debug keypair structure")
    
    choice = input("\nChoose option (1-6): ").strip()
    
    if choice == "1":
        generate_new_wallet()
    elif choice == "2":
        generate_simple_wallet()
    elif choice == "3":
        generate_wallet_from_seed()
    elif choice == "4":
        convert_wallet_json_to_base58()
    elif choice == "5":
        test_base58_key()
    elif choice == "6":
        debug_keypair_structure()
    else: