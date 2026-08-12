import time
import logging
from datetime import datetime
from instagram_automation import create_instagram_account, load_gmail_accounts, load_static_password, save_to_google_sheets
from database import DatabaseUtils

logger = logging.getLogger(__name__)


def load_bot_state():
    """Load bot state from database"""
    try:
        state_obj = DatabaseUtils.get_bot_state()
        if state_obj:
            return {
                'is_running': state_obj.is_running,
                'current_index': state_obj.current_index,
                'total_processed': state_obj.total_processed,
                'successful': state_obj.successful_count,
                'failed': state_obj.failed_count,
                'started_at': state_obj.started_at.strftime('%Y-%m-%d %H:%M:%S') if state_obj.started_at else None,
                'last_updated': state_obj.last_updated.strftime('%Y-%m-%d %H:%M:%S') if state_obj.last_updated else None
            }
        return {
            'is_running': False, 'current_index': 0,
            'total_processed': 0, 'successful': 0, 'failed': 0,
            'started_at': None, 'last_updated': None
        }
    except Exception as e:
        logger.error(f"Error loading bot state: {e}")
        return {
            'is_running': False, 'current_index': 0,
            'total_processed': 0, 'successful': 0, 'failed': 0,
            'started_at': None, 'last_updated': None
        }


def save_bot_state(state):
    """Save bot state to database"""
    try:
        started_at = None
        if state.get('started_at'):
            try:
                started_at = datetime.strptime(state['started_at'], '%Y-%m-%d %H:%M:%S')
            except:
                pass
        DatabaseUtils.update_bot_state(
            is_running=state.get('is_running', False),
            current_index=state.get('current_index', 0),
            total_processed=state.get('total_processed', 0),
            successful_count=state.get('successful', 0),
            failed_count=state.get('failed', 0),
            started_at=started_at
        )
        return True
    except Exception as e:
        logger.error(f"Error saving bot state: {e}")
        return False


def get_gmail_accounts():
    """Get unused Gmail accounts"""
    try:
        accounts = DatabaseUtils.get_unused_gmail_accounts()
        return [{'email': acc.email, 'app_password': acc.app_password} for acc in accounts]
    except Exception as e:
        logger.error(f"Error getting Gmail accounts: {e}")
        return []


def get_all_gmail_accounts():
    """Get all Gmail accounts"""
    try:
        accounts = DatabaseUtils.get_all_gmail_accounts()
        return [{'email': acc.email, 'app_password': acc.app_password, 'is_used': acc.is_used} for acc in accounts]
    except Exception as e:
        logger.error(f"Error getting all Gmail accounts: {e}")
        return []


def get_instagram_accounts(status=None):
    """Get Instagram accounts from database"""
    try:
        return DatabaseUtils.get_instagram_accounts(status)
    except Exception as e:
        logger.error(f"Error getting Instagram accounts: {e}")
        return []


def get_statistics():
    """Get automation statistics"""
    try:
        return DatabaseUtils.get_statistics()
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return {'total': 0, 'successful': 0, 'failed': 0, 'pending': 0, 'success_rate': 0, 'avg_processing_time': 0}


def add_gmail_account(email, app_password):
    """Add Gmail account to database"""
    try:
        return DatabaseUtils.add_gmail_account(email, app_password)
    except Exception as e:
        logger.error(f"Error adding Gmail account: {e}")
        return False


def mark_gmail_account_used(email):
    """Mark Gmail account as used"""
    try:
        return DatabaseUtils.mark_gmail_account_used(email)
    except Exception as e:
        logger.error(f"Error marking Gmail account as used: {e}")
        return False


def get_recent_logs(limit=50):
    """Get recent automation logs"""
    try:
        return DatabaseUtils.get_recent_logs(limit)
    except Exception as e:
        logger.error(f"Error getting recent logs: {e}")
        return []


def add_automation_log(level, message, account_id=None):
    """Add automation log entry"""
    try:
        return DatabaseUtils.add_automation_log(level, message, account_id)
    except Exception as e:
        logger.error(f"Error adding automation log: {e}")
        return False
