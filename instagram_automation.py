import time
import json
import imaplib
import email
import re
import requests
import os
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
import pyotp
from config import *
from database import DatabaseUtils

# Configure logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def init_driver():
    """Initialize Chrome WebDriver for Heroku/Server environments"""
    try:
        options = Options()

        # Headless mode - required for Heroku
        if HEADLESS_MODE:
            options.add_argument('--headless=new')

        # Required arguments for server/CI environments
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--remote-debugging-port=9222')

        # Stability arguments
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--window-size=1920,1080')

        # Set user agent to avoid detection
        options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        # Binary location for Heroku
        chrome_bin = os.getenv('GOOGLE_CHROME_BIN', '')
        if chrome_bin:
            options.binary_location = chrome_bin

        # Additional prefs
        prefs = {
            'profile.default_content_setting_values.notifications': 2,
            'credentials_enable_service': False,
            'profile.password_manager_enabled': False
        }
        options.add_experimental_option('prefs', prefs)

        # Find chromium binary and chromedriver
        import shutil
        chromium_bin = shutil.which('chromium') or shutil.which('chromium-browser') or shutil.which('google-chrome') or os.getenv('CHROME_BIN', '')
        if chromium_bin:
            options.binary_location = chromium_bin

        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(10)
        driver.set_page_load_timeout(30)

        logger.info("Chrome WebDriver initialized successfully")
        return driver

    except Exception as e:
        logger.error(f"Error initializing Chrome WebDriver: {e}")
        raise


def get_gmail_code(email_address, app_password):
    """Extract 6-digit verification code from Gmail"""
    try:
        # Connect to Gmail IMAP server
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_address, app_password)
        mail.select('inbox')

        # Search for Instagram verification emails
        status, messages = mail.search(None, 'FROM', 'instagram.com')
        if not messages[0]:
            return None

        # Get the latest email
        latest_email_id = messages[0].split()[-1]
        status, msg_data = mail.fetch(latest_email_id, '(RFC822)')

        # Parse email content
        email_body = msg_data[0][1].decode('utf-8')
        msg = email.message_from_string(email_body)

        # Extract verification code
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode('utf-8')
                    code_match = re.search(r'\b(\d{6})\b', body)
                    if code_match:
                        mail.close()
                        mail.logout()
                        return code_match.group(1)

        mail.close()
        mail.logout()
        return None

    except Exception as e:
        logger.error(f"Error getting Gmail code: {e}")
        return None


def get_temp_email():
    """Get temporary email from mailvn.site"""
    try:
        response = requests.get('https://mailvn.site', timeout=15)
        if response.status_code == 200:
            # Extract email from response
            email_match = re.search(r'([a-zA-Z0-9._%+-]+@mailvn\.site)', response.text)
            if email_match:
                return email_match.group(1)
        return None
    except Exception as e:
        logger.error(f"Error getting temp email: {e}")
        return None


def download_profile_image():
    """Download AI-generated profile image"""
    try:
        # Using thispersondoesnotexist.com for AI-generated faces
        response = requests.get('https://thispersondoesnotexist.com/image', timeout=20)
        if response.status_code == 200:
            image_path = '/tmp/profile.jpg'
            with open(image_path, 'wb') as f:
                f.write(response.content)
            return image_path
        return None
    except Exception as e:
        logger.error(f"Error downloading profile image: {e}")
        return None


