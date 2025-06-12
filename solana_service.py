#!/usr/bin/env python3
"""
Test script for Solana service functionality
"""

import asyncio
import os
from loguru import logger
from solana_service import (
    init_solana_config,
    validate_token_address,
    get_token_price_sol,
    buy_token_solana,
    sell_token_solana
)

# Configuration
RPC_URL = "https://api.mainnet-beta.solana.com"
PRIVATE_KEY_PATH = "wallet.json"  # Path to your wallet file
AMOUNT_TO_BUY_SOL = 0.01  # Amount in SOL to buy
SLIPPAGE_BPS = 100  # 1% slippage
JUPITER_API_URL = "https://quote-api.jup.ag/v6"
SOLANA_PRIVATE_KEY_BASE58 = None  # Set this if you want to use base58 key instead

# Test token addresses (replace with actual tokens you want to test)
TEST_TOKENS = [
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
    # Add more token addresses here for testing
]

async def test_solana_service():
    """Test all Solana service functions"""
    
    try:
        # Test 1: Initialize Solana configuration
        logger.info("🔧 Testing Solana configuration initialization...")
        
        init_solana_config(
            rpc_url=RPC_URL,
            private_key_path=PRIVATE_KEY_PATH,
            amount_to_buy_sol=AMOUNT_TO_BUY_SOL,
            slippage_bps=SLIPPAGE_BPS,
            jupiter_api_url=JUPITER_API_URL,
            solana_private_key_base58=SOLANA_PRIVATE_KEY_BASE58
        )
        
        logger.info("✅ Solana configuration initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Solana configuration: {e}")
        return False
    
    # Test 2: Validate token addresses
    logger.info("🔍 Testing token address validation...")
    
    valid_addresses = []
    for token_address in TEST_TOKENS:
        logger.info(f"Testing token address: {token_address}")
        
        pubkey = validate_token_address(token_address)
        if pubkey:
            valid_addresses.append((token_address, pubkey))
            logger.info(f"✅ Valid address: {token_address}")
        else:
            logger.error(f"❌ Invalid address: {token_address}")
    
    if not valid_addresses:
        logger.error("❌ No valid token addresses found")
        return False
    
    # Test 3: Get token prices
    logger.info("💰 Testing token price fetching...")
    
    for token_address, pubkey in valid_addresses:
        try:
            price = await get_token_price_sol(pubkey)
            if price:
                logger.info(f"✅ Price for {token_address}: {price:.8f} SOL")
            else:
                logger.warning(f"⚠️ No price data for {token_address}")
        except Exception as e:
            logger.error(f"❌ Error fetching price for {token_address}: {e}")
    
    # Test 4: Test buy functionality (with first valid token)
    # WARNING: This will actually attempt to buy tokens if uncommented
    # Uncomment only if you want to test actual trading
    """
    if valid_addresses:
        test_token_address = valid_addresses[0][0]
        logger.info(f"🛒 Testing buy functionality with {test_token_address}...")
        
        try:
            buy_result = await buy_token_solana(test_token_address)
            if buy_result:
                logger.info(f"✅ Buy test successful: {buy_result}")
                
                # Test 5: Test sell functionality
                logger.info("💸 Testing sell functionality...")
                sell_result = await sell_token_solana(
                    token_address=test_token_address,
                    amount_to_sell=buy_result['amount_bought_token'],
                    wallet_token_account=buy_result['wallet_token_account']
                )
                
                if sell_result:
                    logger.info(f"✅ Sell test successful: {sell_result}")
                else:
                    logger.error("❌ Sell test failed")
            else:
                logger.error("❌ Buy test failed")
        except Exception as e:
            logger.error(f"❌ Error in buy/sell test: {e}")
    """
    
    logger.info("🎉 All tests completed!")
    return True

def test_invalid_addresses():
    """Test validation with invalid addresses"""
    logger.info("🔍 Testing invalid address validation...")
    
    invalid_addresses = [
        "",  # Empty string
        "invalid_address",  # Too short
        "123456789012345678901234567890123456789012345",  # Too long
        "InvalidChars!@#$%^&*()_+",  # Invalid characters
        None,  # None value
        123,  # Not a string
    ]
    
    for invalid_addr in invalid_addresses:
        logger.info(f"Testing invalid address: {invalid_addr}")
        result = validate_token_address(invalid_addr)
        if result is None:
            logger.info(f"✅ Correctly rejected invalid address: {invalid_addr}")
        else:
            logger.error(f"❌ Incorrectly accepted invalid address: {invalid_addr}")

def main():
    """Main test function"""
    logger.info("🚀 Starting Solana service tests...")
    
    # Test invalid addresses first
    test_invalid_addresses()
    
    # Test main functionality
    try:
        asyncio.run(test_solana_service())
    except KeyboardInterrupt:
        logger.info("⏹️ Tests interrupted by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error in tests: {e}")
    
    logger.info("🏁 Tests finished")

if __name__ == "__main__":
    main()