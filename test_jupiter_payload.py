# Create test_jupiter_payload.py
import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

async def test_jupiter_payloads():
    """Test different Jupiter payload formats"""
    
    # Test parameters
    input_mint = 'So11111111111111111111111111111111111111112'  # SOL
    output_mint = 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263'  # BONK
    amount = 5000000  # 0.005 SOL in lamports
    user_pubkey = 'YOUR_WALLET_PUBKEY_HERE'
    
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
                print(f"❌ Quote failed: {response.status}")
                return
            
            quote = await response.json()
            if 'outAmount' not in quote:
                print(f"❌ Invalid quote response")
                return
            
            print(f"✅ Quote received: {quote['outAmount']} tokens")
    
    # Test different payload formats
    payloads = [
        # Format 1: Minimal
        {
            'quoteResponse': quote,
            'userPublicKey': user_pubkey
        },
        
        # Format 2: Basic options
        {
            'quoteResponse': quote,
            'userPublicKey': user_pubkey,
            'wrapAndUnwrapSol': True
        },
        
        # Format 3: Fixed compute settings
        {
            'quoteResponse': quote,
            'userPublicKey': user_pubkey,
            'wrapAndUnwrapSol': True,
            'computeUnitPriceMicroLamports': 1000,
            'prioritizationFeeLamports': 10000
        },
        
        # Format 4: Auto settings
        {
            'quoteResponse': quote,
            'userPublicKey': user_pubkey,
            'wrapAndUnwrapSol': True,
            'computeUnitPriceMicroLamports': 'auto'
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
                        else:
                            print(f"❌ Format {i}: No swapTransaction in response")
                    else:
                        error_text = await response.text()
                        print(f"❌ Format {i}: HTTP {response.status}")
                        print(f"   Error: {error_text[:200]}...")
        except Exception as e:
            print(f"❌ Format {i}: Exception - {e}")

if __name__ == "__main__":
    asyncio.run(test_jupiter_payloads())