import os
import sqlite3
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
from contextlib import contextmanager
from loguru import logger

# Database path
DATABASE_PATH = "trading_bot.db"

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
    created_at: Optional[datetime] = None
    sold_at: Optional[datetime] = None

def init_db():
    """Initialize database with tables"""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sold_at TIMESTAMP
                )
            """)
            
            # Create index for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_token ON trades(token_mint_address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at)
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
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"❌ Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def save_trade(
    db,
    token_mint_address: str,
    buy_price_sol: float,
    amount_bought_token: float,
    wallet_token_account: str,
    buy_tx_signature: str,
    platform: str = "unknown"
) -> int:
    """Save new trade to database"""
    try:
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO trades (
                token_mint_address, platform, buy_price_sol, 
                amount_bought_token, wallet_token_account, buy_tx_signature
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            token_mint_address, platform, buy_price_sol,
            amount_bought_token, wallet_token_account, buy_tx_signature
        ))
        
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
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                sold_at=datetime.fromisoformat(row['sold_at']) if row['sold_at'] else None
            )
            trades.append(trade)
        
        return trades
        
    except Exception as e:
        logger.error(f"❌ Get active trades error: {e}")
        return []

def get_trade_by_id(db, trade_id: int) -> Optional[Trade]:
    """Get trade by ID"""
    try:
        cursor = db.cursor()
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return Trade(
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
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            sold_at=datetime.fromisoformat(row['sold_at']) if row['sold_at'] else None
        )
        
    except Exception as e:
        logger.error(f"❌ Get trade by ID error: {e}")
        return None

def update_trade_status(
    db,
    trade_id: int,
    status: str,
    sell_price_sol: Optional[float] = None,
    sell_tx_signature: Optional[str] = None
):
    """Update trade status (sell)"""
    try:
        cursor = db.cursor()
        
        if status in ['sold_profit', 'sold_loss']:
            cursor.execute("""
                UPDATE trades 
                SET status = ?, sell_price_sol = ?, sell_tx_signature = ?, sold_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, sell_price_sol, sell_tx_signature, trade_id))
        else:
            cursor.execute("""
                UPDATE trades 
                SET status = ?
                WHERE id = ?
            """, (status, trade_id))
        
        db.commit()
        logger.info(f"✅ Trade {trade_id} status updated to: {status}")
        
    except Exception as e:
        logger.error(f"❌ Update trade status error: {e}")
        db.rollback()
        raise

def get_trade_history(db, limit: int = 50) -> List[Trade]:
    """Get trade history"""
    try:
        cursor = db.cursor()
        cursor.execute("""
            SELECT * FROM trades 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
        
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
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                sold_at=datetime.fromisoformat(row['sold_at']) if row['sold_at'] else None
            )
            trades.append(trade)
        
        return trades
        
    except Exception as e:
        logger.error(f"❌ Get trade history error: {e}")
        return []

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
        
        # Total profit/loss
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN status = 'sold_profit' THEN (sell_price_sol - buy_price_sol) * amount_bought_token ELSE 0 END) as total_profit,
                SUM(CASE WHEN status = 'sold_loss' THEN (buy_price_sol - sell_price_sol) * amount_bought_token ELSE 0 END) as total_loss
            FROM trades
        """)
        pnl_row = cursor.fetchone()
        total_profit = pnl_row['total_profit'] or 0
        total_loss = pnl_row['total_loss'] or 0
        
        return {
            'total_trades': total_trades,
            'active_trades': active_trades,
            'profitable_trades': profitable_trades,
            'loss_trades': loss_trades,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'net_pnl': total_profit - total_loss
        }
        
    except Exception as e:
        logger.error(f"❌ Get trade stats error: {e}")
        return {}

def cleanup_old_trades(db, days: int = 30):
    """Clean up old completed trades"""
    try:
        cursor = db.cursor()
        cursor.execute("""
            DELETE FROM trades 
            WHERE status IN ('sold_profit', 'sold_loss', 'error') 
            AND created_at < datetime('now', '-{} days')
        """.format(days))
        
        deleted_count = cursor.rowcount
        db.commit()
        
        if deleted_count > 0:
            logger.info(f"🧹 Cleaned up {deleted_count} old trades")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ Cleanup error: {e}")
        db.rollback()
        return 0

# Test database functions
if __name__ == "__main__":
    # Test database setup
    logger.info("🧪 Testing database...")
    
    try:
        # Initialize
        init_db()
        
        # Test connection
        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM trades")
            count = cursor.fetchone()['count']
            logger.info(f"📊 Current trades in database: {count}")
            
            # Test stats
            stats = get_trade_stats(db)
            logger.info(f"📈 Stats: {stats}")
        
        logger.info("✅ Database test successful!")
        
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")