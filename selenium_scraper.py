"""
Selenium-based web scraper for Asia Society events
Uses a real browser to avoid 403 errors and handle dynamic content
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import time
from datetime import datetime
import re
from database import SpeakerDatabase


class SeleniumEventScraper:
    def __init__(self, base_url="https://asiasociety.org/switzerland/events/past", headless=True):
        """
        Initialize Selenium scraper
        
        Args:
            base_url: Starting URL for events
            headless: If True, browser runs in background. If False, you can watch it work.
        """
        self.base_url = base_url
        self.driver = None
        self.headless = headless
        self.setup_driver()
    
    def setup_driver(self):
        """Set up Chrome WebDriver with options"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')  # Run in background
        
        # These options make it look more like a real browser
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set a realistic user agent
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            # Selenium 4.6+ can auto-download the driver
            self.driver = webdriver.Chrome(options=chrome_options)
            print("✓ Chrome WebDriver initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing Chrome WebDriver: {e}")
            print("\nTroubleshooting:")
            print("1. Make sure Chrome browser is installed")
            print("2. Try: pip3 install --upgrade selenium")
            print("3. If issues persist, you may need to download ChromeDriver manually")
            raise
    
    def fetch_page(self, url, wait_time=5):
        """
        Fetch a page using Selenium
        
        Args:
            url: URL to fetch
            wait_time: Seconds to wait for page to load
        """
        try:
            print(f"   Loading: {url}")
            self.driver.get(url)
            
            # Wait for page to load (wait for body tag)
            WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Give it an extra moment for dynamic content
            time.sleep(2)
            
            return self.driver.page_source
        
        except TimeoutException:
            print(f"   ⚠ Timeout loading page")
            return None
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None
    
    def extract_event_links(self, html):
        """Extract event page URLs from the events listing page"""
        soup = BeautifulSoup(html, 'html.parser')
        event_links = []
        
        # Find all links
        links = soup.find_all('a', href=True)
        
        # Patterns to EXCLUDE (known bad links)
        exclude_patterns = [
            '/events/past',
            '/events/state-asia',  # Future events
            '/switzerland/events$',  # Main events page (ends with /events)
            '/news/',
            '/about',
            '/center',
            '/policy',
            'asiasociety.org/events$',  # Global events page
        ]
        
        for link in links:
            href = link['href']
            
            # Look for event-specific URLs under switzerland
            if '/switzerland/events/' in href or (href.startswith('/events/') and 'switzerland' in self.base_url):
                # Convert relative URLs to absolute
                if href.startswith('http'):
                    full_url = href
                elif href.startswith('/'):
                    full_url = f"https://asiasociety.org{href}"
                else:
                    full_url = f"https://asiasociety.org/switzerland/{href}"
                
                # Check if URL should be excluded
                should_exclude = False
                for pattern in exclude_patterns:
                    if pattern in full_url or full_url.endswith(pattern.replace('$', '')):
                        should_exclude = True
                        break
                
                # Only add if not excluded and not duplicate
                if not should_exclude and full_url not in event_links and full_url != self.base_url:
                    # Additional check: URL should have something after /events/
                    # and should be reasonably long (actual event names are long)
                    parts = full_url.split('/events/')
                    if len(parts) > 1 and len(parts[1]) > 5:
                        event_links.append(full_url)
        
        return event_links
    
    def parse_event_page(self, html, url):
        """Extract event information from an event page"""
        soup = BeautifulSoup(html, 'html.parser')
        
        event_data = {
            'url': url,
            'title': '',
            'event_date': None,
            'body_text': '',
            'raw_html': html
        }
        
        # Extract title
        title_tag = soup.find('h1')
        if title_tag:
            event_data['title'] = title_tag.get_text(strip=True)
        else:
            title_tag = soup.find('title')
            if title_tag:
                event_data['title'] = title_tag.get_text(strip=True)
        
        # Try to extract date
        date_patterns = [
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',
            r'\b\d{4}-\d{2}-\d{2}\b'
        ]
        
        date_elements = soup.find_all(['time', 'span', 'div'], class_=re.compile('date', re.I))
        for elem in date_elements:
            date_text = elem.get_text(strip=True)
            for pattern in date_patterns:
                match = re.search(pattern, date_text)
                if match:
                    event_data['event_date'] = match.group(0)
                    break
            if event_data['event_date']:
                break
        
        # Extract main content
        content_selectors = [
            ('article', None),
            ('div', re.compile('content|body|description|detail|main', re.I)),
            ('section', re.compile('content|body|description|detail|main', re.I)),
        ]
        
        body_texts = []
        for tag, class_pattern in content_selectors:
            if class_pattern:
                areas = soup.find_all(tag, class_=class_pattern)
            else:
                areas = soup.find_all(tag)
            
            for area in areas:
                # Remove unwanted elements
                for unwanted in area(['script', 'style', 'nav', 'footer', 'header']):
                    unwanted.decompose()
                
                text = area.get_text(separator=' ', strip=True)
                if len(text) > 100:
                    body_texts.append(text)
        
        # Fallback to paragraphs if no content found
        if not body_texts:
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 50:
                    body_texts.append(text)
        
        event_data['body_text'] = '\n\n'.join(body_texts)
        
        return event_data
    
    def scrape_events(self, db: SpeakerDatabase, limit=None):
        """
        Main scraping workflow using Selenium
        
        Args:
            db: SpeakerDatabase instance
            limit: Maximum number of events to scrape
        """
        print("="*70)
        print("Starting Selenium-based scrape of Asia Society Switzerland events")
        print("="*70)
        
        try:
            # Fetch events listing page
            print(f"\n1. Fetching events listing page: {self.base_url}")
            html = self.fetch_page(self.base_url)
            
            if not html:
                print("❌ Failed to fetch events page")
                return 0
            
            # Extract event links
            print("\n2. Extracting event links...")
            event_links = self.extract_event_links(html)
            print(f"   Found {len(event_links)} potential event links")
            
            if limit:
                event_links = event_links[:limit]
                print(f"   Limiting to {limit} events for this run")
            
            # Scrape each event
            print(f"\n3. Scraping individual event pages...")
            scraped_count = 0
            
            for i, event_url in enumerate(event_links, 1):
                print(f"\n   [{i}/{len(event_links)}]")
                
                event_html = self.fetch_page(event_url)
                if not event_html:
                    print("      ⚠ Failed to fetch")
                    continue
                
                # Parse event data
                event_data = self.parse_event_page(event_html, event_url)
                
                if not event_data['body_text'] or len(event_data['body_text']) < 100:
                    print("      ⚠ Insufficient content found")
                    continue
                
                # Save to database
                try:
                    event_id = db.add_event(
                        url=event_data['url'],
                        title=event_data['title'],
                        body_text=event_data['body_text'],
                        raw_html=event_data['raw_html'],
                        event_date=event_data['event_date']
                    )
                    print(f"      ✓ Saved (Event ID: {event_id})")
                    print(f"        Title: {event_data['title'][:60]}...")
                    if event_data['event_date']:
                        print(f"        Date: {event_data['event_date']}")
                    print(f"        Content length: {len(event_data['body_text'])} chars")
                    scraped_count += 1
                    
                except Exception as e:
                    print(f"      ❌ Database error: {e}")
                
                # Be polite - wait between requests
                time.sleep(2)
            
            print("\n" + "="*70)
            print(f"Scraping complete: {scraped_count} events saved to database")
            print("="*70)
            
            return scraped_count
        
        finally:
            # Always close the browser
            self.close()
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            print("\n✓ Browser closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # Test the Selenium scraper
    print("Testing Selenium Scraper")
    print("If you want to watch the browser work, change headless=False")
    print()
    
    with SpeakerDatabase() as db:
        # headless=False will show you the browser window
        # headless=True runs it in the background
        scraper = SeleniumEventScraper(headless=True)
        scraper.scrape_events(db, limit=3)
        
        # Show statistics
        stats = db.get_statistics()
        print(f"\nDatabase Statistics:")
        print(f"  Total events: {stats['total_events']}")
        print(f"  Processed: {stats['processed_events']}")
        print(f"  Pending: {stats['total_events'] - stats['processed_events']}")
