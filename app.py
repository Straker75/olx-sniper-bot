#!/usr/bin/env python3
"""
Simple Flask app for health checks and running the bot
"""

import os
from flask import Flask, jsonify
import threading
import time
from sniperbot import OLXSniperBot

app = Flask(__name__)

# Global bot instance
bot = None
bot_thread = None

@app.route('/')
@app.route('/health')
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({
        "status": "healthy",
        "service": "OLX Sniper Bot (Python)",
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    })

def run_bot():
    """Run the bot in a separate thread"""
    global bot
    bot = OLXSniperBot()
    bot.run()

if __name__ == "__main__":
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
