from database import SpeakerDatabase

with SpeakerDatabase() as db:
    stats = db.get_statistics()
    print("Database stats:")
    print(f"  Total events: {stats['total_events']}")
    print(f"  Processed: {stats['processed_events']}")
    print(f"  Pending: {stats['total_events'] - stats['processed_events']}")
    
    # Get ALL events (not just unprocessed)
    cursor = db.conn.cursor()
    cursor.execute('SELECT event_id, title, processing_status FROM events LIMIT 5')
    events = cursor.fetchall()
    
    print("\nFirst 5 events:")
    for event_id, title, status in events:
        print(f"  ID {event_id}: {title[:50]}... - Status: {status}")
    
    # Reset failed events back to pending
    print("\nResetting failed events to pending...")
    cursor.execute("UPDATE events SET processing_status = 'pending' WHERE processing_status = 'failed'")
    db.conn.commit()
    
    print("✓ Done. Try running the extraction again.")