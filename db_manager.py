from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    token_mint_address = Column(String, unique=True, index=True, nullable=False)
    platform = Column(String, nullable=True)  # pumpfun, moonshot, raydium, etc.
    buy_price_sol = Column(Float, nullable=False)
    amount_bought_token = Column(Float, nullable=False)
    buy_timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="active")  # active, sold_profit, sold_sl, sold_time
    sell_price_sol = Column(Float, nullable=True)
    sell_timestamp = Column(DateTime, nullable=True)
    wallet_token_account = Column(String, nullable=False)
    buy_tx_signature = Column(String, unique=True, nullable=True)
    sell_tx_signature = Column(String, nullable=True)
    bonding_curve_complete = Column(Boolean, nullable=True)  # For pump.fun tokens
    
    def __repr__(self):
        return f"<Trade(token={self.token_mint_address}, platform={self.platform}, status={self.status})>"

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./trading_bot.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize database and create tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def add_trade(db_session, token_mint_address, buy_price_sol, amount_bought_token, 
              wallet_token_account, buy_tx_signature, platform=None, bonding_curve_complete=None):
    """Add new trade to database"""
    trade = Trade(
        token_mint_address=token_mint_address,
        platform=platform,
        buy_price_sol=buy_price_sol,
        amount_bought_token=amount_bought_token,
        wallet_token_account=wallet_token_account,
        buy_tx_signature=buy_tx_signature,
        bonding_curve_complete=bonding_curve_complete
    )
    db_session.add(trade)
    db_session.commit()
    db_session.refresh(trade)
    return trade

def get_active_trades(db_session):
    """Get all active trades"""
    return db_session.query(Trade).filter(Trade.status == "active").all()

def get_total_active_trades_count(db_session):
    """Get count of active trades"""
    return db_session.query(Trade).filter(Trade.status == "active").count()

def update_trade_status(db_session, trade_id, status, sell_price_sol=None, sell_tx_signature=None):
    """Update trade status and sell information"""
    trade = db_session.query(Trade).filter(Trade.id == trade_id).first()
    if trade:
        trade.status = status
        trade.sell_timestamp = datetime.utcnow()
        if sell_price_sol:
            trade.sell_price_sol = sell_price_sol
        if sell_tx_signature:
            trade.sell_tx_signature = sell_tx_signature
        db_session.commit()
        db_session.refresh(trade)
    return trade

def get_trade_by_token(db_session, token_mint_address):
    """Get trade by token mint address"""
    return db_session.query(Trade).filter(Trade.token_mint_address == token_mint_address).first()