import os

# Load the .env file manually
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('ANTHROPIC_API_KEY='):
                key = line.split('=', 1)[1].strip()
                os.environ['ANTHROPIC_API_KEY'] = key
                print("✓ API key loaded from .env")

from speaker_extractor import SpeakerExtractor

# Use the actual content
title = "Book Salon: Yellowface"
body_text = """Book Salon: Yellowface VIEW EVENT DETAILS By R.F. Kuang For this Book Salon , we will read the novel Yellowface by R. F. Kuang . About the novel ( publisher's description ): Authors June Hayward and Athena Liu were supposed to be twin rising stars. But Athena's a literary darling. June Hayward is literally nobody. Who wants stories about basic white girls, June thinks. So when June witnesses Athena's death in a freak accident, she acts on impulse: she steals Athena's just-finished masterpiece, an experimental novel about the unsung contributions of Chinese laborers during World War I."""

print(f"Testing extraction with:")
print(f"Title: {title}")
print(f"Body length: {len(body_text)} chars")
print("\n" + "="*70)

try:
    extractor = SpeakerExtractor()
    result = extractor.extract_speakers(title, body_text)
    
    print(f"\nSuccess: {result['success']}")
    
    if result.get('raw_response'):
        print(f"\nRaw API response:")
        print(result['raw_response'])
    
    if result.get('error'):
        print(f"\nError: {result['error']}")
    
    if result.get('speakers'):
        print(f"\nSpeakers found: {len(result['speakers'])}")
        for speaker in result['speakers']:
            print(f"  - {speaker}")
            
except Exception as e:
    print(f"\nException occurred: {e}")
    import traceback
    traceback.print_exc()