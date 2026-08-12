import os

# Telegram Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost/instagram_bot')

# Google Sheets Configuration
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'Instagram Accounts Database')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'Accounts')
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', 'credentials.json')

# Automation Settings
HEADLESS_MODE = os.getenv('HEADLESS_MODE', 'True').lower() == 'true'
DELAY_BETWEEN_ACCOUNTS = int(os.getenv('DELAY_BETWEEN_ACCOUNTS', '30'))
STATIC_PASSWORD = os.getenv('STATIC_PASSWORD', 'SecurePassword123!')

# Web Dashboard Configuration
WEB_DASHBOARD_URL = os.getenv('WEB_DASHBOARD_URL', 'https://your-netlify-app.netlify.app')

# Port (Railway/Heroku auto-set)
PORT = int(os.getenv('PORT', 5000))

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'bot.log')

# Database Connection Settings
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '10'))
DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))

# Admin Configuration
ADMIN_IDS = os.getenv('ADMIN_IDS', '').split(',') if os.getenv('ADMIN_IDS') else []
