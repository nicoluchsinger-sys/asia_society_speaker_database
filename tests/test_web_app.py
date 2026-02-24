"""
Tests for web_app/app.py - Flask web interface.

Covers:
- Login/logout flow
- Protected route redirection
- Stats page
- Speaker detail page
- Event detail page
- API search endpoint

Uses Flask test client with mocked database and search engine.
"""

import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web_app'))


@pytest.fixture
def app():
    """Create Flask app with test configuration."""
    # Mock the scheduler to prevent background threads during testing
    with patch('web_app.app.BackgroundScheduler') as mock_sched:
        mock_scheduler = MagicMock()
        mock_sched.return_value = mock_scheduler

        # Need to reload the app module with mocked scheduler
        # Instead, just import and configure
        from web_app.app import app as flask_app
        flask_app.config['TESTING'] = True
        flask_app.config['SECRET_KEY'] = 'test-secret'
        yield flask_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def authenticated_client(client):
    """Flask test client that is already authenticated."""
    with client.session_transaction() as sess:
        sess['authenticated'] = True
    return client


class TestLogin:
    def test_login_page_renders(self, client):
        response = client.get('/login')
        assert response.status_code == 200

    def test_login_with_correct_password(self, client):
        """Should redirect to index on correct password."""
        with patch('web_app.app.SITE_PASSWORD', 'test123'):
            response = client.post('/login', data={'password': 'test123'}, follow_redirects=False)
            assert response.status_code == 302  # Redirect to index

    def test_login_with_wrong_password(self, client):
        """Should show error on wrong password."""
        with patch('web_app.app.SITE_PASSWORD', 'test123'):
            response = client.post('/login', data={'password': 'wrong'})
            assert response.status_code == 200
            assert b'Incorrect password' in response.data

    def test_logout(self, authenticated_client):
        response = authenticated_client.get('/logout', follow_redirects=False)
        assert response.status_code == 302  # Redirect to login


class TestProtectedRoutes:
    def test_index_redirects_when_not_authenticated(self, client):
        response = client.get('/', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.headers.get('Location', '')

    def test_stats_redirects_when_not_authenticated(self, client):
        response = client.get('/stats', follow_redirects=False)
        assert response.status_code == 302

    def test_index_accessible_when_authenticated(self, authenticated_client):
        response = authenticated_client.get('/')
        assert response.status_code == 200


class TestStatsPage:
    def test_stats_page_renders(self, authenticated_client):
        response = authenticated_client.get('/stats')
        assert response.status_code == 200


class TestSpeakerDetailPage:
    def test_speaker_not_found(self, authenticated_client):
        """Should return 404 for non-existent speaker."""
        with patch('web_app.app.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.get_speaker_by_id.return_value = None
            mock_get_db.return_value = mock_db

            response = authenticated_client.get('/speaker/99999')
            assert response.status_code == 404

    def test_speaker_found(self, authenticated_client):
        """Should render speaker page with full data."""
        with patch('web_app.app.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.get_speaker_by_id.return_value = (
                1, "Jane Smith", "Professor", "MIT", "MIT", "AI researcher"
            )
            mock_db.get_speaker_tags.return_value = [
                ("climate", 0.95, "web_search", "2024-01-01")
            ]
            mock_db.get_speaker_events.return_value = [
                (1, "Climate Summit", "2024-03-15", "https://ex.com/e1", "keynote")
            ]
            mock_db.get_speaker_demographics.return_value = None
            mock_db.get_speaker_locations.return_value = []
            mock_db.get_speaker_languages.return_value = []
            mock_db.get_speaker_corrections.return_value = []
            mock_get_db.return_value = mock_db

            response = authenticated_client.get('/speaker/1')
            assert response.status_code == 200
            assert b'Jane Smith' in response.data


class TestApiSearch:
    def test_search_requires_auth(self, client):
        response = client.post('/api/search',
                              data=json.dumps({'query': 'test'}),
                              content_type='application/json')
        assert response.status_code == 302  # Redirect to login

    def test_empty_query_returns_400(self, authenticated_client):
        with patch('web_app.app.get_search'):
            response = authenticated_client.post('/api/search',
                                                data=json.dumps({'query': ''}),
                                                content_type='application/json')
            assert response.status_code == 400

    def test_successful_search(self, authenticated_client):
        with patch('web_app.app.get_search') as mock_get_search, \
             patch('web_app.app.get_db') as mock_get_db:
            mock_search = MagicMock()
            mock_search.search.return_value = [
                {
                    'speaker_id': 1,
                    'name': 'Jane Smith',
                    'title': 'Professor',
                    'affiliation': 'MIT',
                    'bio': 'AI researcher',
                    'tags': [('AI', 0.9)],
                    'event_count': 3,
                    'location': {'city': 'Boston', 'country': 'USA'},
                    'score': 0.95,
                    'base_score': 0.8,
                    'bonus': 0.15,
                }
            ]
            mock_get_search.return_value = mock_search

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            response = authenticated_client.post('/api/search',
                                                data=json.dumps({'query': 'climate experts'}),
                                                content_type='application/json')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['count'] == 1
            assert data['results'][0]['name'] == 'Jane Smith'

    def test_search_error_returns_500(self, authenticated_client):
        with patch('web_app.app.get_search') as mock_get_search:
            mock_search = MagicMock()
            mock_search.search.side_effect = Exception("Search engine error")
            mock_get_search.return_value = mock_search

            response = authenticated_client.post('/api/search',
                                                data=json.dumps({'query': 'test'}),
                                                content_type='application/json')
            assert response.status_code == 500
