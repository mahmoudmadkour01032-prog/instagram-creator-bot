import asyncio
import threading
import time
import logging
import os
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import *
from automation_logic import *
from database import DatabaseUtils, db_manager
from instagram_automation import create_instagram_account, save_to_google_sheets

# Configure logging
try:
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
except Exception:
    pass

handlers = [logging.StreamHandler()]
try:
    handlers.insert(0, logging.FileHandler(LOG_FILE))
except Exception:
    pass

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)

# Initialize Flask app for API
api_app = Flask(__name__)
CORS(api_app, origins=[WEB_DASHBOARD_URL])

# Initialize rate limiter
limiter = Limiter(
    get_remote_address,
    app=api_app,
    default_limits=["200 per day", "50 per hour"]
)


class InstagramBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.automation_thread = None
        self.is_running = False

    # ==================== COMMANDS ====================

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_message = """
🤖 **Instagram Creator Bot v2**

⚡ **New: Uses instagrapi API + temp emails (mail.tm)**

**Commands:**
/create [count] - Create accounts using temp emails (easiest!)
/create_gmail [count] - Create using Gmail accounts
/start_auto <index> - Start from specific Gmail index
/stop - Stop current automation
/status - Check current status
/accounts - Export all created accounts as .txt
/add_gmail <email>,<password> - Add Gmail account
/help - Show this help

**Examples:**
/create 3 — Create 3 accounts with temp emails
/create_gmail — Create 1 account with next Gmail
        """
        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_message = """
📚 **Bot Commands**

🚀 **Account Creation:**
• `/create [N]` — Create N accounts (temp emails, no Gmail needed!)
• `/create_gmail [N]` — Create N accounts using your Gmail accounts

⚙️ **Automation:**
• `/start_auto <index>` — Start batch from Gmail index
• `/stop` — Stop running automation
• `/status` — Current stats & progress

📁 **Data:**
• `/accounts` — Download all accounts as .txt
• `/add_gmail <email>,<pass>` — Add Gmail account

💡 **Tips:**
• `/create 5` = create 5 accounts automatically
• Temp emails are auto-generated, no setup needed
• Each account gets 2FA enabled automatically
        """
        await update.message.reply_text(help_message)

    async def create_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create accounts using temp emails (no Gmail needed!)"""
        chat_id = update.effective_chat.id
        try:
            state = load_bot_state()
            if state['is_running']:
                await update.message.reply_text("⚠️ Bot is busy! Use /stop first.")
                return

            # Get count (default 1)
            count = 1
            if context.args and context.args[0].isdigit():
                count = min(int(context.args[0]), 10)  # Max 10 at a time

            await update.message.reply_text(
                f"🚀 **Creating {count} account(s) with temp emails...**\n"
                f"⏳ This may take a few minutes per account.\n"
                f"📧 Using mail.tm disposable emails"
            )

            # Start in background thread
            self.is_running = True
            self.automation_thread = threading.Thread(
                target=self.run_temp_email_creation,
                args=(count, chat_id)
            )
            self.automation_thread.daemon = True
            self.automation_thread.start()

        except Exception as e:
            logger.error(f"Create error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def create_gmail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create accounts using Gmail accounts"""
        chat_id = update.effective_chat.id
        try:
            state = load_bot_state()
            if state['is_running']:
                await update.message.reply_text("⚠️ Bot is busy! Use /stop first.")
                return

            count = 1
            if context.args and context.args[0].isdigit():
                count = min(int(context.args[0]), 10)

            accounts = load_gmail_accounts()
            if not accounts:
                await update.message.reply_text(
                    "📭 No Gmail accounts found!\n"
                    "Add with: `/add_gmail email,password`\n"
                    "Or use `/create` for temp email mode"
                )
                return

            await update.message.reply_text(
                f"🚀 **Creating {count} account(s) with Gmail...**\n"
                f"📧 {len(accounts)} Gmail accounts available"
            )

            self.is_running = True
            self.automation_thread = threading.Thread(
                target=self.run_gmail_creation,
                args=(count, chat_id)
            )
            self.automation_thread.daemon = True
            self.automation_thread.start()

        except Exception as e:
            logger.error(f"Create Gmail error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def add_gmail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "❌ Usage: `/add_gmail email,password`\n"
                "Example: `/add_gmail user@gmail.com,xxxx xxxx xxxx xxxx`"
            )
            return

        full_text = ' '.join(context.args)
        if ',' not in full_text:
            await update.message.reply_text("❌ Format: `email,password`")
            return

        email, app_password = full_text.split(',', 1)
        email, app_password = email.strip(), app_password.strip()

        success = DatabaseUtils.add_gmail_account(email, app_password)
        if success:
            await update.message.reply_text(f"✅ Gmail added: `{email}`")
        else:
            await update.message.reply_text(f"❌ Failed (maybe already exists)")

    async def start_auto_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start batch automation from Gmail list"""
        try:
            state = load_bot_state()
            if state['is_running']:
                await update.message.reply_text("⚠️ Already running! Use /stop first.")
                return

            start_index = 0
            if context.args and context.args[0].isdigit():
                start_index = int(context.args[0])

            accounts = load_gmail_accounts()
            if not accounts:
                await update.message.reply_text(
                    "📭 No Gmail accounts! Use /add_gmail or /create for temp mode"
                )
                return

            if start_index >= len(accounts):
                await update.message.reply_text(
                    f"❌ Index {start_index} out of range. Total: {len(accounts)}"
                )
                return

            self.is_running = True
            self.automation_thread = threading.Thread(
                target=self.run_gmail_creation,
                args=(len(accounts) - start_index, update.message.chat_id, start_index)
            )
            self.automation_thread.daemon = True
            self.automation_thread.start()

            await update.message.reply_text(
                f"🚀 **Started!**\n"
                f"📊 From index {start_index}, {len(accounts)} accounts in queue"
            )

        except Exception as e:
            logger.error(f"Start auto error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            state = load_bot_state()
            if not state['is_running']:
                await update.message.reply_text("ℹ️ Nothing is running.")
                return

            state['is_running'] = False
            save_bot_state(state)
            self.is_running = False

            await update.message.reply_text(
                f"🛑 **Stopped!**\n"
                f"✅ Created: {state['successful']}\n"
                f"❌ Failed: {state['failed']}\n"
                f"⏱ Duration: {self.get_session_duration()}"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            state = load_bot_state()
            stats = get_statistics()

            icon = "🔄" if state['is_running'] else "⏸️"
            status = "RUNNING" if state['is_running'] else "IDLE"

            rate = 0
            if state['total_processed'] > 0:
                rate = (state['successful'] / state['total_processed']) * 100

            await update.message.reply_text(
                f"{icon} **Status:** {status}\n"
                f"✅ Created: {stats['successful']}\n"
                f"❌ Failed: {stats['failed']}\n"
                f"📈 Success Rate: {rate:.1f}%\n"
                f"📋 Total in DB: {stats['total']}\n"
                f"⏱ Duration: {self.get_session_duration()}"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def accounts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        try:
            accounts = DatabaseUtils.get_instagram_accounts(status='successful')
            if not accounts:
                await update.message.reply_text("📭 No accounts created yet. Use /create to start!")
                return

            lines = [
                f"=== Instagram Accounts ({len(accounts)}) ===",
                f"Exported: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                "",
                f"{'#':<4} {'Username':<20} {'Password':<20} {'2FA Key':<30}",
                "-" * 80
            ]
            for i, acc in enumerate(accounts, 1):
                username = acc.username or 'N/A'
                password = acc.password or 'N/A'
                secret = acc.secret_key or 'N/A'
                lines.append(f"{i:<4} {username:<20} {password:<20} {secret:<30}")

            filename = f'accounts_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.txt'
            with open(filename, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            with open(filename, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=filename,
                    caption=f"📁 **{len(accounts)} accounts** exported"
                )
            os.remove(filename)

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

    # ==================== AUTOMATION THREADS ====================

    def run_temp_email_creation(self, count, chat_id):
        """Create N accounts using temp emails (mail.tm)"""
        state = load_bot_state()
        state['is_running'] = True
        state['started_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        save_bot_state(state)

        for i in range(count):
            if not state['is_running']:
                break

            asyncio.run(self.bot.send_message(
                chat_id=chat_id,
                text=f"🔄 **Account {i+1}/{count}** — Creating with temp email...\n⏰ {time.strftime('%H:%M:%S')}"
            ))

            account_data = create_instagram_account(use_temp_email=True)

            if account_data:
                state['successful'] += 1
                state['total_processed'] += 1
                asyncio.run(self.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ **Account #{i+1} Created!**\n"
                         f"👤 Username: `{account_data['username']}`\n"
                         f"📧 Email: `{account_data['temp_email']}`\n"
                         f"🔑 2FA: `{account_data.get('secret_key', 'N/A')}`\n"
                         f"⏱ {account_data['processing_time']:.1f}s"
                ))
            else:
                state['failed'] += 1
                state['total_processed'] += 1
                asyncio.run(self.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ **Account #{i+1} Failed** — Trying next..."
                ))

            state['current_index'] = i + 1
            save_bot_state(state)

            if i < count - 1:
                time.sleep(DELAY_BETWEEN_ACCOUNTS)

        if state['is_running']:
            rate = (state['successful'] / state['total_processed'] * 100) if state['total_processed'] > 0 else 0
            asyncio.run(self.bot.send_message(
                chat_id=chat_id,
                text=f"🎉 **Done!**\n✅ {state['successful']} created | ❌ {state['failed']} failed | 📈 {rate:.0f}%"
            ))

        state['is_running'] = False
        save_bot_state(state)
        self.is_running = False

    def run_gmail_creation(self, count, chat_id, start_index=0):
        """Create accounts using Gmail"""
        accounts = load_gmail_accounts()
        state = load_bot_state()
        state['is_running'] = True
        state['started_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        save_bot_state(state)

        end = min(start_index + count, len(accounts))

        for i in range(start_index, end):
            if not state['is_running']:
                break

            acc = accounts[i]
            asyncio.run(self.bot.send_message(
                chat_id=chat_id,
                text=f"🔄 **Account {i+1}/{end}** — Using Gmail: `{acc['email']}`"
            ))

            account_data = create_instagram_account(
                use_temp_email=False,
                gmail_account=acc['email'],
                gmail_app_password=acc['app_password']
            )

            if account_data:
                save_to_google_sheets(account_data)
                DatabaseUtils.mark_gmail_account_used(acc['email'])
                state['successful'] += 1
                state['total_processed'] += 1
                asyncio.run(self.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ **Created!**\n👤 `{account_data['username']}`\n🔑 2FA: `{account_data.get('secret_key', 'N/A')}`"
                ))
            else:
                state['failed'] += 1
                state['total_processed'] += 1
                asyncio.run(self.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Account #{i+1} failed"
                ))

            state['current_index'] = i + 1
            save_bot_state(state)

            if i < end - 1:
                time.sleep(DELAY_BETWEEN_ACCOUNTS)

        if state['is_running']:
            asyncio.run(self.bot.send_message(
                chat_id=chat_id,
                text=f"🎉 **Gmail batch done!**\n✅ {state['successful']} | ❌ {state['failed']}"
            ))

        state['is_running'] = False
        save_bot_state(state)
        self.is_running = False

    # ==================== HELPERS ====================

    def get_session_duration(self):
        state = load_bot_state()
        if state.get('started_at'):
            try:
                start = time.strptime(state['started_at'], '%Y-%m-%d %H:%M:%S')
                dur = time.mktime(time.localtime()) - time.mktime(start)
                return f"{int(dur // 3600)}h {int((dur % 3600) // 60)}m"
            except:
                pass
        return "N/A"

    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("create", self.create_command))
        self.application.add_handler(CommandHandler("create_gmail", self.create_gmail_command))
        self.application.add_handler(CommandHandler("start_auto", self.start_auto_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("add_gmail", self.add_gmail_command))
        self.application.add_handler(CommandHandler("accounts", self.accounts_command))

    def run(self):
        try:
            self.setup_handlers()
            logger.info("Starting Instagram Creator Bot v2 (instagrapi + temp emails)")
            self.application.run_polling()
        except Exception as e:
            logger.error(f"Error running bot: {e}")


# ==================== API Endpoints ====================

@api_app.route('/api/bot/status')
@limiter.limit("10 per minute")
def api_bot_status():
    try:
        state = load_bot_state()
        stats = get_statistics()
        return jsonify({
            'status': 'online' if state['is_running'] else 'offline',
            'is_running': state['is_running'],
            'stats': stats,
            'bot_state': state
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_app.route('/api/bot/create', methods=['POST'])
@limiter.limit("5 per hour")
def api_create_account():
    try:
        data = request.get_json() or {}
        count = min(data.get('count', 1), 10)
        use_temp = data.get('useTempEmail', True)

        state = load_bot_state()
        if state['is_running']:
            return jsonify({'error': 'Bot is busy'}), 400

        bot_instance = InstagramBot()
        if use_temp:
            bot_instance.automation_thread = threading.Thread(
                target=bot_instance.run_temp_email_creation,
                args=(count, None)
            )
        else:
            bot_instance.automation_thread = threading.Thread(
                target=bot_instance.run_gmail_creation,
                args=(count, None, 0)
            )
        bot_instance.automation_thread.daemon = True
        bot_instance.automation_thread.start()

        return jsonify({'success': True, 'count': count, 'mode': 'temp' if use_temp else 'gmail'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_app.route('/api/accounts')
@limiter.limit("20 per minute")
def api_get_accounts():
    try:
        status = request.args.get('status')
        accounts = DatabaseUtils.get_instagram_accounts(status)
        total = len(accounts)

        accounts_data = [{
            'id': a.id, 'username': a.username, 'email': a.email,
            'temp_email': a.temp_email, 'status': a.status,
            'created_at': a.created_at.strftime('%Y-%m-%d %H:%M:%S') if a.created_at else None,
            'secret_key': a.secret_key
        } for a in accounts]

        return jsonify({'accounts': accounts_data, 'total': total})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_app.route('/health')
def health_check():
    try:
        db_ok = db_manager.test_connection()
        return jsonify({
            'status': 'healthy' if db_ok else 'unhealthy',
            'database': 'connected' if db_ok else 'disconnected',
            'bot_running': load_bot_state()['is_running']
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


def run_api_server():
    try:
        logger.info(f"API server on port {PORT}")
        api_app.run(host='0.0.0.0', port=PORT, debug=False)
    except Exception as e:
        logger.error(f"API server error: {e}")


if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        print("ERROR: Set BOT_TOKEN env variable")
        import sys
        sys.exit(1)

    try:
        if db_manager.test_connection():
            logger.info("Database connected")
    except Exception as e:
        logger.error(f"DB init error: {e}")

    # Start API in background
    api_thread = threading.Thread(target=run_api_server)
    api_thread.daemon = True
    api_thread.start()

    # Start Telegram bot
    bot = InstagramBot()
    bot.run()
