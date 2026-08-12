"""
Temporary Email Manager - Using mail.tm API
Creates disposable email addresses, reads inbox, extracts OTP codes.
No real Gmail accounts needed.
"""

import requests
import time
import re
import logging
import random
import string
from datetime import datetime

logger = logging.getLogger(__name__)

# mail.tm API base
MAILTM_BASE = "https://api.mail.tm"


class TempEmailManager:
    """Manages temporary email accounts via mail.tm API"""

    def __init__(self):
        self.token = None
        self.account_id = None
        self.email = None
        self.password = None
        self.domains = []
        self._refresh_domains()

    def _refresh_domains(self):
        """Get available domains from mail.tm"""
        try:
            r = requests.get(f"{MAILTM_BASE}/domains", timeout=15)
            if r.status_code == 200:
                data = r.json()
                self.domains = [d["domain"] for d in data.get("hydra:member", data.get("member", []))]
                logger.info(f"Available domains: {self.domains}")
            else:
                # Fallback domains
                self.domains = ["mail.tm"]
        except Exception as e:
            logger.warning(f"Failed to get domains: {e}")
            self.domains = ["mail.tm"]

    def _get_domain(self):
        """Get a random available domain"""
        if not self.domains:
            self._refresh_domains()
        return random.choice(self.domains) if self.domains else "mail.tm"

    def create_account(self, custom_prefix=None):
        """Create a new temporary email account
        Returns (email, password) or (None, None) on failure
        """
        try:
            domain = self._get_domain()

            # Generate random email
            if custom_prefix:
                username = f"{custom_prefix}_{int(time.time())}"
            else:
                username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))

            self.email = f"{username}@{domain}"

            # Generate password for the email account
            self.password = ''.join(random.choices(string.ascii_letters + string.digits, k=20))

            # Create account on mail.tm
            r = requests.post(
                f"{MAILTM_BASE}/accounts",
                json={"address": self.email, "password": self.password},
                timeout=15
            )

            if r.status_code in (200, 201):
                logger.info(f"Temp email created: {self.email}")

                # Get JWT token for reading inbox
                self._authenticate()
                return self.email, self.password
            else:
                logger.error(f"Failed to create account: {r.status_code} {r.text[:200]}")
                return None, None

        except Exception as e:
            logger.error(f"Error creating temp email: {e}")
            return None, None

    def _authenticate(self):
        """Get JWT token for the email account"""
        try:
            r = requests.post(
                f"{MAILTM_BASE}/token",
                json={"address": self.email, "password": self.password},
                timeout=15
            )
            if r.status_code in (200, 201):
                data = r.json()
                self.token = data.get("token")
                self.account_id = data.get("id")
                logger.info("Authenticated with mail.tm")
            else:
                logger.error(f"Auth failed: {r.status_code}")
        except Exception as e:
            logger.error(f"Auth error: {e}")

    def get_messages(self, max_retries=6, retry_interval=10):
        """Get messages from inbox
        Polls until messages arrive or timeout
        """
        if not self.token:
            self._authenticate()
        if not self.token:
            return []

        headers = {"Authorization": f"Bearer {self.token}"}

        for attempt in range(max_retries):
            try:
                r = requests.get(f"{MAILTM_BASE}/messages", headers=headers, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    messages = data.get("hydra:member", data.get("member", []))
                    if messages:
                        logger.info(f"Got {len(messages)} message(s)")
                        return messages
                    logger.debug(f"No messages yet... attempt {attempt + 1}/{max_retries}")
                else:
                    logger.warning(f"Get messages failed: {r.status_code}")

            except Exception as e:
                logger.warning(f"Get messages error: {e}")

            if attempt < max_retries - 1:
                time.sleep(retry_interval)

        return []

    def get_message_by_id(self, message_id):
        """Get full message content by ID"""
        if not self.token:
            return None
        try:
            r = requests.get(
                f"{MAILTM_BASE}/messages/{message_id}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=15
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.error(f"Get message error: {e}")
        return None

    def extract_otp(self, text):
        """Extract 6-digit OTP code from text"""
        # Try different patterns for OTP codes
        patterns = [
            r'(?:code|CODE|Code)[\s:is]*\s*(\d{6})',
            r'(?:verification|VERIFICATION|Verification)[\s:is]*\s*(\d{6})',
            r'(?:confirm|CONFIRM|Confirm)[\s:is]*\s*(\d{6})',
            r'\b(\d{6})\b',  # Any 6-digit number (fallback)
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def wait_for_otp(self, max_wait=120, poll_interval=10):
        """Wait for Instagram OTP email and extract code
        Args:
            max_wait: Max seconds to wait
            poll_interval: Seconds between checks
        Returns:
            OTP code string or None
        """
        logger.info(f"Waiting for OTP email (max {max_wait}s)...")
        start = time.time()
        attempts = int(max_wait / poll_interval)

        for attempt in range(attempts):
            messages = self.get_messages(max_retries=1, retry_interval=1)
            for msg in messages:
                # Check if from Instagram
                sender = msg.get("from", {}).get("address", "")
                subject = msg.get("subject", "")

                if "instagram" in sender.lower() or "instagram" in subject.lower():
                    # Get full message
                    full = self.get_message_by_id(msg["id"])
                    if full:
                        # Check all text content
                        text = full.get("text", "") or ""
                        html = full.get("html", {}) or ""
                        if isinstance(html, list):
                            html = " ".join(html)
                        all_text = f"{subject} {text} {html}"

                        otp = self.extract_otp(all_text)
                        if otp:
                            logger.info(f"OTP found: {otp}")
                            return otp

            elapsed = time.time() - start
            if elapsed < max_wait:
                remaining = min(poll_interval, max_wait - elapsed)
                logger.debug(f"No OTP yet... {elapsed:.0f}s elapsed, waiting {remaining:.0f}s")
                time.sleep(remaining)

        logger.warning("OTP timeout - no verification email received")
        return None

    def delete_account(self):
        """Delete the temporary email account"""
        if self.token and self.account_id:
            try:
                r = requests.delete(
                    f"{MAILTM_BASE}/accounts/{self.account_id}",
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=10
                )
                logger.info("Temp email deleted")
            except Exception as e:
                logger.warning(f"Delete error: {e}")


def create_temp_email_and_wait_for_otp(max_wait=120):
    """Convenience function: create email + wait for OTP
    Returns (email, otp_code) or (None, None)
    """
    manager = TempEmailManager()
    email, password = manager.create_account()
    if not email:
        return None, None

    otp = manager.wait_for_otp(max_wait=max_wait)
    return email, otp
