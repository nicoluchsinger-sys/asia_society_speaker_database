"""
Selenium-based web scraper for Asia Society events
Uses a real browser to avoid 403 errors and handle dynamic content
Supports scraping from global events page or location-specific pages
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
import logging
from datetime import datetime
import re
from database import SpeakerDatabase

# Configure logging
logger = logging.getLogger(__name__)


class SeleniumEventScraper:
    def __init__(self, base_url="https://asiasociety.org/events/past", headless=True):
        """
        Initialize Selenium scraper

        Args:
            base_url: Starting URL for events (default: global events from all Asia Society locations)
                - https://asiasociety.org/events/past (global - all locations)
                - https://asiasociety.org/switzerland/events/past (Switzerland only)
                - https://asiasociety.org/new-york/events/past (New York only)
            headless: If True, browser runs in background. If False, you can watch it work.
        """
        self.base_url = base_url
        self.driver = None
        self.headless = headless
        self.is_global = '/events/past' in base_url and base_url.count('/') == 4
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
            logger.info("✓ Chrome WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"❌ Error initializing Chrome WebDriver: {e}")
            logger.info("\nTroubleshooting:")
            logger.info("1. Make sure Chrome browser is installed")
            logger.info("2. Try: pip3 install --upgrade selenium")
            logger.info("3. If issues persist, you may need to download ChromeDriver manually")
            raise

    def fetch_page(self, url, wait_time=5):
        """
        Fetch a page using Selenium

        Args:
            url: URL to fetch
            wait_time: Seconds to wait for page to load
        """
        try:
            logger.info(f"   Loading: {url}")
            self.driver.get(url)

            # Wait for page to load (wait for body tag)
            WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Give it an extra moment for dynamic content
            time.sleep(2)

            return self.driver.page_source

        except TimeoutException:
            logger.warning(f"   ⚠ Timeout loading page")
            return None
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
            return None

    def extract_event_links(self, html):
        """Extract event page URLs from the events listing page"""
        soup = BeautifulSoup(html, 'html.parser')
        event_links = []
        seen_urls = set()  # For deduplication

        # Find all links
        links = soup.find_all('a', href=True)

        # Patterns to EXCLUDE (known bad links)
        exclude_patterns = [
            '/events/past',
            '/news/',
            '/about',
            '/center',
            '/policy',
            '/video/',
            '/podcast/',
        ]

        for link in links:
            href = link['href']

            # Look for event-specific URLs with /events/ in path
            if '/events/' not in href:
                continue

            # Convert relative URLs to absolute
            if href.startswith('http'):
                full_url = href
            elif href.startswith('/'):
                full_url = f"https://asiasociety.org{href}"
            else:
                continue

            # Check if URL should be excluded
            should_exclude = False
            for pattern in exclude_patterns:
                if pattern in full_url:
                    should_exclude = True
                    break

            # Skip if it ends with just /events or /events/past
            if full_url.endswith('/events') or full_url.endswith('/events/past'):
                should_exclude = True

            # Check it's an actual event (has something after /events/)
            parts = full_url.split('/events/')
            if len(parts) < 2 or len(parts[1]) < 5:
                should_exclude = True

            # Deduplicate
            if full_url in seen_urls:
                should_exclude = True

            if not should_exclude:
                seen_urls.add(full_url)
                event_links.append(full_url)

        return event_links

    def extract_location_from_url(self, url):
        """Extract location from URL path (e.g., /switzerland/, /new-york/)"""
        try:
            # Parse URL: https://asiasociety.org/location/events/event-name
            parts = url.replace('https://asiasociety.org/', '').split('/')
            if len(parts) >= 1:
                location_slug = parts[0]
                # Convert slug to readable name
                location = location_slug.replace('-', ' ').title()
                return location
        except Exception:
            pass
        return "Unknown"

    def extract_date_from_page(self, soup, html):
        """
        Extract event date using multiple strategies

        Returns date string or None
        """
        # Patterns that capture the full date string
        date_patterns = [
            # Full month name: January 20, 2026
            r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})',
            # Abbreviated month: Jan 20, 2026 or 20 Jan 2026
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})',
            # Day abbreviation + date: Mon 19 Jan 2026, Tue 20 Jan 2026
            r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})',
            # European format: 20 January 2026 or 20 Jan 2026
            r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})',
            # ISO format: 2026-01-20
            r'(\d{4}-\d{2}-\d{2})',
            # US format: 01/20/2026
            r'(\d{1,2}/\d{1,2}/\d{4})',
        ]

        # Strategy 0: Look specifically for event-details widget (Asia Society specific)
        event_details = soup.find('div', class_='event-details-wdgt')
        if event_details:
            text = event_details.get_text(separator=' ', strip=True)
            for pattern in date_patterns:
                match = re.search(pattern, text, re.I)
                if match:
                    return match.group(1)

        # Strategy 1: Look for elements with date-related classes/attributes
        date_selectors = [
            ('time', {}),
            ('span', {'class': re.compile('date', re.I)}),
            ('div', {'class': re.compile('date', re.I)}),
            ('p', {'class': re.compile('date', re.I)}),
            ('span', {'class': re.compile('event-date', re.I)}),
            ('div', {'class': re.compile('event-date', re.I)}),
            ('span', {'class': re.compile('meta', re.I)}),
            ('div', {'class': re.compile('meta', re.I)}),
        ]

        for tag, attrs in date_selectors:
            elements = soup.find_all(tag, attrs) if attrs else soup.find_all(tag)
            for elem in elements:
                text = elem.get_text(strip=True)
                for pattern in date_patterns:
                    match = re.search(pattern, text, re.I)
                    if match:
                        return match.group(1)

        # Strategy 2: Look for datetime attribute on time elements
        time_elements = soup.find_all('time')
        for time_elem in time_elements:
            datetime_attr = time_elem.get('datetime')
            if datetime_attr:
                # Try to extract date from datetime attribute
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', datetime_attr)
                if date_match:
                    return date_match.group(1)

        # Strategy 3: Look in meta tags
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            content = meta.get('content', '')
            name = meta.get('name', '').lower()
            prop = meta.get('property', '').lower()
            if 'date' in name or 'date' in prop:
                for pattern in date_patterns:
                    match = re.search(pattern, content, re.I)
                    if match:
                        return match.group(1)

        # Strategy 4: Search entire body text for date patterns (more thorough)
        body_text = soup.get_text(separator=' ', strip=True)
        for pattern in date_patterns:
            match = re.search(pattern, body_text, re.I)
            if match:
                return match.group(1)

        return None

    def extract_title_from_page(self, soup, url):
        """
        Extract event title using multiple strategies

        Returns title string
        """
        # Strategy 1: Look for og:title meta tag (most reliable)
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content'].strip()
            # Remove site suffix if present
            if ' | Asia Society' in title:
                title = title.split(' | Asia Society')[0].strip()
            if title and len(title) > 5:
                return title

        # Strategy 2: Look for title tag
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Remove site suffix
            if ' | Asia Society' in title:
                title = title.split(' | Asia Society')[0].strip()
            if title and len(title) > 5:
                return title

        # Strategy 3: Look for h1 with specific classes
        h1_classes = ['event-title', 'page-title', 'entry-title', 'article-title']
        for cls in h1_classes:
            h1 = soup.find('h1', class_=re.compile(cls, re.I))
            if h1:
                title = h1.get_text(strip=True)
                if title and len(title) > 5:
                    return title

        # Strategy 4: Look for any h1 that's not just the location name
        location = self.extract_location_from_url(url)
        h1_tags = soup.find_all('h1')
        for h1 in h1_tags:
            title = h1.get_text(strip=True)
            # Skip if it's just the location name
            if title.lower() != location.lower() and len(title) > 5:
                return title

        # Strategy 5: Look for h2 as fallback
        h2_tags = soup.find_all('h2')
        for h2 in h2_tags:
            title = h2.get_text(strip=True)
            if len(title) > 10:
                return title

        # Fallback: extract from URL
        parts = url.split('/events/')
        if len(parts) > 1:
            slug = parts[1].rstrip('/')
            title = slug.replace('-', ' ').title()
            return title

        return "Unknown Event"

    def parse_event_page(self, html, url):
        """Extract event information from an event page"""
        soup = BeautifulSoup(html, 'html.parser')

        # Extract location from URL
        location = self.extract_location_from_url(url)

        # Extract title
        title = self.extract_title_from_page(soup, url)

        # Extract date
        event_date = self.extract_date_from_page(soup, html)

        event_data = {
            'url': url,
            'title': title,
            'event_date': event_date,
            'location': location,
            'body_text': '',
            'raw_html': html
        }

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

    def _calculate_historical_start_page(self, db: SpeakerDatabase) -> int:
        """
        Calculate where to start historical backfill based on database size.

        Formula: (events_in_db / 20) + 10
        - Assumes ~20 events per page
        - Adds 10-page buffer to ensure overlap with known events
        - Automatically adjusts as database grows

        Args:
            db: SpeakerDatabase instance

        Returns:
            Starting page number for historical scraping
        """
        stats = db.get_statistics()
        events_in_db = stats['total_events']
        calculated_page = (events_in_db // 20) + 10

        # Minimum page 30 to avoid re-scraping early pages
        return max(30, calculated_page)

    def scrape_events(self, db: SpeakerDatabase, limit=None, mode='new', start_page=None, max_pages='auto'):
        """
        Main scraping workflow with two modes:

        MODE 1: 'new' - Capture newly published events
        - Starts at page 0
        - Stops when hitting consecutive already-scraped events
        - Efficient for catching new publications

        MODE 2: 'historical' - Backfill historical events
        - Auto-calculates start_page based on DB size
        - Scrapes forward from that page
        - Gradually works through entire event history

        Args:
            db: SpeakerDatabase instance
            limit: Maximum number of events to scrape
            mode: 'new' or 'historical' (default: 'new')
            start_page: Override auto-calculated start page (historical mode only)
            max_pages: Maximum pages to check ('auto' or number)
        """
        # Determine starting page based on mode
        if mode == 'new':
            page = 0
            logger.info("="*70)
            logger.info("NEW EVENTS SCRAPER - Capturing recent publications")
            logger.info(f"Source: {self.base_url}")
            logger.info("="*70)
        elif mode == 'historical':
            if start_page is None:
                page = self._calculate_historical_start_page(db)
            else:
                page = start_page
            logger.info("="*70)
            logger.info("HISTORICAL BACKFILL SCRAPER - Finding older events")
            logger.info(f"Source: {self.base_url}")
            logger.info(f"Starting from page {page} (auto-calculated from DB size)")
            logger.info("="*70)
        else:
            raise ValueError(f"Invalid mode: {mode}. Must be 'new' or 'historical'")

        try:
            # Fetch events from listing pages (with pagination)
            all_event_links = []

            logger.info(f"\n1. Fetching events listing pages...")

            # Get already-scraped URLs from database
            cursor = db.conn.cursor()
            cursor.execute('SELECT url FROM events')
            already_scraped = set(row[0] for row in cursor.fetchall())
            logger.info(f"   Database contains {len(already_scraped)} already-scraped events")

            consecutive_empty_pages = 0
            consecutive_scraped_pages = 0  # Track pages with all already-scraped events (new mode)
            max_consecutive_empty = 3
            max_consecutive_scraped = 5  # Stop after 5 pages of all already-scraped (new mode)

            while True:
                page_url = f"{self.base_url}?page={page}"
                logger.info(f"   Page {page}: {page_url}")
                html = self.fetch_page(page_url)

                if not html:
                    logger.error("   ❌ Failed to fetch page")
                    consecutive_empty_pages += 1
                    if consecutive_empty_pages >= max_consecutive_empty:
                        logger.info(f"   Stopping after {consecutive_empty_pages} consecutive failures")
                        break
                    page += 1
                    continue

                # Extract event links from this page
                page_links = self.extract_event_links(html)
                if not page_links:
                    logger.info("   No events found on this page")
                    consecutive_empty_pages += 1
                    if consecutive_empty_pages >= max_consecutive_empty:
                        logger.info(f"   Stopping after {consecutive_empty_pages} consecutive empty pages")
                        break
                    page += 1
                    continue

                # Reset empty page counter when we find events
                consecutive_empty_pages = 0

                new_links = [l for l in page_links if l not in all_event_links]
                all_event_links.extend(new_links)

                # Count how many are actually new (not in DB)
                new_on_page = [l for l in page_links if l not in already_scraped]
                new_unscraped = [l for l in all_event_links if l not in already_scraped]
                logger.info(f"   Found {len(new_links)} events on page ({len(new_on_page)} new, total collected: {len(new_unscraped)})")

                # MODE-SPECIFIC STOP LOGIC
                if mode == 'new':
                    # Stop if this page has all already-scraped events
                    if len(new_on_page) == 0:
                        consecutive_scraped_pages += 1
                        if consecutive_scraped_pages >= max_consecutive_scraped:
                            logger.info(f"   ✓ Stopping: {consecutive_scraped_pages} consecutive pages with all already-scraped events")
                            break
                    else:
                        consecutive_scraped_pages = 0

                page += 1

                # Stop conditions
                if max_pages and max_pages != 'auto' and page >= max_pages:
                    logger.info(f"   Reached max pages limit ({max_pages})")
                    break

                # For historical mode, stop when we have enough new events
                if mode == 'historical' and limit and len(new_unscraped) >= limit:
                    logger.info(f"   ✓ Found {len(new_unscraped)} new events, meeting limit")
                    break

                # For auto mode, keep going until we hit consecutive empty pages
                # (handled by consecutive_empty_pages logic above)

                time.sleep(1)  # Brief pause between listing pages

            # Filter to only new events
            new_event_links = [l for l in all_event_links if l not in already_scraped]
            logger.info(f"\n2. Total unique events found: {len(all_event_links)} ({len(new_event_links)} new)")

            event_links = new_event_links
            if limit and len(event_links) > limit:
                event_links = event_links[:limit]
                logger.info(f"   Limiting to {limit} new events for this run")
            elif len(event_links) == 0:
                logger.info(f"   No new events to scrape!")
            else:
                logger.info(f"   Will scrape {len(event_links)} new events")

            # Scrape each event
            logger.info(f"\n3. Scraping individual event pages...")
            scraped_count = 0

            for i, event_url in enumerate(event_links, 1):
                logger.info(f"\n   [{i}/{len(event_links)}]")

                event_html = self.fetch_page(event_url)
                if not event_html:
                    logger.warning("      ⚠ Failed to fetch")
                    continue

                # Parse event data
                event_data = self.parse_event_page(event_html, event_url)

                if not event_data['body_text'] or len(event_data['body_text']) < 100:
                    logger.warning("      ⚠ Insufficient content found")
                    continue

                # Save to database
                try:
                    event_id = db.add_event(
                        url=event_data['url'],
                        title=event_data['title'],
                        body_text=event_data['body_text'],
                        raw_html=event_data['raw_html'],
                        event_date=event_data['event_date'],
                        location=event_data['location']
                    )
                    logger.info(f"      ✓ Saved (Event ID: {event_id})")
                    logger.info(f"        Title: {event_data['title'][:60]}...")
                    logger.info(f"        Location: {event_data['location']}")
                    if event_data['event_date']:
                        logger.info(f"        Date: {event_data['event_date']}")
                    logger.info(f"        Content length: {len(event_data['body_text'])} chars")
                    scraped_count += 1

                except Exception as e:
                    logger.error(f"      ❌ Database error: {e}")

                # Be polite - wait between requests
                time.sleep(2)

            logger.info("\n" + "="*70)
            logger.info(f"Scraping complete: {scraped_count} events saved to database")
            logger.info("="*70)

            return scraped_count

        finally:
            # Always close the browser
            self.close()

    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            logger.info("\n✓ Browser closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # Test the Selenium scraper
    logger.info("Testing Selenium Scraper")
    logger.info("If you want to watch the browser work, change headless=False")
    print()

    with SpeakerDatabase() as db:
        # Test with global events page
        scraper = SeleniumEventScraper(
            base_url="https://asiasociety.org/events/past",
            headless=True
        )
        scraper.scrape_events(db, limit=3)

        # Show statistics
        stats = db.get_statistics()
        logger.info(f"\nDatabase Statistics:")
        logger.info(f"  Total events: {stats['total_events']}")
        logger.info(f"  Processed: {stats['processed_events']}")
        logger.info(f"  Pending: {stats['total_events'] - stats['processed_events']}")
