"""
Instagram Account Creation using instagrapi API
No Selenium/Chrome needed - pure API-based approach.
"""

import time
import random
import string
import logging
import pyotp
from datetime import datetime
from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired,
    ChallengeError,
    FeedbackRequired,
    PleaseWaitFewMinutesError,
)
from temp_email import TempEmailManager
from config import *
from database import DatabaseUtils

logger = logging.getLogger(__name__)


def generate_username():
    """Generate a random Instagram-style username"""
    prefix = random.choice([
        "the", "real", "its", "im", "just", "not", "so", "official",
        "only", "one", "hey", "oh", "my", "mr", "dr", ""
    ])
    name = ''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 8)))
    suffix = random.choices(string.digits, k=random.randint(2, 4))
    return f"{prefix}{name}{''.join(suffix)}".strip()


def generate_fullname():
    """Generate a random full name"""
    first_names = [
        "James", "Emma", "Liam", "Olivia", "Noah", "Ava",
        "Ethan", "Sophia", "Mason", "Isabella", "Lucas", "Mia",
        "Logan", "Charlotte", "Alex", "Amelia", "Daniel", "Harper"
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
        "Miller", "Davis", "Rodriguez", "Martinez", "Wilson", "Anderson",
        "Taylor", "Thomas", "Moore", "Jackson", "Martin", "Lee"
    ]
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def create_instagram_account(use_temp_email=True, gmail_account=None, gmail_app_password=None):
    """
    Create an Instagram account using instagrapi API.

    Args:
        use_temp_email: If True, uses mail.tm disposable email (no Gmail needed)
        gmail_account: Optional Gmail address (if use_temp_email=False)
        gmail_app_password: Optional Gmail app password

    Returns:
        dict with account data, or None on failure
    """
    start_time = time.time()
    client = None
    email_manager = None

    try:
        DatabaseUtils.add_automation_log("info", "Starting Instagram account creation (instagrapi)")

        # Step 1: Get an email address
        if use_temp_email:
            DatabaseUtils.add_automation_log("info", "Creating temp email via mail.tm")
            email_manager = TempEmailManager()
            signup_email, email_password = email_manager.create_account()

            if not signup_email:
                raise Exception("Failed to create temporary email address")

            DatabaseUtils.add_automation_log("info", f"Temp email created: {signup_email}")
        else:
            signup_email = gmail_account
            email_password = gmail_app_password
            DatabaseUtils.add_automation_log("info", f"Using Gmail: {signup_email}")

        # Step 2: Initialize instagrapi client
        client = Client()
        client.delay_range = [1, 3]
        client.set_country('US')
        client.set_timezone_offset(-18000)
        client.device_id = client.generate_android_device_id()

        # Generate account details
        username = generate_username()
        password = STATIC_PASSWORD
        full_name = generate_fullname()

        DatabaseUtils.add_automation_log("info", f"Attempting signup: {username}")

        # Step 3: Sign up using instagrapi signup() method
        try:
            client.signup(
                username=username,
                password=password,
                email=signup_email,
                phone_number="",  # empty = email-based signup
                full_name=full_name
            )
            DatabaseUtils.add_automation_log("info", "Signup form submitted successfully")

        except (ChallengeRequired, CheckpointRequired) as challenge:
            DatabaseUtils.add_automation_log("info", f"Challenge required: {type(challenge).__name__}")

            # Handle the challenge - select email verification
            try:
                client.challenge_resolve(challenge)
            except Exception as ce:
                DatabaseUtils.add_automation_log("warning", f"challenge_resolve note: {ce}")

            # Select email as verification method
            try:
                client.challenge_select_verify_method('email')
                DatabaseUtils.add_automation_log("info", "Selected email verification")
            except Exception as e:
                DatabaseUtils.add_automation_log("debug", f"Select method note: {e}")

            # Request code to be sent
            try:
                client.challenge_send_code('email')
                DatabaseUtils.add_automation_log("info", "Verification code sent to email")
            except Exception as e:
                DatabaseUtils.add_automation_log("warning", f"Send code note: {e}")

            # Step 4: Get the OTP code
            otp_code = None

            if use_temp_email and email_manager:
                # Poll temp email inbox for OTP
                otp_code = email_manager.wait_for_otp(max_wait=120, poll_interval=10)

            elif gmail_account and gmail_app_password:
                # Read Gmail via IMAP for OTP
                otp_code = get_gmail_otp(gmail_account, gmail_app_password, max_retries=6)

            if not otp_code:
                raise Exception("Failed to retrieve verification code")

            DatabaseUtils.add_automation_log("info", f"OTP retrieved: {otp_code}")

            # Submit the code
            try:
                client.challenge_verify_code(otp_code)
                DatabaseUtils.add_automation_log("info", "Verification code accepted!")
            except Exception as verify_err:
                DatabaseUtils.add_automation_log("warning", f"Verify attempt: {verify_err}")
                try:
                    client.challenge_send_code_security_code(otp_code)
                    DatabaseUtils.add_automation_log("info", "Code submitted (alt method)")
                except Exception as e2:
                    raise Exception(f"Verification failed: {verify_err} / {e2}")

        except FeedbackRequired as fb:
            # Account might have been created but needs feedback
            error_text = fb.message if hasattr(fb, 'message') else str(fb)
            DatabaseUtils.add_automation_log("warning", f"Feedback required: {error_text}")

            # Check if signup actually worked
            try:
                client.login(signup_email, password)
                DatabaseUtils.add_automation_log("info", "Login after feedback succeeded - account exists")
            except:
                raise Exception(f"Account creation failed with feedback: {error_text}")

        except PleaseWaitFewMinutesError:
            raise Exception("Rate limited - Instagram says please wait a few minutes")

        except SignupError as se:
            raise Exception(f"Signup error: {se}")

        # Step 5: Get final username (Instagram might change it)
        try:
            user_info = client.user_info(client.user_id)
            final_username = user_info.username
        except:
            final_username = username

        DatabaseUtils.add_automation_log("info", f"Final username: {final_username}")

        # Step 6: Setup 2FA (TOTP)
        totp_secret = None
        try:
            totp_secret = client.two_factor_enable()
            if totp_secret:
                DatabaseUtils.add_automation_log("info", f"2FA enabled with secret: {totp_secret}")
        except Exception as e:
            DatabaseUtils.add_automation_log("warning", f"2FA setup failed (non-critical): {e}")

        # Step 7: Save to database
        processing_time = time.time() - start_time

        success = DatabaseUtils.add_instagram_account(
            username=final_username,
            email=signup_email,
            temp_email=signup_email,
            password=password,
            secret_key=totp_secret,
            status='successful',
            processing_time=processing_time
        )

        if success:
            DatabaseUtils.add_automation_log("info", f"Account saved to DB: {final_username}")

        account_data = {
            'username': final_username,
            'temp_email': signup_email,
            'password': password,
            'secret_key': totp_secret,
            'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'successful',
            'processing_time': processing_time
        }

        logger.info(f"Account created successfully: {final_username} in {processing_time:.1f}s")
        return account_data

    except PleaseWaitFewMinutesError as e:
        processing_time = time.time() - start_time
        error_msg = f"Rate limited: {str(e)}"
        logger.warning(error_msg)
        DatabaseUtils.add_instagram_account(
            username=f"rate_limited_{int(time.time())}",
            email=signup_email if use_temp_email else (gmail_account or "unknown"),
            temp_email=None,
            password=STATIC_PASSWORD,
            status='failed',
            processing_time=processing_time,
            error_message=error_msg
        )
        DatabaseUtils.add_automation_log("error", error_msg)
        return None

    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Account creation failed: {str(e)}"
        logger.error(error_msg)

        try:
            DatabaseUtils.add_instagram_account(
                username=f"failed_{int(time.time())}",
                email=signup_email if use_temp_email else (gmail_account or "unknown"),
                temp_email=None,
                password=STATIC_PASSWORD,
                status='failed',
                processing_time=processing_time,
                error_message=error_msg
            )
        except:
            pass

        DatabaseUtils.add_automation_log("error", error_msg)
        return None

    finally:
        # Cleanup
        if email_manager:
            try:
                email_manager.delete_account()
            except:
                pass


