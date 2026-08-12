from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import logging
import os
from config import DATABASE_URL

# Configure logging
logger = logging.getLogger(__name__)

# Create base class for models
Base = declarative_base()

class GmailAccount(Base):
    __tablename__ = 'gmail_accounts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    app_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class InstagramAccount(Base):
    __tablename__ = 'instagram_accounts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=True)
    email = Column(String(255), nullable=False)
    temp_email = Column(String(255), nullable=True)
    password = Column(String(255), nullable=False)
    secret_key = Column(String(255), nullable=True)
    status = Column(String(50), default='pending')
    processing_time = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BotState(Base):
    __tablename__ = 'bot_state'
    id = Column(Integer, primary_key=True, autoincrement=True)
    is_running = Column(Boolean, default=False)
    current_index = Column(Integer, default=0)
    total_processed = Column(Integer, default=0)
    successful_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AutomationLog(Base):
    __tablename__ = 'automation_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    account_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Database Manager Class
class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.setup_database()
    
    def setup_database(self):
        try:
            # SQLite needs check_same_thread=False for multi-threading
            if DATABASE_URL.startswith('sqlite'):
                self.engine = create_engine(
                    DATABASE_URL,
                    connect_args={'check_same_thread': False},
                    echo=False
                )
            else:
                from sqlalchemy.pool import QueuePool
                self.engine = create_engine(
                    DATABASE_URL,
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_recycle=3600,
                    echo=False
                )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            Base.metadata.create_all(bind=self.engine)
            logger.info(f"Database connected: {DATABASE_URL}")
        except Exception as e:
            logger.error(f"Error setting up database: {e}")
            raise
    
    def get_session(self):
        return self.SessionLocal()
    
    def test_connection(self):
        try:
            session = self.get_session()
            from sqlalchemy import text
            session.execute(text("SELECT 1"))
            session.close()
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

# Global database manager
db_manager = DatabaseManager()

# DatabaseUtils Class
class DatabaseUtils:
    @staticmethod
    def add_gmail_account(email, app_password):
        try:
            session = db_manager.get_session()
            account = GmailAccount(email=email, app_password=app_password)
            session.add(account)
            session.commit()
            session.close()
            logger.info(f"Added Gmail account: {email}")
            return True
        except Exception as e:
            logger.error(f"Error adding Gmail account: {e}")
            return False
    
    @staticmethod
    def get_all_gmail_accounts():
        try:
            session = db_manager.get_session()
            accounts = session.query(GmailAccount).filter(GmailAccount.is_active == True).all()
            session.close()
            return accounts
        except Exception as e:
            logger.error(f"Error getting Gmail accounts: {e}")
            return []
    
    @staticmethod
    def get_unused_gmail_accounts():
        try:
            session = db_manager.get_session()
            accounts = session.query(GmailAccount).filter(
                GmailAccount.is_active == True,
                GmailAccount.is_used == False
            ).all()
            session.close()
            return accounts
        except Exception as e:
            logger.error(f"Error getting unused Gmail accounts: {e}")
            return []
    
    @staticmethod
    def mark_gmail_account_used(email):
        try:
            session = db_manager.get_session()
            account = session.query(GmailAccount).filter(GmailAccount.email == email).first()
            if account:
                account.is_used = True
                account.updated_at = datetime.utcnow()
                session.commit()
            session.close()
            return True
        except Exception as e:
            logger.error(f"Error marking Gmail account as used: {e}")
            return False
    
    @staticmethod
    def add_instagram_account(username, email, temp_email, password, secret_key=None, 
                               status='successful', processing_time=None, error_message=None):
        try:
            session = db_manager.get_session()
            account = InstagramAccount(
                username=username,
                email=email,
                temp_email=temp_email,
                password=password,
                secret_key=secret_key,
                status=status,
                processing_time=processing_time,
                error_message=error_message
            )
            session.add(account)
            session.commit()
            session.close()
            logger.info(f"Added Instagram account: {username}")
            return True
        except Exception as e:
            logger.error(f"Error adding Instagram account: {e}")
            return False
    
    @staticmethod
    def get_instagram_accounts(status=None):
        try:
            session = db_manager.get_session()
            query = session.query(InstagramAccount)
            if status:
                query = query.filter(InstagramAccount.status == status)
            accounts = query.order_by(InstagramAccount.created_at.desc()).all()
            session.close()
            return accounts
        except Exception as e:
            logger.error(f"Error getting Instagram accounts: {e}")
            return []
    
    @staticmethod
    def get_bot_state():
        try:
            session = db_manager.get_session()
            state = session.query(BotState).first()
            if not state:
                state = BotState()
                session.add(state)
                session.commit()
            session.close()
            return state
        except Exception as e:
            logger.error(f"Error getting bot state: {e}")
            return None
    
    @staticmethod
    def update_bot_state(is_running=None, current_index=None, total_processed=None,
                         successful_count=None, failed_count=None, started_at=None):
        try:
            session = db_manager.get_session()
            state = session.query(BotState).first()
            if not state:
                state = BotState()
                session.add(state)
            if is_running is not None:
                state.is_running = is_running
            if current_index is not None:
                state.current_index = current_index
            if total_processed is not None:
                state.total_processed = total_processed
            if successful_count is not None:
                state.successful_count = successful_count
            if failed_count is not None:
                state.failed_count = failed_count
            if started_at is not None:
                state.started_at = started_at
            state.last_updated = datetime.utcnow()
            session.commit()
            session.close()
            return True
        except Exception as e:
            logger.error(f"Error updating bot state: {e}")
            return False
    
    @staticmethod
    def add_automation_log(level, message, account_id=None):
        try:
            session = db_manager.get_session()
            log = AutomationLog(level=level, message=message, account_id=account_id)
            session.add(log)
            session.commit()
            session.close()
            return True
        except Exception as e:
            logger.error(f"Error adding automation log: {e}")
            return False
    
    @staticmethod
    def get_recent_logs(limit=50):
        try:
            session = db_manager.get_session()
            logs = session.query(AutomationLog).order_by(
                AutomationLog.created_at.desc()
            ).limit(limit).all()
            session.close()
            return logs
        except Exception as e:
            logger.error(f"Error getting recent logs: {e}")
            return []
    
    @staticmethod
    def get_statistics():
        try:
            session = db_manager.get_session()
            total_accounts = session.query(InstagramAccount).count()
            successful_accounts = session.query(InstagramAccount).filter(
                InstagramAccount.status == 'successful'
            ).count()
            failed_accounts = session.query(InstagramAccount).filter(
                InstagramAccount.status == 'failed'
            ).count()
            pending_accounts = session.query(InstagramAccount).filter(
                InstagramAccount.status == 'pending'
            ).count()
            
            success_rate = 0
            if total_accounts > 0:
                success_rate = (successful_accounts / total_accounts) * 100
            
            session.close()
            return {
                'total': total_accounts,
                'successful': successful_accounts,
                'failed': failed_accounts,
                'pending': pending_accounts,
                'success_rate': round(success_rate, 2),
                'avg_processing_time': 0
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'pending': 0,
                'success_rate': 0,
                'avg_processing_time': 0
            }
