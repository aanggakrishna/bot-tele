import re
import validators
from loguru import logger
from config import config

class CADetector:
    """Solana Contract Address (CA) detector"""
    
    # Regular expression patterns
    SOLANA_ADDRESS_PATTERN = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
    
    # Known domains for platforms
    PUMPFUN_DOMAINS = ['pump.fun', 'www.pump.fun', 'pumpfun.io']
    MOONSHOT_DOMAINS = ['moonshot.watch', 'moonshotwatch.io']
    
    def __init__(self):
        """Initialize CA detector"""
        self.patterns = {
            'solana': re.compile(self.SOLANA_ADDRESS_PATTERN)
        }
        
        # Stats
        self.stats = {
            'messages_processed': 0,
            'addresses_found': 0,
            'pumpfun_detected': 0,
            'moonshot_detected': 0, 
            'native_detected': 0
        }
    
    def detect_addresses(self, text):
        """Detect Solana addresses in text"""
        if not text:
            return []
        
        # Find all potential addresses
        addresses = self.patterns['solana'].findall(text)
        
        # Filter valid addresses (base58 check)
        valid_addresses = []
        for addr in addresses:
            # Crude validation: most Solana addresses are 32-44 chars, base58
            if validators.length(addr, min=32, max=44) and self._is_base58(addr):
                valid_addresses.append(addr)
        
        self.stats['addresses_found'] += len(valid_addresses)
        return valid_addresses
    
    def _is_base58(self, value):
        """Check if a string is base58 encoded"""
        try:
            # Base58 allowed chars
            return all(c in '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz' for c in value)
        except:
            return False
    
    def detect_platform(self, text, addresses):
        """Detect which platform the CA belongs to"""
        if not addresses:
            return []
        
        results = []
        
        # Process each address
        for address in addresses:
            # Default platform is "native" Solana
            platform = "native"
            confidence = 0.5  # Default confidence
            
            # Check for PumpFun indicators
            if config.ENABLE_PUMPFUN and self._is_pumpfun(text, address):
                platform = "pumpfun"
                confidence = 0.8
                self.stats['pumpfun_detected'] += 1
            
            # Check for Moonshot indicators
            elif config.ENABLE_MOONSHOT and self._is_moonshot(text, address):
                platform = "moonshot"
                confidence = 0.8
                self.stats['moonshot_detected'] += 1
            
            # Only count native if enabled
            elif config.ENABLE_NATIVE:
                self.stats['native_detected'] += 1
            else:
                continue  # Skip this address if native detection disabled
            
            results.append({
                'address': address,
                'platform': platform,
                'confidence': confidence
            })
        
        return results
    
    def _is_pumpfun(self, text, address):
        """Check if the address is from PumpFun"""
        # Check for PumpFun domains
        for domain in self.PUMPFUN_DOMAINS:
            if domain.lower() in text.lower():
                return True
                
        # Check for PumpFun keywords
        pumpfun_keywords = ['pumpfun', 'pump.fun', 'pump fun', 'buy on pf', 'listed on pf']
        for keyword in pumpfun_keywords:
            if keyword.lower() in text.lower():
                return True
        
        return False
    
    def _is_moonshot(self, text, address):
        """Check if the address is from Moonshot"""
        # Check for Moonshot domains
        for domain in self.MOONSHOT_DOMAINS:
            if domain.lower() in text.lower():
                return True
                
        # Check for Moonshot keywords
        moonshot_keywords = ['moonshot', 'moon shot', 'moonshotwatch', 'moonshot watch']
        for keyword in moonshot_keywords:
            if keyword.lower() in text.lower():
                return True
        
        return False
    
    def process_message(self, text, source=None):
        """Process message to detect CAs and platform"""
        if not text:
            return []
        
        self.stats['messages_processed'] += 1
        
        # Detect addresses
        addresses = self.detect_addresses(text)
        if not addresses:
            return []
        
        # Detect platform for each address
        results = self.detect_platform(text, addresses)
        
        # Log results
        if results:
            logger.info(f"📊 Found {len(results)} Solana addresses from {source or 'unknown'}")
            for ca in results:
                logger.debug(f"🔍 {ca['platform']} CA: {ca['address']}")
        
        return results