#!/usr/bin/env python3
"""
Temporary script to upload database to Railway via HTTP
Run this after deploying, then remove this file
"""

import requests
import sys

def upload_db(url, db_path='speakers.db'):
    """Upload database file to Railway"""
    print(f"Uploading {db_path} to {url}...")

    with open(db_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{url}/admin/upload-db", files=files)

    if response.status_code == 200:
        print("✓ Database uploaded successfully!")
        return True
    else:
        print(f"✗ Upload failed: {response.text}")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 temp_upload.py <your-railway-url>")
        print("Example: python3 temp_upload.py https://speaker-database-production.up.railway.app")
        sys.exit(1)

    url = sys.argv[1].rstrip('/')
    upload_db(url)
