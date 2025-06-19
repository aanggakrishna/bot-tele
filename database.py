import sqlite3
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
from contextlib import contextmanager
from loguru import logger
from config import config

@dataclass
class Trade:
    """Trade data model"""
    id: Optional[int] = None
    token_mint_address: str = ""
    platform: str = ""
    buy_price_sol: float = 0.0
    amount_bought_token: float = 0.0
    wallet_token_account: str = ""
    buy_tx_signature: str = ""
    sell_price_sol: Optional[float] = None
    sell_tx_signature: Optional[str] = None
    status: str = "active"  # active, sold_profit, sold_loss, error
    pnl_percent: Optional[float] = None
    created_at: Optional[datetime] = None
    sold_at: Optional[datetime] = None

def init_db():
    """Initialize database with tables"""
    try:
        with sqlite3.connect(config.DATABASE_PATH) as conn:
            cursor = conn.cursor()
            
            # Create trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_mint_address TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    buy_price_sol REAL NOT NULL,
                    amount_bought_token REAL NOT NULL,
                    wallet_token_account TEXT NOT NULL,
                    buy_tx_signature TEXT NOT NULL,
                    sell_price_sol REAL,
                    sell_tx_signature TEXT,
                    status TEXT DEFAULT 'active',
                    pnl_percent REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sold_at TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_token ON trades(token_mint_address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at)")
            
            # Create signals table for tracking detected CAs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_mint_address TEXT NOT NULL,
                    platform TEXT,
                    source_type TEXT NOT NULL, -- 'pin' or 'message'
                    source_id INTEGER NOT NULL,
                    message_text TEXT,
                    processed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            logger.info("✅ Database initialized successfully")
            
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        raise

@contextmanager
def get_db():
    """Get database connection with context manager"""
    conn = None
    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"❌ Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def save_signal(db, token_mint: str, platform: str, source_type: str, source_id: int, message_text: str) -> int:
    """Save detected signal to database"""
    try:
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO signals (token_mint_address, platform, source_type, source_id, message_text)
            VALUES (?, ?, ?, ?, ?)
        """, (token_mint, platform, source_type, source_id, message_text))
        
        db.commit()
        signal_id = cursor.lastrowid
        logger.info(f"📊 Signal saved with ID: {signal_id}")
        return signal_id
        
    except Exception as e:
        logger.error(f"❌ Save signal error: {e}")
        db.rollback()
        raise

def save_trade(db, token_mint_address: str, buy_price_sol: float, amount_bought_token: float,
               wallet_token_account: str, buy_tx_signature: str, platform: str = "unknown") -> int:
    """Save new trade to database"""
    try:
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO trades (
                token_mint_address, platform, buy_price_sol, 
                amount_bought_token, wallet_token_account, buy_tx_signature
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (token_mint_address, platform, buy_price_sol, amount_bought_token, wallet_token_account, buy_tx_signature))
        
        db.commit()
        trade_id = cursor.lastrowid
        logger.info(f"✅ Trade saved with ID: {trade_id}")
        return trade_id
        
    except Exception as e:
        logger.error(f"❌ Save trade error: {e}")
        db.rollback()
        raise

def get_active_trades(db) -> List[Trade]:
    """Get all active trades"""
    try:
        cursor = db.cursor()
        cursor.execute("""
            SELECT * FROM trades 
            WHERE status = 'active' 
            ORDER BY created_at DESC
        """)
        
        rows = cursor.fetchall()
        trades = []
        
        for row in rows:
            trade = Trade(
                id=row['id'],
                token_mint_address=row['token_mint_address'],
                platform=row['platform'],
                buy_price_sol=row['buy_price_sol'],
                amount_bought_token=row['amount_bought_token'],
                wallet_token_account=row['wallet_token_account'],
                buy_tx_signature=row['buy_tx_signature'],
                sell_price_sol=row['sell_price_sol'],
                sell_tx_signature=row['sell_tx_signature'],
                status=row['status'],
                pnl_percent=row['pnl_percent'],
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                sold_at=datetime.fromisoformat(row['sold_at']) if row['sold_at'] else None
            )
            trades.append(trade)
        
        return trades
        
    except Exception as e:
        logger.error(f"❌ Get active trades error: {e}")
        return []

def update_trade_status(db, trade_id: int, status: str, sell_price_sol: Optional[float] = None,
                       sell_tx_signature: Optional[str] = None, pnl_percent: Optional[float] = None):
    """Update trade status when selling"""
    try:
        cursor = db.cursor()
        
        if status in ['sold_profit', 'sold_loss']:
            cursor.execute("""
                UPDATE trades 
                SET status = ?, sell_price_sol = ?, sell_tx_signature = ?, 
                    pnl_percent = ?, sold_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, sell_price_sol, sell_tx_signature, pnl_percent, trade_id))
        else:
            cursor.execute("UPDATE trades SET status = ? WHERE id = ?", (status, trade_id))
        
        db.commit()
        logger.info(f"✅ Trade {trade_id} status updated to: {status}")
        
    except Exception as e:
        logger.error(f"❌ Update trade status error: {e}")
        db.rollback()
        raise

def get_trade_stats(db) -> dict:
    """Get trading statistics"""
    try:
        cursor = db.cursor()
        
        # Total trades
        cursor.execute("SELECT COUNT(*) as total FROM trades")
        total_trades = cursor.fetchone()['total']
        
        # Active trades
        cursor.execute("SELECT COUNT(*) as active FROM trades WHERE status = 'active'")
        active_trades = cursor.fetchone()['active']
        
        # Profitable trades
        cursor.execute("SELECT COUNT(*) as profitable FROM trades WHERE status = 'sold_profit'")
        profitable_trades = cursor.fetchone()['profitable']
        
        # Loss trades
        cursor.execute("SELECT COUNT(*) as loss FROM trades WHERE status = 'sold_loss'")
        loss_trades = cursor.fetchone()['loss']
        
        # Average PNL
        cursor.execute("SELECT AVG(pnl_percent) as avg_pnl FROM trades WHERE pnl_percent IS NOT NULL")
        avg_pnl = cursor.fetchone()['avg_pnl'] or 0
        
        return {
            'total_trades': total_trades,
            'active_trades': active_trades,
            'profitable_trades': profitable_trades,
            'loss_trades': loss_trades,
            'avg_pnl': avg_pnl,
            'win_rate': (profitable_trades / (profitable_trades + loss_trades) * 100) if (profitable_trades + loss_trades) > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"❌ Get trade stats error: {e}")
        return {}