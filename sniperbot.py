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
            
            # Find listing containers - look for containers that have offer links
            listing_containers = []
            
            # Alternative approach: Look for common OLX listing containers
            # Try different selectors that might contain listings
            listing_selectors = [
                '[data-testid="listing"]',
                '[data-testid="ad-card"]',
                '.css-1sw7q4x',  # Common OLX listing class
                '.css-1ap3yc9',  # Another common OLX class
                '[class*="css-"][class*="listing"]',
                '[class*="css-"][class*="card"]',
                '[class*="css-"][class*="offer"]'
            ]
            
            for selector in listing_selectors:
                found_containers = soup.select(selector)
                if found_containers:
                    logger.info(f"Found {len(found_containers)} containers with selector: {selector}")
                    listing_containers.extend(found_containers)
                    break
            
            # If no containers found with selectors, fall back to the original method
            if not listing_containers:
                logger.info("No containers found with selectors, trying original method...")
                # First, find all offer links
                offer_links = soup.find_all('a', href=True)
                offer_links = [link for link in offer_links if '/oferta/' in link.get('href', '')]
                
                logger.info(f"Found {len(offer_links)} offer links")
                
                for link in offer_links:
                    # Find the container that contains this link
                    container = link
                    # Go up the DOM tree to find a suitable container
                    for _ in range(5):  # Limit search depth
                        container = container.parent
                        if not container:
                            break
                        
                        # Check if this container looks like a listing container
                        container_class = container.get('class', [])
                        container_class_str = ' '.join(container_class).lower()
                        
                        if any(keyword in container_class_str for keyword in ['css-', 'listing', 'offer', 'card', 'item']):
                            if container not in listing_containers:
                                listing_containers.append(container)
                            break
                    else:
                        # If no suitable container found, use the link itself
                        if link not in listing_containers:
                            listing_containers.append(link)
            
            logger.info(f"Found {len(listing_containers)} listing containers")
            
            for container in listing_containers:
                # Find the main link in this container
                link = container.find('a', href=True) if container.name != 'a' else container
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
                
                # Debug: Log container HTML to see what we're working with
                logger.info(f"Container HTML for {title}: {str(container)[:300]}...")
                
                # Extract data from the container (better context)
                price = self.extract_price(container)
                location = self.extract_location(container)
                image = self.extract_image(container)
                publish_date = self.extract_publish_date(container)
                
                # Debug: Log what we extracted
                logger.info(f"Extracted data for {title}: price={price}, location={location}, date={publish_date}")
                
                # Debug logging for image extraction
                if not image:
                    logger.debug(f"No image found for listing: {title}")
                    # Try alternative image extraction
                    image = self.extract_image_alternative(container, href)
                    if image:
                        logger.debug(f"Found image with alternative method: {image}")
                    else:
                        # Log container HTML for debugging
                        logger.debug(f"Container HTML: {str(container)[:200]}...")
                
                # Only include offers from today
                if not self.is_today_offer(publish_date):
                    logger.debug(f"Skipping offer from {publish_date}: {title}")
                    continue
                
                listing = {
                    'id': listing_id,
                    'title': title,
                    'url': href,
                    'price': price or 'Cena do uzgodnienia',
                    'location': location or 'Brak',
                    'image': image or 'https://via.placeholder.com/300x200/007AFF/FFFFFF?text=iPhone',
                    'publish_date': publish_date
                }
                
                listings.append(listing)
                logger.info(f"Found TODAY'S listing: {title} - {price} - {location} - {publish_date}")
            
            # Remove duplicates
            unique_listings = []
            seen_ids = set()
            for listing in listings:
                if listing['id'] not in seen_ids:
                    unique_listings.append(listing)
                    seen_ids.add(listing['id'])
            
            logger.info(f"Found {len(unique_listings)} unique TODAY'S listings out of {len(listings)} total offers")
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
            # Get all text from the element first
            all_text = element.get_text()
            logger.info(f"All text from element for location: {all_text[:300]}...")
            
            # Look for location-date pattern in all text first (most reliable)
            # Pattern like "Murowana Goślina - Dzisiaj o 11:49"
            location_patterns = [
                r'([A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ\s\-]+)\s*-\s*(Dzisiaj o \d{1,2}:\d{2})',
                r'([A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ\s\-]+)\s*-\s*(Wczoraj o \d{1,2}:\d{2})',
                r'([A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ\s\-]+)\s*-\s*(Dzisiaj)',
                r'([A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ\s\-]+)\s*-\s*(Wczoraj)',
                r'([A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ\s\-]+)\s*-\s*(\d{1,2}\.\d{1,2}\.\d{4})'
            ]
            
            for pattern in location_patterns:
                location_match = re.search(pattern, all_text)
                if location_match:
                    location = location_match.group(1).strip()
                    logger.info(f"Found location with pattern '{pattern}': {location}")
                    return location
            
            # If no pattern match, try specific selectors
            location_selectors = [
                'p[data-testid="location-date"]',
                'span[data-testid="location-date"]',
                'p[data-testid="location"]',
                'span[data-testid="location"]',
                '.css-veheph',
                '.css-17o22yg',
                '.css-1a4brun',
                '[class*="location"]',
                '[class*="city"]',
                'small',
                'span[class*="css-"]',
                'p[class*="css-"]',
                '[class*="css-"][class*="location"]',
                '[class*="css-"][class*="city"]'
            ]
            
            for selector in location_selectors:
                location_elem = element.select_one(selector)
                if location_elem:
                    location_text = location_elem.get_text().strip()
                    logger.info(f"Checking location text with selector '{selector}': {location_text}")
                    
                    # Try the same patterns on this specific element
                    for pattern in location_patterns:
                        location_match = re.search(pattern, location_text)
                        if location_match:
                            location = location_match.group(1).strip()
                            logger.info(f"Found location with selector '{selector}' and pattern '{pattern}': {location}")
                            return location
                    
                    # Also try to extract just the location part if it looks like a city
                    if len(location_text) > 3 and len(location_text) < 50 and not any(char.isdigit() for char in location_text):
                        logger.info(f"Found potential location with selector '{selector}': {location_text}")
                        return location_text
            
            # Look for common Polish cities in all text
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
                     'Środa Wielkopolska', 'Gostyń', 'Rawicz', 'Kępno', 'Ostrzeszów', 'Brzesko',
                     'Murowana Goślina', 'Olszowice']
            
            for city in cities:
                if city.lower() in all_text.lower():
                    logger.info(f"Found city in all text: {city}")
                    return city
                    
            logger.info("No location found in any method")
        except Exception as e:
            logger.info(f"Error extracting location: {e}")
        return None
    
    def extract_image(self, element):
        """Extract image URL from listing element"""
        try:
            # Look for images in specific elements first - prioritize data attributes
            image_selectors = [
                'img[data-src]',
                'img[data-lazy-src]', 
                'img[data-original]',
                'img[src]',
                '.css-1bmvjcs img',
                '[class*="image"] img',
                '[class*="photo"] img',
                '[class*="thumbnail"] img',
                'img'
            ]
            
            for selector in image_selectors:
                img_elements = element.select(selector)
                for img_elem in img_elements:
                    # Try multiple attributes in order of preference
                    src = (img_elem.get('data-src') or 
                           img_elem.get('data-lazy-src') or 
                           img_elem.get('data-original') or 
                           img_elem.get('src'))
                    
                    if src:
                        # Clean and validate the URL
                        if src.startswith('/'):
                            src = urljoin('https://www.olx.pl', src)
                        
                        # Remove query parameters but keep the image ID
                        if '?' in src:
                            base_url = src.split('?')[0]
                            # Try to preserve image ID from query params
                            query_params = src.split('?')[1]
                            if 'id=' in query_params:
                                img_id = query_params.split('id=')[1].split('&')[0]
                                src = f"{base_url}?id={img_id}"
                            else:
                                src = base_url
                        
                        # More lenient validation - just check if it's a valid URL
                        if src.startswith('http'):
                            logger.debug(f"Found image with selector '{selector}': {src}")
                            return src
            
            # If no image found in the element, try parent elements
            parent = element.parent
            if parent:
                img = parent.find('img')
                if img:
                    src = (img.get('data-src') or 
                           img.get('data-lazy-src') or 
                           img.get('data-original') or 
                           img.get('src'))
                    if src:
                        if src.startswith('/'):
                            src = urljoin('https://www.olx.pl', src)
                        if '?' in src:
                            src = src.split('?')[0]
                        if src.startswith('http'):
                            logger.debug(f"Found image in parent: {src}")
                            return src
            
            # Try grandparent elements too
            grandparent = element.parent.parent if element.parent else None
            if grandparent:
                img = grandparent.find('img')
                if img:
                    src = (img.get('data-src') or 
                           img.get('data-lazy-src') or 
                           img.get('data-original') or 
                           img.get('src'))
                    if src:
                        if src.startswith('/'):
                            src = urljoin('https://www.olx.pl', src)
                        if '?' in src:
                            src = src.split('?')[0]
                        if src.startswith('http'):
                            logger.debug(f"Found image in grandparent: {src}")
                            return src
                            
        except Exception as e:
            logger.debug(f"Error extracting image: {e}")
        return None
    
    def extract_image_alternative(self, element, url):
        """Alternative image extraction method"""
        try:
            # Try to find any img tag in the entire element tree
            all_imgs = element.find_all('img')
            for img in all_imgs:
                src = (img.get('data-src') or 
                       img.get('data-lazy-src') or 
                       img.get('data-original') or 
                       img.get('src'))
                if src:
                    if src.startswith('/'):
                        src = urljoin('https://www.olx.pl', src)
                    if src.startswith('http'):
                        logger.debug(f"Alternative method found image: {src}")
                        return src
            
            # Try to extract from the offer URL itself (sometimes images are in the URL structure)
            if '/oferta/' in url:
                # This is a fallback - sometimes OLX has predictable image URLs
                # But we'll skip this for now as it's not reliable
                pass
                
        except Exception as e:
            logger.debug(f"Error in alternative image extraction: {e}")
        return None
    
    def extract_publish_date(self, element):
        """Extract publish date from listing element"""
        try:
            # Get all text from the element first
            all_text = element.get_text()
            logger.info(f"All text from element: {all_text[:300]}...")
            
            # Look for date patterns in all text first (most reliable)
            date_patterns = [
                r'(Dzisiaj o \d{1,2}:\d{2})',  # "Dzisiaj o 11:49"
                r'(Wczoraj o \d{1,2}:\d{2})',  # "Wczoraj o 15:20"
                r'(Dzisiaj)',                   # Just "Dzisiaj"
                r'(Wczoraj)',                   # Just "Wczoraj"
                r'(\d{1,2}\.\d{1,2}\.\d{4})',  # "17.10.2024"
                r'(\d{1,2} \w+ \d{4})',        # "17 października 2024"
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, all_text)
                if date_match:
                    date_found = date_match.group(1)
                    logger.info(f"Found date with pattern '{pattern}': {date_found}")
                    return date_found
            
            # If no date found in text, try specific selectors
            date_selectors = [
                'p[data-testid="location-date"]',
                'span[data-testid="location-date"]',
                'p[data-testid="date"]',
                'span[data-testid="date"]',
                '.css-veheph',
                '.css-17o22yg',
                '.css-1a4brun',
                '[class*="date"]',
                '[class*="time"]',
                'small',
                'span[class*="css-"]',
                'p[class*="css-"]',
                '[class*="css-"][class*="date"]',
                '[class*="css-"][class*="time"]'
            ]
            
            for selector in date_selectors:
                date_elem = element.select_one(selector)
                if date_elem:
                    date_text = date_elem.get_text().strip()
                    logger.info(f"Checking date text with selector '{selector}': {date_text}")
                    
                    # Look for date patterns in this specific element
                    for pattern in date_patterns:
                        date_match = re.search(pattern, date_text)
                        if date_match:
                            date_found = date_match.group(1)
                            logger.info(f"Found date with selector '{selector}' and pattern '{pattern}': {date_found}")
                            return date_found
            
            # If still no date found, return None (don't assume it's recent)
            logger.info("No date found - will exclude this offer")
            return None
                
        except Exception as e:
            logger.info(f"Error extracting publish date: {e}")
            return None
    
    def is_today_offer(self, date_str):
        """Check if the offer is from today - ONLY include offers with 'Dzisiaj'"""
        if not date_str:
            # If no date found, exclude it (be strict)
            logger.info("No date found - EXCLUDING offer")
            return False
        
        try:
            # ONLY include offers with "Dzisiaj" (Today)
            if 'Dzisiaj' in date_str:
                logger.info(f"Found 'Dzisiaj' in date: {date_str} - INCLUDING")
                return True
            
            # Exclude everything else (Wczoraj, specific dates, etc.)
            logger.info(f"Date is not 'Dzisiaj': {date_str} - EXCLUDING")
            return False
                
        except Exception as e:
            logger.info(f"Error checking date: {e} - EXCLUDING")
            return False
    
    def send_discord_notification(self, listing):
        """Send Discord webhook notification"""
        try:
            # Prepare Discord embed data
            embed_data = {
                "title": listing['title'],
                "url": listing['url'],
                "color": 3066993,  # Green color
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "description": f"📌 {listing['title']}\n💰 Cena: {listing['price']}\n📍 Lokalizacja: {listing['location']}\n📅 Data: {listing.get('publish_date', 'Dzisiaj')}"
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
