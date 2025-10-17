#!/usr/bin/env python3
"""
OLX Sniper Bot - Python Version
Monitors OLX for new iPhone listings and sends Discord notifications
"""

import os
import time
import json
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import urljoin, urlparse
import re
from datetime import datetime

# Load environment variables
load_dotenv('ini.env')

# Configuration
OLX_SEARCH_URL = os.getenv('OLX_SEARCH_URL', 'https://www.olx.pl/oferty/q-iphone/?search%5Border%5D=created_at:desc')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '45'))
USER_AGENT = os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36')
SEEN_FILE = os.getenv('SEEN_FILE', './seen.json')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S+00:00'
)
logger = logging.getLogger(__name__)

class OLXSniperBot:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.seen_listings = self.load_seen_listings()
        
    def load_seen_listings(self):
        """Load previously seen listing IDs"""
        try:
            if os.path.exists(SEEN_FILE):
                with open(SEEN_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading seen listings: {e}")
        return []
    
    def save_seen_listings(self):
        """Save seen listing IDs"""
        try:
            with open(SEEN_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.seen_listings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving seen listings: {e}")
    
    def extract_title_from_url(self, url):
        """Extract title from OLX URL"""
        try:
            # Pattern: /oferta/[TITLE]-CID99-ID[ID].html
            if '/oferta/' in url and '-CID99' in url:
                start_pos = url.find('/oferta/') + 8  # Length of '/oferta/'
                end_pos = url.find('-CID99')
                if end_pos > start_pos:
                    title = url[start_pos:end_pos]
                    # Convert dashes to spaces and capitalize
                    title = title.replace('-', ' ').title()
                    return title
        except Exception as e:
            logger.error(f"Error extracting title from URL: {e}")
        return None
    
    def fetch_listings(self):
        """Fetch and parse OLX listings"""
        try:
            logger.info(f"Fetching listings from: {OLX_SEARCH_URL}")
            response = self.session.get(OLX_SEARCH_URL, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            listings = []
            
            # Find listing containers instead of just links
            # Look for common OLX listing container patterns
            listing_containers = soup.find_all(['div', 'article'], class_=lambda x: x and any(
                keyword in x.lower() for keyword in ['css-', 'listing', 'offer', 'card']
            ))
            
            logger.info(f"Found {len(listing_containers)} potential listing containers")
            
            for container in listing_containers:
                # Find the main link in this container
                link = container.find('a', href=True)
                if not link or '/oferta/' not in link.get('href', ''):
                    continue
                
                href = link.get('href')
                if href.startswith('/'):
                    href = urljoin('https://www.olx.pl', href)
                
                # Extract listing ID from URL
                listing_id = self.extract_listing_id(href)
                if not listing_id:
                    continue
                
                # Extract title from URL (more reliable than HTML parsing)
                title = self.extract_title_from_url(href)
                if not title:
                    title = "iPhone na OLX"
                
                # Extract data from the container (better context)
                price = self.extract_price(container)
                location = self.extract_location(container)
                image = self.extract_image(container)
                
                listing = {
                    'id': listing_id,
                    'title': title,
                    'url': href,
                    'price': price or 'Cena do uzgodnienia',
                    'location': location or 'Brak',
                    'image': image
                }
                
                listings.append(listing)
                logger.info(f"Found listing: {title} - {price} - {location}")
            
            # Remove duplicates
            unique_listings = []
            seen_ids = set()
            for listing in listings:
                if listing['id'] not in seen_ids:
                    unique_listings.append(listing)
                    seen_ids.add(listing['id'])
            
            logger.info(f"Found {len(unique_listings)} unique listings")
            return unique_listings
            
        except Exception as e:
            logger.error(f"Error fetching listings: {e}")
            return []
    
    def extract_listing_id(self, url):
        """Extract listing ID from URL"""
        try:
            # Pattern: -ID[ID].html
            match = re.search(r'-ID([A-Za-z0-9]+)\.html', url)
            if match:
                return match.group(1)
            # Fallback: use URL hash
            return str(hash(url))[-8:]
        except Exception:
            return None
    
    def extract_price(self, element):
        """Extract price from listing element"""
        try:
            # Look for price in specific elements first
            price_selectors = [
                'span[data-testid="ad-price"]',
                'p[data-testid="ad-price"]',
                '.css-1bafgv4',
                '.css-1u2vqda',
                '.price',
                '.offer-price',
                '[class*="price"]',
                '[class*="cost"]'
            ]
            
            for selector in price_selectors:
                price_elem = element.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text().strip()
                    price_match = re.search(r'(\d+(?:\s*\d+)*(?:,\d+)?\s*(?:zł|PLN|€|\$))', price_text)
                    if price_match:
                        logger.debug(f"Found price with selector '{selector}': {price_match.group(1)}")
                        return price_match.group(1)
            
            # Look for price patterns in all text
            text = element.get_text()
            price_match = re.search(r'(\d+(?:\s*\d+)*(?:,\d+)?\s*(?:zł|PLN|€|\$))', text)
            if price_match:
                logger.debug(f"Found price in text: {price_match.group(1)}")
                return price_match.group(1)
            
            # Look in parent elements
            parent = element.parent
            if parent:
                parent_text = parent.get_text()
                price_match = re.search(r'(\d+(?:\s*\d+)*(?:,\d+)?\s*(?:zł|PLN|€|\$))', parent_text)
                if price_match:
                    logger.debug(f"Found price in parent: {price_match.group(1)}")
                    return price_match.group(1)
                    
        except Exception as e:
            logger.debug(f"Error extracting price: {e}")
        return None
    
    def extract_location(self, element):
        """Extract location from listing element"""
        try:
            # Look for location in specific elements first
            location_selectors = [
                'p[data-testid="location-date"]',
                'span[data-testid="location-date"]',
                '.css-veheph',
                '.css-17o22yg',
                '.css-1a4brun',
                '[class*="location"]',
                '[class*="city"]'
            ]
            
            for selector in location_selectors:
                location_elem = element.select_one(selector)
                if location_elem:
                    location_text = location_elem.get_text().strip()
                    # Look for location-date pattern like "Brzesko - Dzisiaj o 10:32"
                    location_match = re.search(r'([A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ\s\-]+)\s*-\s*(Dzisiaj|Wczoraj|\d{1,2}\.\d{1,2}\.\d{4})', location_text)
                    if location_match:
                        logger.debug(f"Found location with selector '{selector}': {location_match.group(1)}")
                        return location_match.group(1).strip()
            
            # Look for location patterns in all text
            text = element.get_text()
            # Look for location-date pattern like "Brzesko - Dzisiaj o 10:32"
            location_match = re.search(r'([A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ\s\-]+)\s*-\s*(Dzisiaj|Wczoraj|\d{1,2}\.\d{1,2}\.\d{4})', text)
            if location_match:
                logger.debug(f"Found location in text: {location_match.group(1)}")
                return location_match.group(1).strip()
            
            # Look for common Polish cities
            cities = ['Warszawa', 'Kraków', 'Gdańsk', 'Wrocław', 'Poznań', 'Łódź', 'Szczecin', 
                     'Bydgoszcz', 'Lublin', 'Katowice', 'Białystok', 'Gdynia', 'Częstochowa', 
                     'Radom', 'Sosnowiec', 'Toruń', 'Kielce', 'Gliwice', 'Zabrze', 'Bytom', 
                     'Olsztyn', 'Bielsko-Biała', 'Rzeszów', 'Ruda Śląska', 'Rybnik', 'Tychy', 
                     'Dąbrowa Górnicza', 'Płock', 'Elbląg', 'Opole', 'Gorzów Wielkopolski', 
                     'Włocławek', 'Zielona Góra', 'Tarnów', 'Chorzów', 'Kalisz', 'Koszalin', 
                     'Legnica', 'Grudziądz', 'Słupsk', 'Jaworzno', 'Jastrzębie-Zdrój', 
                     'Jelenia Góra', 'Nowy Sącz', 'Konin', 'Piotrków Trybunalski', 'Lubin', 
                     'Inowrocław', 'Ostrów Wielkopolski', 'Stargard', 'Mysłowice', 'Piła', 
                     'Ostrowiec Świętokrzyski', 'Siedlce', 'Mielec', 'Oława', 'Gniezno', 
                     'Głogów', 'Swarzędz', 'Tarnobrzeg', 'Żory', 'Pruszków', 'Racibórz', 
                     'Świętochłowice', 'Zawiercie', 'Starachowice', 'Skierniewice', 'Kutno', 
                     'Otwock', 'Żywiec', 'Wejherowo', 'Zgierz', 'Będzin', 'Pabianice', 
                     'Rumia', 'Świdnica', 'Żyrardów', 'Kraśnik', 'Mikołów', 'Łomża', 
                     'Żagań', 'Świnoujście', 'Kołobrzeg', 'Ostrołęka', 'Stalowa Wola', 
                     'Myszków', 'Łuków', 'Grodzisk Mazowiecki', 'Skarżysko-Kamienna', 
                     'Jarocin', 'Krotoszyn', 'Zduńska Wola', 'Śrem', 'Kłodzko', 'Nowa Sól', 
                     'Środa Wielkopolska', 'Gostyń', 'Rawicz', 'Kępno', 'Ostrzeszów', 'Brzesko']
            
            for city in cities:
                if city.lower() in text.lower():
                    logger.debug(f"Found city in text: {city}")
                    return city
        except Exception as e:
            logger.debug(f"Error extracting location: {e}")
        return None
    
    def extract_image(self, element):
        """Extract image URL from listing element"""
        try:
            # Look for images in specific elements first
            image_selectors = [
                'img[data-src]',
                'img[src]',
                'img[data-lazy-src]',
                'img[data-original]',
                '.css-1bmvjcs img',
                '[class*="image"] img',
                '[class*="photo"] img',
                '[class*="thumbnail"] img'
            ]
            
            for selector in image_selectors:
                img_elem = element.select_one(selector)
                if img_elem:
                    src = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy-src') or img_elem.get('data-original')
                    if src:
                        if src.startswith('/'):
                            src = urljoin('https://www.olx.pl', src)
                        # Remove query parameters that might break the URL
                        src = src.split('?')[0]
                        # Validate URL
                        if src.startswith('http') and not src.endswith('.svg'):
                            logger.debug(f"Found image with selector '{selector}': {src}")
                            return src
            
            # Look for any img in the element
            img = element.find('img')
            if img:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-original')
                if src:
                    if src.startswith('/'):
                        src = urljoin('https://www.olx.pl', src)
                    src = src.split('?')[0]
                    if src.startswith('http') and not src.endswith('.svg'):
                        logger.debug(f"Found image: {src}")
                        return src
            
            # Look in parent elements
            parent = element.parent
            if parent:
                img = parent.find('img')
                if img:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-original')
                    if src:
                        if src.startswith('/'):
                            src = urljoin('https://www.olx.pl', src)
                        src = src.split('?')[0]
                        if src.startswith('http') and not src.endswith('.svg'):
                            logger.debug(f"Found image in parent: {src}")
                            return src
        except Exception as e:
            logger.debug(f"Error extracting image: {e}")
        return None
    
    def send_discord_notification(self, listing):
        """Send Discord webhook notification"""
        try:
            # Prepare Discord embed data
            embed_data = {
                "title": listing['title'],
                "url": listing['url'],
                "color": 3066993,  # Green color
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "description": f"📌 {listing['title']}\n💰 Cena: {listing['price']}\n📍 Lokalizacja: {listing['location']}\n📦 Dostawa: TAK\n🔗 Link do ogłoszenia"
            }
            
            # Add thumbnail if image available
            if listing['image']:
                embed_data["thumbnail"] = {"url": listing['image']}
            else:
                embed_data["thumbnail"] = {"url": "https://www.olx.pl/favicon.ico"}
            
            # Prepare webhook payload
            payload = {
                "content": "",
                "username": "OLX Sniper Bot",
                "embeds": [embed_data],
                "components": [{
                    "type": 1,
                    "components": [{
                        "type": 2,
                        "style": 5,
                        "label": "KUP TERAZ",
                        "url": listing['url'],
                        "emoji": {"name": "🔗"}
                    }]
                }]
            }
            
            # Send webhook with retry logic
            max_retries = 3
            retry_delay = 5
            
            for attempt in range(1, max_retries + 1):
                try:
                    response = requests.post(
                        DISCORD_WEBHOOK_URL,
                        json=payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=30
                    )
                    response.raise_for_status()
                    logger.info(f"✅ Sent notification for: {listing['title']}")
                    return True
                    
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:  # Rate limited
                        logger.warning(f"Rate limited, waiting {retry_delay}s before retry {attempt}/{max_retries}")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        logger.error(f"HTTP error sending webhook (attempt {attempt}): {e}")
                        break
                except Exception as e:
                    logger.error(f"Error sending webhook (attempt {attempt}): {e}")
                    break
            
            logger.error(f"Failed to send notification for {listing['id']} after {max_retries} attempts")
            return False
            
        except Exception as e:
            logger.error(f"Error preparing Discord notification: {e}")
            return False
    
    def run(self):
        """Main bot loop"""
        if not DISCORD_WEBHOOK_URL:
            logger.error("DISCORD_WEBHOOK_URL not set in environment variables")
            return
        
        logger.info(f"Starting OLX sniper bot. Polling {OLX_SEARCH_URL} every {POLL_INTERVAL}s")
        
        # First run: mark all current listings as seen (don't notify)
        is_first_run = True
        
        while True:
            try:
                logger.info(f"Polling {OLX_SEARCH_URL}")
                listings = self.fetch_listings()
                
                if not listings:
                    logger.info("No listings found or error occurred")
                else:
                    new_count = 0
                    current_listing_ids = [listing['id'] for listing in listings]
                    
                    # On first run, mark all current listings as seen
                    if is_first_run:
                        logger.info(f"First run - marking {len(current_listing_ids)} current listings as seen")
                        self.seen_listings.extend(current_listing_ids)
                        self.seen_listings = list(set(self.seen_listings))  # Remove duplicates
                        self.save_seen_listings()
                        is_first_run = False
                        logger.info("First run complete. Future runs will only show new listings.")
                        continue
                    
                    # Check for new listings
                    for listing in listings:
                        if listing['id'] not in self.seen_listings:
                            new_count += 1
                            logger.info(f"NEW listing: {listing['title']} ({listing['id']})")
                            
                            success = self.send_discord_notification(listing)
                            if success:
                                self.seen_listings.append(listing['id'])
                                self.save_seen_listings()
                                time.sleep(5)  # Pause between notifications
                            else:
                                logger.error(f"Failed to notify Discord for {listing['id']}")
                    
                    # Clean up old seen IDs (keep only recent ones)
                    if len(self.seen_listings) > 1000:
                        self.seen_listings = self.seen_listings[-500:]  # Keep only last 500
                        self.save_seen_listings()
                        logger.info(f"Cleaned up old seen listings. Kept {len(self.seen_listings)} recent ones.")
                    
                    if new_count == 0:
                        logger.info(f"No new listings found. Total listings: {len(listings)}")
                    else:
                        logger.info(f"Found {new_count} new listings out of {len(listings)} total.")
                
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
            
            # Sleep with jitter to avoid perfect periodicity
            import random
            jitter = random.randint(0, max(1, POLL_INTERVAL // 5))
            sleep_time = max(1, POLL_INTERVAL + jitter - POLL_INTERVAL // 10)
            time.sleep(sleep_time)

def health_check():
    """Simple health check for Railway"""
    return {
        "status": "healthy",
        "service": "OLX Sniper Bot",
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    }

if __name__ == "__main__":
    bot = OLXSniperBot()
    bot.run()
