import os
import shutil
import logging

logger = logging.getLogger(__name__)

def get_chrome_binary():
    """Find Chrome/Chromium binary on the system"""
    candidates = [
        'chromium',
        'chromium-browser', 
        'google-chrome',
        'google-chrome-stable',
        'chrome',
    ]
    
    for name in candidates:
        path = shutil.which(name)
        if path:
            logger.info(f"Found browser: {path}")
            return path
    
    # Check common paths
    common_paths = [
        '/usr/bin/chromium',
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/nix/store/chromium/bin/chromium',
    ]
    for p in common_paths:
        if os.path.exists(p):
            logger.info(f"Found browser at: {p}")
            return p
    
    env_bin = os.getenv('CHROME_BIN', '')
    if env_bin and os.path.exists(env_bin):
        logger.info(f"Using CHROME_BIN: {env_bin}")
        return env_bin
    
    return None
