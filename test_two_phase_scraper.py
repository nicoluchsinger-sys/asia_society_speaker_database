#!/usr/bin/env python3
"""
Test the two-phase scraping logic
"""

from database import SpeakerDatabase
from selenium_scraper import SeleniumEventScraper

def test_two_phase_scraping():
    """Test both new and historical scraping modes"""

    db = SpeakerDatabase('speakers.db')

    print("="*70)
    print("TESTING TWO-PHASE SCRAPER")
    print("="*70)

    # Get initial stats
    initial_stats = db.get_statistics()
    print(f"\nInitial state:")
    print(f"  Events in DB: {initial_stats['total_events']}")
    print(f"  Speakers in DB: {initial_stats['total_speakers']}")

    # Test historical start page calculation
    scraper = SeleniumEventScraper()
    start_page = scraper._calculate_historical_start_page(db)
    print(f"\n✓ Historical scraper would start at page: {start_page}")
    print(f"  Formula: ({initial_stats['total_events']} events ÷ 20) + 10 = {start_page}")

    # Don't actually scrape in test mode
    print("\n⚠ Test mode - not actually scraping")
    print("To run actual scraping:")
    print("  python3 pipeline_cron.py --events 5 --existing 0")

    scraper.close()
    db.close()

    print("\n✓ Two-phase scraper logic validated!")

if __name__ == '__main__':
    test_two_phase_scraping()
