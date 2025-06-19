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
        with sqlite3.connect(config.DATABASE_PATH) as conn:
            cursor = conn.cursor()
            
            # Check if trades table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                # Create new table with all columns
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
                        pnl_percent REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        sold_at TIMESTAMP
                    )
                """)
                logger.info("✅ New trades table created")
            else:
                # Check existing columns and add missing ones
                existing_columns = get_table_columns(cursor, 'trades')
                logger.info(f"📊 Existing columns: {existing_columns}")
                
                # Define required columns with their types
                required_columns = {
                    'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                    'sold_at': 'TIMESTAMP',
                    'platform': 'TEXT DEFAULT "unknown"',
                    'sell_price_sol': 'REAL',
                    'sell_tx_signature': 'TEXT',
                    'pnl_percent': 'REAL',
                    'status': 'TEXT DEFAULT "active"'
                }
                
                # Add missing columns
                for column, column_type in required_columns.items():
                    if column not in existing_columns:
                        try:
                            logger.info(f"➕ Adding column: {column}")
                            cursor.execute(f"ALTER TABLE trades ADD COLUMN {column} {column_type}")
                        except sqlite3.OperationalError as e:
                            if "duplicate column name" not in str(e).lower():
                                logger.warning(f"⚠️ Could not add column {column}: {e}")
            
            # Create signals table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
            signals_exists = cursor.fetchone() is not None
            
            if not signals_exists:
                logger.info("📊 Creating signals table...")
                cursor.execute("""
                    CREATE TABLE signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        token_mint_address TEXT NOT NULL,
                        platform TEXT,
                        source_type TEXT NOT NULL,
                        source_id INTEGER NOT NULL,
                        message_text TEXT,
                        processed BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.info("✅ Signals table created")
            
            # Create indexes (with IF NOT EXISTS)
            indexes = [
                ("idx_trades_status", "trades", "status"),
                ("idx_trades_token", "trades", "token_mint_address"),
                ("idx_trades_created", "trades", "created_at"),
                ("idx_signals_processed", "signals", "processed"),
                ("idx_signals_token", "signals", "token_mint_address")
            ]
            
            for idx_name, table, columns in indexes:
                try:
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({columns})")
                except sqlite3.OperationalError as e:
                    logger.debug(f"Index {idx_name} might already exist: {e}")
            
            conn.commit()
            logger.info("✅ Database initialized successfully")
            
            # Show final table structure
            final_columns = get_table_columns(cursor, 'trades')
            logger.info(f"📋 Final trades table: {final_columns}")
            
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
            """, (token_mint_address, platform, buy_price_sol, amount_bought_token, wallet_token_account, buy_tx_signature))
        else:
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
        
        # Check available columns
        existing_columns = get_table_columns(cursor, 'trades')
        
        cursor.execute("""
            SELECT * FROM trades 
            WHERE status = 'active' OR status IS NULL
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
                pnl_percent=row.get('pnl_percent'),
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

def update_trade_status(db, trade_id: int, status: str, sell_price_sol: Optional[float] = None,
                       sell_tx_signature: Optional[str] = None, pnl_percent: Optional[float] = None):
    """Update trade status when selling"""
    try:
        cursor = db.cursor()
        existing_columns = get_table_columns(cursor, 'trades')
        
        if status in ['sold_profit', 'sold_loss']:
            if 'sold_at' in existing_columns and 'pnl_percent' in existing_columns:
                cursor.execute("""
                    UPDATE trades 
                    SET status = ?, sell_price_sol = ?, sell_tx_signature = ?, 
                        pnl_percent = ?, sold_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, sell_price_sol, sell_tx_signature, pnl_percent, trade_id))
            else:
                cursor.execute("""
                    UPDATE trades 
                    SET status = ?, sell_price_sol = ?, sell_tx_signature = ?
                    WHERE id = ?
                """, (status, sell_price_sol, sell_tx_signature, trade_id))
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
        cursor.execute("SELECT COUNT(*) as active FROM trades WHERE status = 'active' OR status IS NULL")
        active_trades = cursor.fetchone()['active']
        
        # Profitable trades
        cursor.execute("SELECT COUNT(*) as profitable FROM trades WHERE status = 'sold_profit'")
        profitable_trades = cursor.fetchone()['profitable']
        
        # Loss trades
        cursor.execute("SELECT COUNT(*) as loss FROM trades WHERE status = 'sold_loss'")
        loss_trades = cursor.fetchone()['loss']
        
        # Check if pnl_percent column exists
        existing_columns = get_table_columns(cursor, 'trades')
        avg_pnl = 0
        if 'pnl_percent' in existing_columns:
            cursor.execute("SELECT AVG(pnl_percent) as avg_pnl FROM trades WHERE pnl_percent IS NOT NULL")
            result = cursor.fetchone()
            avg_pnl = result['avg_pnl'] or 0
        
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

def reset_database():
    """Reset database - USE WITH CAUTION!"""
    try:
        import os
        if os.path.exists(config.DATABASE_PATH):
            os.remove(config.DATABASE_PATH)
            logger.info("🗑️ Old database deleted")
        
        init_db()
        logger.info("✅ Database reset complete")
        
    except Exception as e:
        logger.error(f"❌ Database reset error: {e}")

# Test database functions
if __name__ == "__main__":
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