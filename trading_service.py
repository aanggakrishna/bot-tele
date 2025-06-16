import re
import asyncio
from loguru import logger
from typing import Optional, Dict, Any
import aiohttp
from solders.pubkey import Pubkey as PublicKey
import base58

class MultiPlatformTradingService:
    def __init__(self, solana_service):
        self.solana_service = solana_service
        
    async def detect_platform(self, token_address: str, message_text: str = "") -> str:
        """
        Detect which platform a token is from based on various indicators
        """
        # Check for platform-specific keywords in message
        message_lower = message_text.lower()
        
        if any(keyword in message_lower for keyword in ['pump.fun', 'pumpfun', 'pump fun', 'pump portal']):
            logger.info(f"Detected Pump.fun from message keywords")
            return 'pumpfun'
        elif any(keyword in message_lower for keyword in ['moonshot', 'moon shot', 'dexscreener.com/moonshot']):
            logger.info(f"Detected Moonshot from message keywords")
            return 'moonshot'
        elif any(keyword in message_lower for keyword in ['raydium', 'ray', 'dexscreener.com/solana']):
            logger.info(f"Detected Raydium from message keywords")
            return 'raydium'
        elif any(keyword in message_lower for keyword in ['jupiter', 'jup']):
            logger.info(f"Detected Jupiter from message keywords")
            return 'jupiter'
        
        # Try to detect based on token metadata or on-chain data
        try:
            platform = await self._detect_platform_from_metadata(token_address)
            return platform
        except Exception as e:
            logger.warning(f"Could not detect platform from metadata: {e}")
            return 'generic'
    
    async def _detect_platform_from_metadata(self, token_address: str) -> str:
        """
        Detect platform from token metadata
        """
        try:
            # Check if token exists on Jupiter (most comprehensive)
            async with aiohttp.ClientSession() as session:
                # Try Jupiter tokens API first
                async with session.get(f"https://quote-api.jup.ag/v6/tokens/{token_address}") as response:
                    if response.status == 200:
                        data = await response.json()
                        name = data.get('name', '').lower()
                        symbol = data.get('symbol', '').lower()
                        
                        # Check for platform indicators in name/symbol
                        if any(indicator in name or indicator in symbol for indicator in ['pump', 'pf']):
                            return 'pumpfun'
                        elif any(indicator in name or indicator in symbol for indicator in ['moon', 'ms']):
                            return 'moonshot'
                        else:
                            return 'generic'
                
                # Try Pump.fun API
                pump_api_url = f"https://frontend-api.pump.fun/coins/{token_address}"
                async with session.get(pump_api_url) as response:
                    if response.status == 200:
                        logger.info("Token found on Pump.fun API")
                        return 'pumpfun'
                
                return 'generic'
                
        except Exception as e:
            logger.error(f"Error detecting platform from metadata: {e}")
            return 'unknown'
    
    async def buy_token_multi_platform(self, token_address: str, message_text: str = "") -> Optional[Dict[str, Any]]:
        """
        Buy token using the appropriate method based on detected platform
        """
        platform = await self.detect_platform(token_address, message_text)
        logger.info(f"🔍 Detected platform: {platform.upper()} for token: {token_address}")
        
        try:
            if platform == 'pumpfun':
                return await self._buy_pumpfun_token(token_address)
            elif platform == 'moonshot':
                return await self._buy_moonshot_token(token_address)
            elif platform == 'raydium':
                return await self._buy_raydium_token(token_address)
            else:
                # Use generic Jupiter swap for unknown/generic tokens
                logger.info("Using generic Jupiter swap")
                result = await self.solana_service.buy_token_solana(token_address)
                if result:
                    result['platform'] = platform
                return result
                
        except Exception as e:
            logger.error(f"Error buying token from {platform}: {e}")
            return None
    
    async def _buy_pumpfun_token(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Buy token specifically from Pump.fun
        """
        logger.info(f"🚀 Buying Pump.fun token: {token_address}")
        
        try:
            # Check if token is still on bonding curve
            bonding_curve_info = await self._get_pumpfun_bonding_curve_info(token_address)
            
            if bonding_curve_info and bonding_curve_info.get('complete', False):
                logger.info("Token has graduated from bonding curve, using standard DEX trading")
            else:
                logger.info("Token is on bonding curve, using Jupiter which handles bonding curve tokens")
            
            # Use Jupiter which should handle both bonding curve and graduated tokens
            result = await self.solana_service.buy_token_solana(token_address)
            if result:
                result['platform'] = 'pumpfun'
                result['bonding_curve_complete'] = bonding_curve_info.get('complete', False) if bonding_curve_info else None
            return result
                
        except Exception as e:
            logger.error(f"Error in Pump.fun trading: {e}")
            return None
    
    async def _buy_moonshot_token(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Buy token from Moonshot platform
        """
        logger.info(f"🌙 Buying Moonshot token: {token_address}")
        
        try:
            # Moonshot tokens are usually standard SPL tokens that can be traded on DEXs
            result = await self.solana_service.buy_token_solana(token_address)
            if result:
                result['platform'] = 'moonshot'
            return result
            
        except Exception as e:
            logger.error(f"Error in Moonshot trading: {e}")
            return None
    
    async def _buy_raydium_token(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Buy token from Raydium DEX
        """
        logger.info(f"⚡ Buying Raydium token: {token_address}")
        
        try:
            # Raydium tokens can be traded through Jupiter
            result = await self.solana_service.buy_token_solana(token_address)
            if result:
                result['platform'] = 'raydium'
            return result
            
        except Exception as e:
            logger.error(f"Error in Raydium trading: {e}")
            return None
    
    async def _get_pumpfun_bonding_curve_info(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Get Pump.fun bonding curve information
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://frontend-api.pump.fun/coins/{token_address}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'complete': data.get('complete', False),
                            'market_cap': data.get('usd_market_cap', 0),
                            'created_timestamp': data.get('created_timestamp'),
                        }
            return None
            
        except Exception as e:
            logger.error(f"Error getting bonding curve info: {e}")
            return None

    async def sell_token_multi_platform(self, token_address: str, amount_to_sell: float, 
                                      wallet_token_account: str, platform: str = None) -> Optional[Dict[str, Any]]:
        """
        Sell token using appropriate method based on platform
        """
        if not platform:
            # Try to detect platform if not provided
            platform = await self.detect_platform(token_address)
        
        logger.info(f"💰 Selling {platform.upper()} token: {token_address}")
        
        try:
            # For now, all platforms can use Jupiter for selling
            result = await self.solana_service.sell_token_solana(token_address, amount_to_sell, wallet_token_account)
            if result:
                result['platform'] = platform
            return result
            
        except Exception as e:
            logger.error(f"Error selling {platform} token: {e}")
            return None

def extract_solana_ca_enhanced(message_text):
    """
    Enhanced Solana CA extraction with platform detection and multiple patterns
    """
    if not message_text:
        return None
        
    # Multiple patterns for different contexts
    patterns = [
        r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b',  # Standard base58
        r'(?:CA:?\s*|Contract:?\s*|Token:?\s*|Address:?\s*)([1-9A-HJ-NP-Za-km-z]{32,44})',  # With prefixes
        r'([1-9A-HJ-NP-Za-km-z]{32,44})(?:\s*(?:pump|moon|ray))',  # With platform suffix
        r'https?://[^\s]*?([1-9A-HJ-NP-Za-km-z]{32,44})',  # In URLs
    ]
    
    all_matches = []
    for pattern in patterns:
        matches = re.findall(pattern, message_text, re.IGNORECASE)
        # Handle tuple results from grouped patterns
        for match in matches:
            if isinstance(match, tuple):
                all_matches.extend([m for m in match if m])
            else:
                all_matches.append(match)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_matches = []
    for match in all_matches:
        if match not in seen:
            seen.add(match)
            unique_matches.append(match)
    
    if not unique_matches:
        logger.info("No potential Solana addresses found in message")
        return None
    
    logger.info(f"Found {len(unique_matches)} potential addresses: {unique_matches}")
    
    # Validate each match
    for match in unique_matches:
        validated = validate_and_clean_address(match)
        if validated:
            return validated
    
    logger.info("No valid Solana CA found after validation")
    return None

def validate_and_clean_address(address: str) -> Optional[str]:
    """
    Validate and clean Solana address
    """
    if not address:
        return None
        
    # Clean the address
    address = address.strip()
    
    # Skip if contains invalid characters
    if any(char in address for char in ['.', '/', ':', '@', '#', ' ', '\n', '\t', '?', '&', '=']):
        logger.debug(f"Skipping '{address}' - contains invalid characters")
        return None
        
    # Validate length
    if not (32 <= len(address) <= 44):
        logger.debug(f"Skipping '{address}' - invalid length: {len(address)}")
        return None
    
    # Validate base58 characters
    valid_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    if not all(c in valid_chars for c in address):
        logger.debug(f"Skipping '{address}' - contains invalid base58 characters")
        return None
    
    # Try to create PublicKey
    try:
        from solders.pubkey import Pubkey
        validated_pubkey = Pubkey.from_string(address)
        logger.info(f"✅ Valid Solana address: {address}")
        return address
    except Exception as e:
        logger.debug(f"Pubkey validation failed for '{address}': {e}")
        
        # Fallback to base58 validation
        try:
            decoded = base58.b58decode(address)
            if len(decoded) == 32:  # Solana address should be 32 bytes
                logger.info(f"✅ Valid Solana address (base58): {address}")
                return address
        except Exception as e2:
            logger.debug(f"Base58 validation failed for '{address}': {e2}")
    
    return None