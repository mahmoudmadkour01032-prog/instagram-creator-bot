import os

# Telegram Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# Database Configuration - SQLite
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_database.db')

# Automation Settings
HEADLESS_MODE = os.getenv('HEADLESS_MODE', 'True').lower() == 'true'
DELAY_BETWEEN_ACCOUNTS = int(os.getenv('DELAY_BETWEEN_ACCOUNTS', '30'))
STATIC_PASSWORD = os.getenv('STATIC_PASSWORD', 'SecurePass!2024x')

# Gmail Account (optional - bot can use temp emails instead)
GMAIL_EMAIL = os.getenv('GMAIL_EMAIL', '')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', '')

# Captcha Solving (optional)
CAPTCHA_API_KEY = os.getenv('CAPTCHA_API_KEY', '')

# Account Creation Mode: 'temp' (uses mail.tm) or 'gmail' (uses your Gmail accounts)
ACCOUNT_MODE = os.getenv('ACCOUNT_MODE', 'temp')

# Google Sheets (optional)
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'Instagram Accounts Database')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'Accounts')
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', 'credentials.json')

# Web Dashboard
WEB_DASHBOARD_URL = os.getenv('WEB_DASHBOARD_URL', 'https://your-netlify-app.netlify.app')

# Port
PORT = int(os.getenv('PORT', '5000'))

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'bot.log')

# Admin (kept for reference, no longer enforced)
ADMIN_IDS = os.getenv('ADMIN_IDS', '').split(',') if os.getenv('ADMIN_IDS') else []
