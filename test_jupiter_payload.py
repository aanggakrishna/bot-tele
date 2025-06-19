import asyncio
import aiohttp
import os
import base58
from dotenv import load_dotenv

# Import Solana untuk get wallet pubkey
try:
    from solders.keypair import Keypair
    SOLANA_AVAILABLE = True
except ImportError:
    SOLANA_AVAILABLE = False
    print("❌ Install: pip install solders==0.18.1")

load_dotenv()

def get_wallet_pubkey():
    """Get wallet public key from environment"""
    try:
        private_key_b58 = os.getenv('SOLANA_PRIVATE_KEY_BASE58')
        if private_key_b58 and SOLANA_AVAILABLE:
            key_bytes = base58.b58decode(private_key_b58)
            keypair = Keypair.from_bytes(key_bytes)
            return str(keypair.pubkey())
        return None
    except Exception as e:
        print(f"❌ Wallet error: {e}")
        return None

async def test_jupiter_payloads():
    """Test different Jupiter payload formats"""
    
    # Get real wallet pubkey
    user_pubkey = get_wallet_pubkey()
    if not user_pubkey:
        print("❌ Could not get wallet public key from environment")
        print("💡 Make sure SOLANA_PRIVATE_KEY_BASE58 is set in .env")
        return
    
    print(f"🔑 Using wallet: {user_pubkey}")
    
    # Test parameters
    input_mint = 'So11111111111111111111111111111111111111112'  # SOL
    output_mint = 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263'  # BONK
    amount = 5000000  # 0.005 SOL in lamports
    
    # Get quote first
    jupiter_api = 'https://quote-api.jup.ag/v6'
    quote_url = f"{jupiter_api}/quote"
    quote_params = {
        'inputMint': input_mint,
        'outputMint': output_mint,
        'amount': str(amount),
        'slippageBps': '500'
    }
    
    print("🔄 Getting Jupiter quote...")
    async with aiohttp.ClientSession() as session:
        async with session.get(quote_url, params=quote_params, timeout=10) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f"❌ Quote failed: {response.status}")
                print(f"   Error: {error_text}")
                return
            
            quote = await response.json()
            if 'outAmount' not in quote:
                print(f"❌ Invalid quote response")
                print(f"   Response: {quote}")
                return
            
            print(f"✅ Quote received: {quote['outAmount']} tokens")
            print(f"   Route: {len(quote.get('routePlan', []))} steps")
    
    # Test different payload formats
    payloads = [
        # Format 1: Minimal (recommended)
        {
            'quoteResponse': quote,
            'userPublicKey': user_pubkey,
            'wrapAndUnwrapSol': True
        },
        
        # Format 2: With dynamic compute
        {
            'quoteResponse': quote,
            'userPublicKey': user_pubkey,
            'wrapAndUnwrapSol': True,
            'dynamicComputeUnitLimit': True
        },
        
        # Format 3: Fixed priority fee
        {
            'quoteResponse': quote,
            'userPublicKey': user_pubkey,
            'wrapAndUnwrapSol': True,
            'prioritizationFeeLamports': 1000
        },
        
        # Format 4: With all options
        {
            'quoteResponse': quote,
            'userPublicKey': user_pubkey,
            'wrapAndUnwrapSol': True,
            'dynamicComputeUnitLimit': True,
            'prioritizationFeeLamports': 1000
        },
        
        # Format 5: Legacy transaction
        {
            'quoteResponse': quote,
            'userPublicKey': user_pubkey,
            'wrapAndUnwrapSol': True,
            'asLegacyTransaction': True
        }
    ]
    
    swap_url = f"{jupiter_api}/swap"
    
    for i, payload in enumerate(payloads, 1):
        print(f"\n🧪 Testing payload format {i}...")
        print(f"📊 Keys: {list(payload.keys())}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(swap_url, json=payload, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'swapTransaction' in data:
                            print(f"✅ Format {i}: SUCCESS!")
                            print(f"   Transaction length: {len(data['swapTransaction'])} chars")
                            
                            # Return the successful format
                            return i, payload
                        else:
                            print(f"❌ Format {i}: No swapTransaction in response")
                            print(f"   Response keys: {list(data.keys())}")
                    else:
                        error_text = await response.text()
                        print(f"❌ Format {i}: HTTP {response.status}")
                        print(f"   Error: {error_text[:200]}...")
        except Exception as e:
            print(f"❌ Format {i}: Exception - {e}")
    
    print(f"\n❌ All payload formats failed!")
    return None, None

async def test_simple_quote():
    """Test simple quote without swap"""
    print("\n" + "="*50)
    print("🧪 TESTING SIMPLE QUOTE")
    print("="*50)
    
    jupiter_api = 'https://quote-api.jup.ag/v6'
    quote_url = f"{jupiter_api}/quote"
    
    # Test different quote parameters
    test_cases = [
        {
            'inputMint': 'So11111111111111111111111111111111111111112',  # SOL
            'outputMint': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',  # BONK
            'amount': '5000000',  # 0.005 SOL
            'slippageBps': '500'
        },
        {
            'inputMint': 'So11111111111111111111111111111111111111112',  # SOL
            'outputMint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
            'amount': '10000000',  # 0.01 SOL
            'slippageBps': '300'
        }
    ]
    
    for i, params in enumerate(test_cases, 1):
        print(f"\n🔍 Quote test {i}: {params['outputMint'][:8]}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(quote_url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'outAmount' in data:
                            print(f"✅ Quote {i}: {data['outAmount']} tokens")
                            print(f"   Price impact: {data.get('priceImpactPct', 'N/A')}%")
                        else:
                            print(f"❌ Quote {i}: No outAmount")
                    else:
                        error_text = await response.text()
                        print(f"❌ Quote {i}: HTTP {response.status}")
                        print(f"   Error: {error_text[:100]}...")
        except Exception as e:
            print(f"❌ Quote {i}: Exception - {e}")

async def main():
    print("🚀 JUPITER API TESTING")
    print("="*50)
    
    # Test quotes first
    await test_simple_quote()
    
    # Test swap payloads
    print("\n" + "="*50)
    print("🧪 TESTING SWAP PAYLOADS")
    print("="*50)
    
    success_format, success_payload = await test_jupiter_payloads()
    
    if success_format:
        print(f"\n🎉 SUCCESS! Format {success_format} works!")
        print(f"📋 Successful payload structure:")
        for key, value in success_payload.items():
            if key != 'quoteResponse':  # Don't print the huge quote
                print(f"   {key}: {value}")
    else:
        print(f"\n❌ No working payload format found")
        print(f"💡 Check Jupiter API documentation for latest format")

if __name__ == "__main__":
    asyncio.run(main())