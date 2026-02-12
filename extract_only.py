# extract_only.py
import os
from database import SpeakerDatabase
from speaker_extractor import SpeakerExtractor
import json


def get_db_path():
    """Get database path - /data/speakers.db on Railway, ./speakers.db locally"""
    if os.path.exists('/data'):
        return '/data/speakers.db'
    return './speakers.db'


# Load API key
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('ANTHROPIC_API_KEY='):
                key = line.split('=', 1)[1].strip()
                os.environ['ANTHROPIC_API_KEY'] = key

print("🤖 EXTRACTING SPEAKERS WITH AI")
print("="*70)

db_path = get_db_path()
with SpeakerDatabase(db_path) as db:
    unprocessed = db.get_unprocessed_events()
    
    print(f"Found {len(unprocessed)} unprocessed event(s)\n")
    
    extractor = SpeakerExtractor()
    total_speakers = 0
    
    for event_id, url, title, body_text in unprocessed:
        print(f"📄 Event ID {event_id}: {title[:60]}...")
        
        result = extractor.extract_speakers(title, body_text)
        
        if result['success']:
            speakers = result['speakers']
            print(f"   ✓ Found {len(speakers)} speaker(s)")
            
            for speaker_data in speakers:
                speaker_id = db.add_speaker(
                    name=speaker_data.get('name'),
                    title=speaker_data.get('title'),
                    affiliation=speaker_data.get('affiliation'),
                    primary_affiliation=speaker_data.get('primary_affiliation'),
                    bio=speaker_data.get('bio')
                )
                
                db.link_speaker_to_event(
                    event_id=event_id,
                    speaker_id=speaker_id,
                    role_in_event=speaker_data.get('role_in_event'),
                    extracted_info=json.dumps(speaker_data)
                )
                
                print(f"     - {speaker_data.get('name')}")
                total_speakers += 1
            
            db.mark_event_processed(event_id, 'completed')
        else:
            print(f"   ❌ Error: {result['error']}")
            db.mark_event_processed(event_id, 'failed')
    
    # Clean up any duplicates that slipped through fuzzy matching
    merged = db.merge_duplicates(verbose=True)

    print("\n" + "="*70)
    print(f"✓ Complete: {total_speakers} speaker records created")
    if merged:
        print(f"✓ Merged {merged} duplicate speaker(s)")