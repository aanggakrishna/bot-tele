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

def get_table_columns(cursor, table_name: str) -> List[str]:
    """Get existing table columns"""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return columns
    except:
        return []

def init_db():
    """Initialize database with safe migration"""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            
            # Check if trades table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                # Create new table
                logger.info("📊 Creating new trades table...")
                cursor.execute("""
                    CREATE TABLE trades (
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
            else:
                # Check existing columns
                existing_columns = get_table_columns(cursor, 'trades')
                logger.info(f"📊 Existing columns: {existing_columns}")
                
                # Add missing columns if needed
                required_columns = {
                    'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                    'sold_at': 'TIMESTAMP',
                    'platform': 'TEXT DEFAULT "unknown"',
                    'sell_price_sol': 'REAL',
                    'sell_tx_signature': 'TEXT'
                }
                
                for column, column_type in required_columns.items():
                    if column not in existing_columns:
                        try:
                            logger.info(f"➕ Adding column: {column}")
                            cursor.execute(f"ALTER TABLE trades ADD COLUMN {column} {column_type}")
                        except sqlite3.OperationalError as e:
                            if "duplicate column name" not in str(e).lower():
                                logger.warning(f"⚠️ Could not add column {column}: {e}")
            
            # Create indexes (with IF NOT EXISTS)
            indexes = [
                ("idx_trades_status", "trades", "status"),
                ("idx_trades_token", "trades", "token_mint_address"),
                ("idx_trades_created", "trades", "created_at")
            ]
            
            for idx_name, table, column in indexes:
                try:
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
                except sqlite3.OperationalError as e:
                    logger.debug(f"Index {idx_name} might already exist: {e}")
            
            conn.commit()
            logger.info("✅ Database initialized successfully")
            
            # Show final table structure
            final_columns = get_table_columns(cursor, 'trades')
            logger.info(f"📋 Final table structure: {final_columns}")
            
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
        
        # Check what columns exist
        existing_columns = get_table_columns(cursor, 'trades')
        
        # Build query based on available columns
        if 'created_at' in existing_columns:
            cursor.execute("""
                INSERT INTO trades (
                    token_mint_address, platform, buy_price_sol, 
                    amount_bought_token, wallet_token_account, buy_tx_signature,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                token_mint_address, platform, buy_price_sol,
                amount_bought_token, wallet_token_account, buy_tx_signature
            ))
        else:
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
        
        # Check available columns
        existing_columns = get_table_columns(cursor, 'trades')
        
        cursor.execute("""
            SELECT * FROM trades 
            WHERE status = 'active' 
            ORDER BY id DESC
        """)
        
        rows = cursor.fetchall()
        trades = []
        
        for row in rows:
            # Safely get values with defaults
            created_at = None
            if 'created_at' in existing_columns and row['created_at']:
                try:
                    created_at = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
                except:
                    created_at = None
            
            sold_at = None
            if 'sold_at' in existing_columns and row['sold_at']:
                try:
                    sold_at = datetime.fromisoformat(row['sold_at'].replace('Z', '+00:00'))
                except:
                    sold_at = None
            
            trade = Trade(
                id=row['id'],
                token_mint_address=row['token_mint_address'],
                platform=row.get('platform', 'unknown'),
                buy_price_sol=row['buy_price_sol'],
                amount_bought_token=row['amount_bought_token'],
                wallet_token_account=row['wallet_token_account'],
                buy_tx_signature=row['buy_tx_signature'],
                sell_price_sol=row.get('sell_price_sol'),
                sell_tx_signature=row.get('sell_tx_signature'),
                status=row.get('status', 'active'),
                created_at=created_at,
                sold_at=sold_at
            )
            trades.append(trade)
        
        return trades
        
    except Exception as e:
        logger.error(f"❌ Get active trades error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return []

def get_trade_by_id(db, trade_id: int) -> Optional[Trade]:
    """Get trade by ID"""
    try:
        cursor = db.cursor()
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Check available columns
        existing_columns = get_table_columns(cursor, 'trades')
        
        # Safely get datetime values
        created_at = None
        if 'created_at' in existing_columns and row['created_at']:
            try:
                created_at = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
            except:
                created_at = None
        
        sold_at = None
        if 'sold_at' in existing_columns and row['sold_at']:
            try:
                sold_at = datetime.fromisoformat(row['sold_at'].replace('Z', '+00:00'))
            except:
                sold_at = None
        
        return Trade(
            id=row['id'],
            token_mint_address=row['token_mint_address'],
            platform=row.get('platform', 'unknown'),
            buy_price_sol=row['buy_price_sol'],
            amount_bought_token=row['amount_bought_token'],
            wallet_token_account=row['wallet_token_account'],
            buy_tx_signature=row['buy_tx_signature'],
            sell_price_sol=row.get('sell_price_sol'),
            sell_tx_signature=row.get('sell_tx_signature'),
            status=row.get('status', 'active'),
            created_at=created_at,
            sold_at=sold_at
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
        existing_columns = get_table_columns(cursor, 'trades')
        
        if status in ['sold_profit', 'sold_loss']:
            if 'sold_at' in existing_columns:
                cursor.execute("""
                    UPDATE trades 
                    SET status = ?, sell_price_sol = ?, sell_tx_signature = ?, sold_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, sell_price_sol, sell_tx_signature, trade_id))
            else:
                cursor.execute("""
                    UPDATE trades 
                    SET status = ?, sell_price_sol = ?, sell_tx_signature = ?
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
            ORDER BY id DESC 
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        trades = []
        existing_columns = get_table_columns(cursor, 'trades')
        
        for row in rows:
            # Safely get datetime values
            created_at = None
            if 'created_at' in existing_columns and row['created_at']:
                try:
                    created_at = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
                except:
                    created_at = None
            
            sold_at = None
            if 'sold_at' in existing_columns and row['sold_at']:
                try:
                    sold_at = datetime.fromisoformat(row['sold_at'].replace('Z', '+00:00'))
                except:
                    sold_at = None
            
            trade = Trade(
                id=row['id'],
                token_mint_address=row['token_mint_address'],
                platform=row.get('platform', 'unknown'),
                buy_price_sol=row['buy_price_sol'],
                amount_bought_token=row['amount_bought_token'],
                wallet_token_account=row['wallet_token_account'],
                buy_tx_signature=row['buy_tx_signature'],
                sell_price_sol=row.get('sell_price_sol'),
                sell_tx_signature=row.get('sell_tx_signature'),
                status=row.get('status', 'active'),
                created_at=created_at,
                sold_at=sold_at
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
        
        return {
            'total_trades': total_trades,
            'active_trades': active_trades,
            'profitable_trades': profitable_trades,
            'loss_trades': loss_trades,
            'total_profit': 0.0,
            'total_loss': 0.0,
            'net_pnl': 0.0
        }
        
    except Exception as e:
        logger.error(f"❌ Get trade stats error: {e}")
        return {}

def cleanup_old_trades(db, days: int = 30):
    """Clean up old completed trades"""
    try:
        cursor = db.cursor()
        existing_columns = get_table_columns(cursor, 'trades')
        
        if 'created_at' in existing_columns:
            cursor.execute("""
                DELETE FROM trades 
                WHERE status IN ('sold_profit', 'sold_loss', 'error') 
                AND created_at < datetime('now', '-{} days')
            """.format(days))
        else:
            # Fallback: delete by ID (keep recent ones)
            cursor.execute("""
                DELETE FROM trades 
                WHERE status IN ('sold_profit', 'sold_loss', 'error') 
                AND id < (SELECT MAX(id) FROM trades) - 100
            """)
        
        deleted_count = cursor.rowcount
        db.commit()
        
        if deleted_count > 0:
            logger.info(f"🧹 Cleaned up {deleted_count} old trades")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ Cleanup error: {e}")
        db.rollback()
        return 0

# Manual database reset function
def reset_database():
    """Reset database - USE WITH CAUTION!"""
    try:
        if os.path.exists(DATABASE_PATH):
            os.remove(DATABASE_PATH)
            logger.info("🗑️ Old database deleted")
        
        init_db()
        logger.info("✅ Database reset complete")
        
    except Exception as e:
        logger.error(f"❌ Database reset error: {e}")

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