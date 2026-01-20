"""
Main script to scrape events and extract speaker information
"""

import os
from database import SpeakerDatabase
from scraper import EventScraper
from speaker_extractor import SpeakerExtractor
import json

def load_api_key():
    """Load API key from .env file or environment"""
    # Try to load from .env file
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ANTHROPIC_API_KEY='):
                    key = line.split('=', 1)[1].strip()
                    os.environ['ANTHROPIC_API_KEY'] = key
                    return key
    
    # Try environment variable
    return os.getenv('ANTHROPIC_API_KEY')


def scrape_events(limit=None):
    """Step 1: Scrape events from website and save to database"""
    print("\n" + "🌐 STEP 1: SCRAPING EVENTS FROM WEBSITE")
    print("="*70)
    
    with SpeakerDatabase() as db:
        scraper = EventScraper()
        count = scraper.scrape_events(db, limit=limit)
        
        stats = db.get_statistics()
        print(f"\n📊 Current Database Status:")
        print(f"   Total events in database: {stats['total_events']}")
        print(f"   Unprocessed events: {stats['total_events'] - stats['processed_events']}")
        
        return count


def extract_speakers():
    """Step 2: Use AI to extract speakers from scraped events"""
    print("\n\n" + "🤖 STEP 2: EXTRACTING SPEAKERS WITH AI")
    print("="*70)
    
    # Load API key
    api_key = load_api_key()
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not found!")
        print("   Please create a .env file with: ANTHROPIC_API_KEY=your_key_here")
        return 0
    
    print("✓ API key loaded")
    
    with SpeakerDatabase() as db:
        # Get unprocessed events
        unprocessed = db.get_unprocessed_events()
        
        if not unprocessed:
            print("\n✓ All events have been processed!")
            return 0
        
        print(f"\nFound {len(unprocessed)} unprocessed event(s)")
        print("-"*70)
        
        # Initialize AI extractor
        extractor = SpeakerExtractor(api_key=api_key)
        
        # Process each event
        total_speakers = 0
        
        for event_id, url, title, body_text in unprocessed:
            print(f"\n📄 Processing Event ID {event_id}")
            print(f"   Title: {title[:70]}...")
            
            # Extract speakers using AI
            result = extractor.extract_speakers(title, body_text)
            
            if result['success']:
                speakers = result['speakers']
                print(f"   ✓ Found {len(speakers)} speaker(s)")
                
                # Save each speaker to database
                for speaker_data in speakers:
                    # Add speaker to speakers table
                    speaker_id = db.add_speaker(
                        name=speaker_data.get('name'),
                        title=speaker_data.get('title'),
                        affiliation=speaker_data.get('affiliation'),
                        bio=speaker_data.get('bio')
                    )
                    
                    # Link speaker to event
                    db.link_speaker_to_event(
                        event_id=event_id,
                        speaker_id=speaker_id,
                        role_in_event=speaker_data.get('role_in_event'),
                        extracted_info=json.dumps(speaker_data)
                    )
                    
                    print(f"     - {speaker_data.get('name')} ({speaker_data.get('role_in_event', 'participant')})")
                    total_speakers += 1
                
                # Mark event as processed
                db.mark_event_processed(event_id, 'completed')
                
            else:
                print(f"   ❌ Error: {result['error']}")
                db.mark_event_processed(event_id, 'failed')
        
        print("\n" + "="*70)
        print(f"✓ Extraction complete: {total_speakers} speaker records created")
        
        return total_speakers


def show_statistics():
    """Display database statistics and sample data"""
    print("\n\n" + "📊 DATABASE STATISTICS")
    print("="*70)
    
    with SpeakerDatabase() as db:
        stats = db.get_statistics()
        
        print(f"\nEvents:")
        print(f"  Total events: {stats['total_events']}")
        print(f"  Processed: {stats['processed_events']}")
        print(f"  Pending: {stats['total_events'] - stats['processed_events']}")
        
        print(f"\nSpeakers:")
        print(f"  Total unique speakers: {stats['total_speakers']}")
        print(f"  Total speaker-event connections: {stats['total_connections']}")
        
        # Show some sample speakers
        speakers = db.get_all_speakers()
        if speakers:
            print(f"\n📋 Sample Speakers (showing first 10):")
            print("-"*70)
            for speaker in speakers[:10]:
                speaker_id, name, title, affiliation, bio, first_seen, last_updated = speaker
                print(f"\n  {name}")
                if title:
                    print(f"    Title: {title}")
                if affiliation:
                    print(f"    Affiliation: {affiliation}")
                
                # Get events for this speaker
                events = db.get_speaker_events(speaker_id)
                if events:
                    print(f"    Events: {len(events)}")


def export_speakers_to_csv():
    """Export all speakers to a CSV file"""
    import csv
    
    print("\n\n" + "💾 EXPORTING SPEAKERS TO CSV")
    print("="*70)
    
    with SpeakerDatabase() as db:
        speakers = db.get_all_speakers()
        
        if not speakers:
            print("No speakers to export")
            return
        
        filename = f"speakers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['ID', 'Name', 'Title', 'Affiliation', 'Bio', 'First Seen', 'Last Updated', 'Number of Events'])
            
            for speaker in speakers:
                speaker_id, name, title, affiliation, bio, first_seen, last_updated = speaker
                events = db.get_speaker_events(speaker_id)
                writer.writerow([speaker_id, name, title or '', affiliation or '', bio or '', first_seen, last_updated, len(events)])
        
        print(f"✓ Exported {len(speakers)} speakers to {filename}")


def main():
    """Main workflow"""
    print("="*70)
    print("ASIA SOCIETY SWITZERLAND - SPEAKER DATABASE BUILDER")
    print("="*70)
    
    print("\nThis tool will:")
    print("1. Scrape event pages from asiasociety.org/switzerland")
    print("2. Use AI to extract speaker information")
    print("3. Store everything in a SQLite database")
    
    # Step 1: Scrape events
    print("\n" + "-"*70)
    response = input("\nHow many events to scrape? (Enter number or 'all'): ").strip()
    
    if response.lower() == 'all':
        limit = None
    else:
        try:
            limit = int(response)
        except ValueError:
            limit = 5
            print(f"Invalid input, using default: {limit}")
    
    scraped = scrape_events(limit=limit)
    
    if scraped == 0:
        print("\n⚠ No events were scraped. Exiting.")
        return
    
    # Step 2: Extract speakers
    print("\n" + "-"*70)
    response = input("\nProceed with speaker extraction using AI? (y/n): ").strip().lower()
    
    if response == 'y':
        extracted = extract_speakers()
    else:
        print("\nSkipping speaker extraction. Run this script again to process events.")
        return
    
    # Show results
    show_statistics()
    
    # Export option
    print("\n" + "-"*70)
    response = input("\nExport speakers to CSV? (y/n): ").strip().lower()
    
    if response == 'y':
        export_speakers_to_csv()
    
    print("\n" + "="*70)
    print("✓ COMPLETE")
    print("="*70)
    print(f"\nDatabase saved as: speakers.db")
    print("You can:")
    print("  - Run this script again to scrape more events")
    print("  - View the database with SQLite browser")
    print("  - Use the database for further analysis")


if __name__ == "__main__":
    from datetime import datetime
    main()