def create_instagram_account(gmail_account, app_password, static_password):
    """Main function to create Instagram account"""
    driver = None
    start_time = time.time()

    try:
        # Log the start of account creation
        DatabaseUtils.add_automation_log("info", f"Starting Instagram account creation for {gmail_account}")

        # Initialize WebDriver
        driver = init_driver()

        # Step 1: Instagram Signup
        logger.info("Starting Instagram signup process")
        DatabaseUtils.add_automation_log("info", "Navigating to Instagram signup page")

        driver.get('https://www.instagram.com/accounts/emailsignup/')
        time.sleep(3)

        # Fill signup form
        email_field = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "emailOrPhone"))
        )
        email_field.send_keys(gmail_account)

        fullname_field = driver.find_element(By.NAME, "fullName")
        fullname_field.send_keys("John Doe")

        username_field = driver.find_element(By.NAME, "username")
        random_num = int(time.time())
        username_field.send_keys(f"user_{random_num}")

        password_field = driver.find_element(By.NAME, "password")
        password_field.send_keys(static_password)

        # Submit form
        signup_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        signup_button.click()

        DatabaseUtils.add_automation_log("info", "Instagram signup form submitted")

        # Step 2: Email Verification
        logger.info("Waiting for email verification")
        time.sleep(5)

        # Get verification code from Gmail (retry up to 3 times)
        verification_code = None
        for attempt in range(3):
            verification_code = get_gmail_code(gmail_account, app_password)
            if verification_code:
                break
            logger.info(f"Waiting for verification code... attempt {attempt + 1}/3")
            time.sleep(10)

        if not verification_code:
            error_msg = "Failed to get verification code from Gmail after 3 attempts"
            DatabaseUtils.add_automation_log("error", error_msg)
            raise Exception(error_msg)

        DatabaseUtils.add_automation_log("info", f"Retrieved verification code: {verification_code}")

        # Enter verification code
        try:
            code_field = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.NAME, "email_confirmation_code"))
            )
            code_field.send_keys(verification_code)

            # Submit verification
            verify_button = driver.find_element(By.XPATH, "//button[@type='submit']")
            verify_button.click()
        except TimeoutException:
            # Try alternative code input
            try:
                code_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='tel']")
                for i, digit in enumerate(verification_code):
                    code_inputs[i].send_keys(digit)
                time.sleep(2)
            except Exception as e:
                logger.warning(f"Alternative code input failed: {e}")

        DatabaseUtils.add_automation_log("info", "Email verification completed")

        # Step 3: Profile Setup
        logger.info("Setting up profile")
        time.sleep(5)

        # Download and upload profile picture
        profile_image_path = download_profile_image()
        if profile_image_path:
            try:
                file_input = driver.find_element(By.XPATH, "//input[@type='file']")
                file_input.send_keys(profile_image_path)
                time.sleep(3)

                # Click next/skip buttons
                try:
                    next_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Next')]")
                    next_button.click()
                    time.sleep(2)
                except NoSuchElementException:
                    pass

                try:
                    skip_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Skip')]")
                    skip_button.click()
                except NoSuchElementException:
                    pass

                DatabaseUtils.add_automation_log("info", "Profile picture uploaded successfully")
            except Exception as e:
                logger.warning(f"Profile picture upload failed: {e}")
                DatabaseUtils.add_automation_log("warning", f"Profile picture upload failed: {e}")

        # Step 4: Get final username
        try:
            final_username = driver.find_element(By.XPATH, "//h2").text
        except:
            final_username = f"user_{random_num}"

        DatabaseUtils.add_automation_log("info", f"Instagram username: {final_username}")

        # Step 5: Email Replacement
        logger.info("Replacing email with temporary email")
        temp_email = get_temp_email()
        if not temp_email:
            temp_email = f"temp_{random_num}@mailvn.site"
            DatabaseUtils.add_automation_log("warning", "Using fallback temporary email")
        DatabaseUtils.add_automation_log("info", f"Temporary email: {temp_email}")

        # Step 6: 2FA Setup
        logger.info("Setting up 2FA")
        secret_key = None
        try:
            driver.get('https://www.instagram.com/accounts/two_factor_authentication/')
            time.sleep(3)

            auth_app_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Authentication App')]")
            auth_app_button.click()
            time.sleep(3)

            secret_key_element = driver.find_element(By.XPATH, "//code")
            secret_key = secret_key_element.text

            confirm_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Confirm')]")
            confirm_button.click()

            DatabaseUtils.add_automation_log("info", f"2FA setup completed with key: {secret_key}")
        except Exception as e:
            logger.warning(f"2FA setup failed: {e}")
            DatabaseUtils.add_automation_log("warning", f"2FA setup failed: {e}")

        # Calculate processing time
        processing_time = time.time() - start_time

        # Save account data to database
        success = DatabaseUtils.add_instagram_account(
            username=final_username,
            email=gmail_account,
            temp_email=temp_email,
            password=static_password,
            secret_key=secret_key,
            status='successful',
            processing_time=processing_time
        )

        if success:
            DatabaseUtils.mark_gmail_account_used(gmail_account)
            DatabaseUtils.add_automation_log("info", f"Account created successfully: {final_username}")

            account_data = {
                'username': final_username,
                'temp_email': temp_email,
                'password': static_password,
                'secret_key': secret_key,
                'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'successful',
                'processing_time': processing_time
            }

            logger.info(f"Account created successfully: {final_username}")
            return account_data
        else:
            raise Exception("Failed to save account data to database")

    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Error creating Instagram account: {e}"
        logger.error(error_msg)

        DatabaseUtils.add_instagram_account(
            username=f"failed_{int(time.time())}",
            email=gmail_account,
            temp_email=None,
            password=static_password,
            secret_key=None,
            status='failed',
            processing_time=processing_time,
            error_message=str(e)
        )

        DatabaseUtils.add_automation_log("error", error_msg)
        return None

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def save_to_google_sheets(account_data):
    """Save account data to Google Sheets"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        # Authenticate with Google Sheets
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
        client = gspread.authorize(creds)

        # Open spreadsheet
        spreadsheet = client.open(SPREADSHEET_NAME)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

        # Append data
        row_data = [
            account_data['username'],
            account_data['temp_email'],
            account_data['password'],
            account_data['secret_key'],
            account_data['created_at'],
            account_data['status']
        ]

        worksheet.append_row(row_data)
        logger.info("Account data saved to Google Sheets")

    except Exception as e:
        logger.error(f"Error saving to Google Sheets: {e}")


def load_bot_state():
    """Load bot state from database"""
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
            'is_running': False,
            'current_index': 0,
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'started_at': None,
            'last_updated': None
        }
    except Exception as e:
        logger.error(f"Error loading bot state: {e}")
        return {
            'is_running': False,
            'current_index': 0,
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'started_at': None,
            'last_updated': None
        }


def save_bot_state(state):
    """Save bot state to database"""
    try:
        DatabaseUtils.update_bot_state(
            is_running=state.get('is_running'),
            current_index=state.get('current_index'),
            total_processed=state.get('total_processed'),
            successful_count=state.get('successful'),
            failed_count=state.get('failed'),
            started_at=datetime.strptime(state['started_at'], '%Y-%m-%d %H:%M:%S') if state.get('started_at') else None
        )
    except Exception as e:
        logger.error(f"Error saving bot state: {e}")


def load_gmail_accounts():
    """Load Gmail accounts from database"""
    try:
        accounts = DatabaseUtils.get_unused_gmail_accounts()
        return [{'email': acc.email, 'app_password': acc.app_password} for acc in accounts]
    except Exception as e:
        logger.error(f"Error loading Gmail accounts: {e}")
        return []


def load_static_password():
    """Load static password from configuration"""
    return STATIC_PASSWORD
