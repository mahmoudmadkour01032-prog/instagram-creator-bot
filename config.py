import os

# Telegram Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# Database Configuration - SQLite (local file-based)
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_database.db')

# Google Sheets Configuration
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'Instagram Accounts Database')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'Accounts')
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', 'credentials.json')

# Automation Settings
HEADLESS_MODE = os.getenv('HEADLESS_MODE', 'True').lower() == 'true'
DELAY_BETWEEN_ACCOUNTS = int(os.getenv('DELAY_BETWEEN_ACCOUNTS', '30'))
STATIC_PASSWORD = os.getenv('STATIC_PASSWORD', 'SecurePassword123!')

# Gmail Account for verification
GMAIL_EMAIL = os.getenv('GMAIL_EMAIL', '')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', '')

# Web Dashboard Configuration
WEB_DASHBOARD_URL = os.getenv('WEB_DASHBOARD_URL', 'https://your-netlify-app.netlify.app')

# Port (Railway/Heroku auto-set)
PORT = int(os.getenv('PORT', 5000))

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'bot.log')

# Admin Configuration
ADMIN_IDS = os.getenv('ADMIN_IDS', '').split(',') if os.getenv('ADMIN_IDS') else []
