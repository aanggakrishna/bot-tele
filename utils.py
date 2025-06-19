import re
from typing import List
from loguru import logger

def extract_solana_addresses(text: str) -> List[str]:
    """Extract Solana token addresses from text"""
    patterns = [
        r'[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{44}',  # Solana base58
        r'[A-Za-z0-9]{40,50}',  # General base58
        r'(?:CA|Contract|Address|Token):\s*([A-Za-z0-9]{40,50})',  # Prefixed formats
    ]
    
    addresses = set()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            
            match = match.strip()
            if 40 <= len(match) <= 50:
                addresses.add(match)
    
    return list(addresses)

def detect_platform(text: str) -> str:
    """Detect trading platform from message text"""
    text_lower = text.lower()
    
    platforms = {
        'pumpfun': ['pump.fun', 'pumpfun', 'pump fun'],
        'moonshot': ['moonshot', 'moon shot'],
        'raydium': ['raydium', 'ray'],
        'jupiter': ['jupiter', 'jup'],
        'orca': ['orca'],
        'dexscreener': ['dexscreener', 'dex screener']
    }
    
    for platform, keywords in platforms.items():
        if any(keyword in text_lower for keyword in keywords):
            return platform
    
    return 'unknown'

def format_pnl(pnl_percent: float) -> str:
    """Format PNL percentage with emoji"""
    if pnl_percent > 0:
        return f"📈 +{pnl_percent:.2f}%"
    elif pnl_percent < 0:
        return f"📉 {pnl_percent:.2f}%"
    else:
        return f"➖ {pnl_percent:.2f}%"

def truncate_address(address: str, length: int = 8) -> str:
    """Truncate Solana address for display"""
    if len(address) <= length * 2:
        return address
    return f"{address[:length]}...{address[-length:]}"