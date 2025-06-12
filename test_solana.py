# Buat file test_solana.py untuk testing terpisah:

import asyncio
import os
from dotenv import load_dotenv
from loguru import logger
import solana_service

load_dotenv()

async def test_solana_validation():
    """Test validasi alamat Solana"""
    
    # Test addresses
    test_addresses = [
        "HLcVBPMpALNGMvixanRNxiL1NQ4rdXJaaExwaBCkpump",  # Your address
        "So11111111111111111111111111111111111111112",    # SOL address
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC address
        "invalidaddress",                                   # Invalid
        "11111111111111111111111111111111"                 # System program (valid but different)
    ]
    
    logger.info("Testing address validation...")
    
    for addr in test_addresses:
        logger.info(f"\nTesting: {addr}")
        validated = solana_service.validate_token_address(addr)
        if validated:
            logger.info(f"  ✅ Valid - PublicKey: {validated}")
        else:
            logger.error(f"  ❌ Invalid")

async def test_jupiter_connectivity():
    """Test Jupiter API"""
    import aiohttp
    
    jupiter_url = os.getenv('JUPITER_API_URL')
    if not jupiter_url:
        logger.error("JUPITER_API_URL not set")
        return
    
    logger.info(f"Testing Jupiter API: {jupiter_url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test tokens endpoint
            async with session.get(f"{jupiter_url}/tokens") as response:
                logger.info(f"Tokens endpoint: {response.status}")
                
            # Test quote endpoint with SOL -> USDC
            params = {
                'inputMint': 'So11111111111111111111111111111111111111112',
                'outputMint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', 
                'amount': 1000000000,  # 1 SOL
                'slippageBps': 50
            }
            async with session.get(f"{jupiter_url}/quote", params=params) as response:
                logger.info(f"Quote endpoint: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Quote successful: {data.get('outAmount', 'N/A')} USDC")
    
    except Exception as e:
        logger.error(f"Jupiter API test failed: {e}")

async def main():
    logger.info("Starting Solana service tests...")
    
    # Initialize solana service
    try:
        solana_service.init_solana_config(
            rpc_url=os.getenv('RPC_URL'),
            private_key_path=os.getenv('PRIVATE_KEY_PATH'),
            amount_to_buy_sol=float(os.getenv('AMOUNT_TO_BUY_SOL', 0.01)),
            slippage_bps=int(os.getenv('SLIPPAGE_BPS', 50)),
            jupiter_api_url=os.getenv('JUPITER_API_URL'),
            solana_private_key_base58=os.getenv('SOLANA_PRIVATE_KEY_BASE58')
        )
        logger.info("✅ Solana service initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize solana service: {e}")
        return
    
    # Run tests
    await test_solana_validation()
    await test_jupiter_connectivity()
    
    logger.info("🎉 All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())