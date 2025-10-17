#!/usr/bin/env python3
"""
Simple Flask app for health checks and running the bot
"""

import os
from flask import Flask, jsonify
import threading
import time
import logging
from sniperbot import OLXSniperBot

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S+00:00'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global bot instance
bot = None
bot_thread = None

def run_bot():
    """Run the bot in a separate thread"""
    global bot
    try:
        logger.info("Starting OLX Sniper Bot thread...")
        bot = OLXSniperBot()
        bot.run()
    except Exception as e:
        logger.error(f"Error in bot thread: {e}")

# Start bot in background thread when module is imported
if not bot_thread:
    logger.info("Starting bot thread...")
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

@app.route('/')
@app.route('/health')
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({
        "status": "healthy",
        "service": "OLX Sniper Bot (Python)",
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
        "bot_running": bot_thread.is_alive() if bot_thread else False
    })

if __name__ == "__main__":
    # Start Flask app
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
