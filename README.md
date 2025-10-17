# OLX Sniper Bot

A PHP-based web scraper that monitors OLX listings and sends real-time notifications to Discord when new items matching your search criteria are found.

## Features

- 🔍 Monitors OLX search results in real-time
- 📱 Sends Discord notifications for new listings
- 💾 Tracks seen listings to avoid duplicates
- ⚙️ Configurable polling intervals
- 🖼️ Rich Discord embeds with images
- 🛡️ Rate limiting and error handling

## Requirements

- PHP 7.4 or higher
- Composer
- SQLite (included with PHP)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/olx-sniper-bot.git
cd olx-sniper-bot
```

2. Install dependencies:
```bash
composer install
```

3. Copy the environment template:
```bash
cp .env.example .env
```

4. Configure your settings in `.env`:
```env
OLX_SEARCH_URL=https://www.olx.pl/oferty/q-your-search-term/
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
POLL_INTERVAL=60
USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
DB_PATH=./seen.sqlite
```

## Configuration

### Environment Variables

- `OLX_SEARCH_URL`: The OLX search URL you want to monitor
- `DISCORD_WEBHOOK_URL`: Your Discord webhook URL for notifications
- `POLL_INTERVAL`: How often to check for new listings (in seconds)
- `USER_AGENT`: Browser user agent string
- `DB_PATH`: Path to the SQLite database file

### Getting a Discord Webhook URL

1. Go to your Discord server settings
2. Navigate to Integrations → Webhooks
3. Create a new webhook
4. Copy the webhook URL

## Usage

Run the bot:
```bash
php sniperbot.php
```

The bot will continuously monitor the specified OLX search URL and send Discord notifications for new listings.

## How It Works

1. The bot fetches the OLX search page at regular intervals
2. Parses the HTML to extract listing information (title, price, URL, image)
3. Checks if each listing has been seen before using a SQLite database
4. Sends Discord notifications for new listings
5. Stores seen listings to prevent duplicate notifications

## Dependencies

- [Guzzle HTTP](https://github.com/guzzle/guzzle) - HTTP client
- [Symfony DomCrawler](https://github.com/symfony/dom-crawler) - HTML parsing
- [PHP Dotenv](https://github.com/vlucas/phpdotenv) - Environment variable management

## License

This project is open source and available under the [MIT License](LICENSE).

## Disclaimer

This bot is for educational purposes. Please respect OLX's terms of service and rate limits. Use responsibly and consider the impact on OLX's servers.
