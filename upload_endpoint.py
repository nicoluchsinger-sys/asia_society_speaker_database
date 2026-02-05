"""
Temporary upload endpoint for Railway database upload
Run this locally, then use curl to upload database
DELETE THIS FILE after upload completes!
"""

from flask import Flask, request
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from web_app.app import app

@app.route('/admin/upload-db', methods=['POST'])
def upload_database():
    """TEMPORARY: Upload database file - REMOVE AFTER USE"""
    try:
        if 'file' not in request.files:
            return {'error': 'No file provided'}, 400

        file = request.files['file']
        file.save('speakers.db')

        return {'success': True, 'message': 'Database uploaded successfully'}
    except Exception as e:
        return {'error': str(e)}, 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, port=port, host='0.0.0.0')
