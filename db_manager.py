# db_manager.py
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timedelta

# Database file name
DATABASE_URL = "sqlite:///bot_trades.db"

# Base for declarative models
Base = declarative_base()

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    token_mint_address = Column(String, unique=True, index=True, nullable=False)
    # Ubah buy_price_usd menjadi buy_price_sol
    buy_price_sol = Column(Float, nullable=False) # Price of token in SOL at time of buy
    amount_bought_token = Column(Float, nullable=False)
    buy_timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="active") # "active", "sold_profit", "sold_sl", "sold_time", "failed"
    # Ubah sell_price_usd menjadi sell_price_sol
    sell_price_sol = Column(Float, nullable=True) # Price of token in SOL at time of sell
    sell_timestamp = Column(DateTime, nullable=True)
    wallet_token_account = Column(String, nullable=False) # ATA address
    buy_tx_signature = Column(String, unique=True, nullable=True)
    sell_tx_signature = Column(String, nullable=True)

    def __repr__(self):
        return f"<Trade(token_mint='{self.token_mint_address}', status='{self.status}', buy_price_sol={self.buy_price_sol})>"

# Database engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database initialized.")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Perbarui parameter fungsi ini
def add_trade(db_session, token_mint_address, buy_price_sol, amount_bought_token, wallet_token_account, buy_tx_signature):
    trade = Trade(
        token_mint_address=token_mint_address,
        buy_price_sol=buy_price_sol,
        amount_bought_token=amount_bought_token,
        wallet_token_account=wallet_token_account,
        buy_tx_signature=buy_tx_signature
    )
    db_session.add(trade)
    db_session.commit()
    db_session.refresh(trade)
    return trade

def get_active_trades(db_session):
    return db_session.query(Trade).filter(Trade.status == "active").all()

def get_trade_by_mint(db_session, token_mint_address):
    return db_session.query(Trade).filter(Trade.token_mint_address == token_mint_address).first()

# Perbarui parameter fungsi ini
def update_trade_status(db_session, trade_id, status, sell_price_sol=None, sell_tx_signature=None):
    trade = db_session.query(Trade).filter(Trade.id == trade_id).first()
    if trade:
        trade.status = status
        trade.sell_timestamp = datetime.utcnow()
        trade.sell_price_sol = sell_price_sol
        trade.sell_tx_signature = sell_tx_signature
        db_session.commit()
        db_session.refresh(trade)
    return trade

def get_total_active_trades_count(db_session):
    return db_session.query(Trade).filter(Trade.status == "active").count()

# Initialize the database when this module is imported
init_db()

if __name__ == '__main__':
    pass