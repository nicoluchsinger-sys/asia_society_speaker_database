from database import SpeakerDatabase

with SpeakerDatabase() as db:
    cursor = db.conn.cursor()
    cursor.execute('SELECT event_id, url, title, body_text FROM events WHERE event_id = 7 LIMIT 1')
    event = cursor.fetchone()
    
    if event:
        event_id, url, title, body_text = event
        print(f"Event ID: {event_id}")
        print(f"URL: {url}")
        print(f"Title: {title}")
        print(f"\nBody text length: {len(body_text)} chars")
        print(f"\nFirst 1000 chars of body text:")
        print(body_text[:1000])
        print("\n" + "="*70)