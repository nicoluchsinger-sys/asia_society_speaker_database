#!/bin/bash
# Upload database to Railway using base64 encoding
# This works around binary file upload issues

echo "Encoding database..."
base64 speakers.db > speakers.db.b64

echo "Uploading to Railway..."
railway run bash -c 'cat > speakers.db.b64 && base64 -d speakers.db.b64 > speakers.db && rm speakers.db.b64' < speakers.db.b64

echo "Cleaning up..."
rm speakers.db.b64

echo "Done! Database uploaded to Railway."
echo "Now restart your Railway service in the dashboard."