def get_gmail_otp(email_address, app_password, max_retries=6):
    """Read Gmail inbox via IMAP and extract 6-digit OTP code"""
    import imaplib
    import email as email_lib
    import re

    for attempt in range(max_retries):
        try:
            mail = imaplib.IMAP4_SSL('imap.gmail.com')
            mail.login(email_address, app_password)
            mail.select('inbox')

            # Search for Instagram emails
            status, messages = mail.search(None, '(FROM "instagram")')
            if not messages[0]:
                mail.close()
                mail.logout()
                time.sleep(10)
                continue

            # Get latest email
            latest_id = messages[0].split()[-1]
            status, msg_data = mail.fetch(latest_id, '(RFC822)')

            email_body = msg_data[0][1].decode('utf-8', errors='ignore')
            msg = email_lib.message_from_string(email_body)

            # Extract OTP from all parts
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type in ("text/plain", "text/html"):
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    match = re.search(r'\b(\d{6})\b', body)
                    if match:
                        code = match.group(1)
                        mail.close()
                        mail.logout()
                        return code

            mail.close()
            mail.logout()
            time.sleep(10)

        except Exception as e:
            logger.error(f"Gmail OTP error (attempt {attempt+1}): {e}")
            time.sleep(10)

    return None


def save_to_google_sheets(account_data):
    """Save account data to Google Sheets (optional)"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
        client = gspread.authorize(creds)

        spreadsheet = client.open(SPREADSHEET_NAME)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

        row_data = [
            account_data['username'],
            account_data['temp_email'],
            account_data['password'],
            account_data.get('secret_key', 'N/A'),
            account_data['created_at'],
            account_data['status']
        ]
        worksheet.append_row(row_data)
        logger.info("Saved to Google Sheets")

    except Exception as e:
        logger.debug(f"Google Sheets skipped: {e}")


# ========== State Management (kept for compatibility) ==========

def load_bot_state():
    try:
        bot_state = DatabaseUtils.get_bot_state()
        if bot_state:
            return {
                'is_running': bot_state.is_running,
                'current_index': bot_state.current_index,
                'total_processed': bot_state.total_processed,
                'successful': bot_state.successful_count,
                'failed': bot_state.failed_count,
                'started_at': bot_state.started_at.strftime('%Y-%m-%d %H:%M:%S') if bot_state.started_at else None,
                'last_updated': bot_state.last_updated.strftime('%Y-%m-%d %H:%M:%S') if bot_state.last_updated else None
            }
        return {
            'is_running': False, 'current_index': 0,
            'total_processed': 0, 'successful': 0, 'failed': 0,
            'started_at': None, 'last_updated': None
        }
    except Exception as e:
        logger.error(f"Load state error: {e}")
        return {
            'is_running': False, 'current_index': 0,
            'total_processed': 0, 'successful': 0, 'failed': 0,
            'started_at': None, 'last_updated': None
        }


def save_bot_state(state):
    try:
        started_at = None
        if state.get('started_at'):
            try:
                started_at = datetime.strptime(state['started_at'], '%Y-%m-%d %H:%M:%S')
            except:
                pass
        DatabaseUtils.update_bot_state(
            is_running=state.get('is_running'),
            current_index=state.get('current_index'),
            total_processed=state.get('total_processed'),
            successful_count=state.get('successful'),
            failed_count=state.get('failed'),
            started_at=started_at
        )
    except Exception as e:
        logger.error(f"Save state error: {e}")


def load_gmail_accounts():
    """Load Gmail accounts (kept for compatibility - now optional)"""
    try:
        accounts = DatabaseUtils.get_unused_gmail_accounts()
        return [{'email': acc.email, 'app_password': acc.app_password} for acc in accounts]
    except:
        return []


def load_static_password():
    return STATIC_PASSWORD
