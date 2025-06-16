import re
import base58
from typing import Optional, Dict
from loguru import logger
from solders.pubkey import Pubkey

class MultiPlatformTradingService:
    def __init__(self, solana_service):
        self.solana_service = solana_service
        
    async def buy_token_multi_platform(self, token_mint: str, message_text: str) -> Optional[Dict]:
        """Buy token from detected platform"""
        try:
            # Validate token address
            if not self.is_valid_solana_address(token_mint):  # Make it public
                logger.error(f"❌ Invalid token address: {token_mint}")
                return None
            
            # Detect platform
            platform = self._detect_platform(message_text)
            logger.info(f"🎯 Detected platform: {platform}")
            
            # Use solana service to buy
            buy_result = await self.solana_service.buy_token(token_mint)
            
            if buy_result:
                # Add platform info
                buy_result['platform'] = platform
                buy_result['bonding_curve_complete'] = False
                
            return buy_result
            
        except Exception as e:
            logger.error(f"❌ Error buying token {token_mint}: {e}")
            return None
    
    async def sell_token_multi_platform(self, token_mint: str, amount: float, 
                                      wallet_account: str, platform: str) -> Optional[Dict]:
        """Sell token from platform"""
        try:
            if not self.is_valid_solana_address(token_mint):  # Make it public
                logger.error(f"❌ Invalid token address: {token_mint}")
                return None
            
            return await self.solana_service.sell_token(token_mint, amount, wallet_account)
            
        except Exception as e:
            logger.error(f"❌ Error selling token {token_mint}: {e}")
            return None
    
    def _detect_platform(self, message_text: str) -> str:
        """Detect platform from message"""
        message_lower = message_text.lower()
        
        if 'pump.fun' in message_lower or 'pumpfun' in message_lower:
            return 'pumpfun'
        elif 'moonshot' in message_lower:
            return 'moonshot'
        elif 'raydium' in message_lower:
            return 'raydium'
        else:
            return 'pumpfun'  # Default
    
    def is_valid_solana_address(self, address: str) -> bool:  # Make it public (remove _)
        """Validate Solana address"""
        try:
            if not (32 <= len(address) <= 44):
                return False
            
            decoded = base58.b58decode(address)
            if len(decoded) != 32:
                return False
            
            Pubkey.from_string(address)
            return True
            
        except Exception:
            return False

def extract_solana_ca_enhanced(text: str) -> Optional[str]:
    """Extract valid Solana CA from text"""
    # Pattern for Solana addresses
    pattern = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
    matches = re.findall(pattern, text)
    
    for match in matches:
        # Skip common addresses
        if match.startswith('So1111111111111111111111111111111111111111'):
            continue
        
        # Skip all same character
        if all(c == match[0] for c in match):
            continue
        
        # Validate format
        try:
            decoded = base58.b58decode(match)
            if len(decoded) == 32:
                Pubkey.from_string(match)
                logger.debug(f"✅ Valid CA found: {match}")
                return match
        except Exception:
            continue
    
    return None

# Add a simple validation function for use in main.py
def is_valid_solana_address(address: str) -> bool:
    """Standalone function to validate Solana address"""
    try:
        if not (32 <= len(address) <= 44):
            return False
        
        decoded = base58.b58decode(address)
        if len(decoded) != 32:
            return False
        
        Pubkey.from_string(address)
        return True
        
    except Exception:
        return False