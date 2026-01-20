from speaker_extractor import SpeakerExtractor
from database import SpeakerDatabase

# Get one event from the database
with SpeakerDatabase() as db:
    unprocessed = db.get_unprocessed_events()
    if unprocessed:
        event_id, url, title, body_text = unprocessed[0]
        
        print(f"Testing extraction on:")
        print(f"Title: {title}")
        print(f"URL: {url}")
        print(f"Body text length: {len(body_text)} chars")
        print(f"First 500 chars of body text:\n{body_text[:500]}\n")
        print("-" * 70)
        
        # Try extraction
        extractor = SpeakerExtractor()
        result = extractor.extract_speakers(title, body_text)
        
        print("\nAPI Response:")
        print(f"Success: {result['success']}")
        
        if result.get('raw_response'):
            print(f"\nRaw response:\n{result['raw_response']}")
        
        if result.get('error'):
            print(f"\nError: {result['error']}")
        
        if result.get('speakers'):
            print(f"\nSpeakers found: {len(result['speakers'])}")
            for speaker in result['speakers']:
                print(f"  - {speaker}")