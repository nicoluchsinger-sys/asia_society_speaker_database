"""
Tests for speaker_extractor.py - SpeakerExtractor.

Covers:
- Initialization and API key handling
- Speaker extraction with mocked Claude API
- JSON parsing (including markdown fence removal)
- Dynamic token allocation based on event size
- Error handling (rate limits, timeouts, bad JSON, API errors)
- Batch extraction
"""

import pytest
import json
import os
from unittest.mock import patch, MagicMock, PropertyMock


# We need to mock the logging_config imports before importing speaker_extractor
# because it tries to import from logging_config at module level
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSpeakerExtractorInit:
    def test_missing_api_key_raises(self):
        """Should raise ValueError when no API key is available."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove ANTHROPIC_API_KEY if present
            env = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}
            with patch.dict(os.environ, env, clear=True):
                from speaker_extractor import SpeakerExtractor
                with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                    SpeakerExtractor(api_key=None)

    def test_explicit_api_key(self):
        """Should accept an explicit API key."""
        with patch('speaker_extractor.anthropic.Anthropic'):
            from speaker_extractor import SpeakerExtractor
            extractor = SpeakerExtractor(api_key="test-key-123")
            assert extractor.api_key == "test-key-123"


class TestSpeakerExtraction:
    @pytest.fixture
    def extractor(self):
        """Create a SpeakerExtractor with mocked Anthropic client."""
        with patch('speaker_extractor.anthropic.Anthropic') as mock_anthropic:
            from speaker_extractor import SpeakerExtractor
            ext = SpeakerExtractor(api_key="test-key")
            ext.client = mock_anthropic.return_value
            return ext

    def _make_mock_response(self, response_text):
        """Helper to create a mock Claude API response."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=response_text)]
        mock_msg.usage = MagicMock(input_tokens=100, output_tokens=50)
        return mock_msg

    def test_successful_extraction(self, extractor):
        """Should parse valid JSON response and return speakers."""
        response_json = json.dumps({
            "speakers": [
                {
                    "name": "Jane Smith",
                    "title": "Professor",
                    "affiliation": "MIT",
                    "primary_affiliation": "MIT",
                    "role_in_event": "keynote",
                    "bio": "AI researcher"
                }
            ],
            "event_summary": "An AI conference."
        })

        extractor.client.messages.create.return_value = self._make_mock_response(response_json)

        result = extractor.extract_speakers("AI Conference", "A talk about AI.")
        assert result['success'] is True
        assert len(result['speakers']) == 1
        assert result['speakers'][0]['name'] == "Jane Smith"
        assert result['event_summary'] == "An AI conference."

    def test_markdown_fence_removal(self, extractor):
        """Should strip ```json fences from response."""
        response_json = json.dumps({
            "speakers": [{"name": "Test Speaker", "title": None, "affiliation": None,
                         "primary_affiliation": None, "role_in_event": None, "bio": None}],
            "event_summary": "Test event"
        })
        fenced = f"```json\n{response_json}\n```"

        extractor.client.messages.create.return_value = self._make_mock_response(fenced)

        result = extractor.extract_speakers("Test", "Test event text")
        assert result['success'] is True
        assert len(result['speakers']) == 1

    def test_empty_speakers_list(self, extractor):
        """Should handle events with no speakers gracefully."""
        response_json = json.dumps({
            "speakers": [],
            "event_summary": "An event with no identifiable speakers."
        })

        extractor.client.messages.create.return_value = self._make_mock_response(response_json)

        result = extractor.extract_speakers("Empty Event", "No speakers mentioned.")
        assert result['success'] is True
        assert result['speakers'] == []

    def test_invalid_json_response(self, extractor):
        """Should handle invalid JSON gracefully."""
        extractor.client.messages.create.return_value = self._make_mock_response(
            "This is not valid JSON at all"
        )

        result = extractor.extract_speakers("Test", "Some text")
        assert result['success'] is False
        assert 'error' in result

    def test_dynamic_token_allocation_small(self, extractor):
        """Events < 30k chars should use 2000 max_tokens."""
        response_json = json.dumps({"speakers": [], "event_summary": "Small event"})
        extractor.client.messages.create.return_value = self._make_mock_response(response_json)

        small_text = "x" * 10000  # 10k chars
        extractor.extract_speakers("Small Event", small_text)

        call_kwargs = extractor.client.messages.create.call_args
        assert call_kwargs.kwargs.get('max_tokens', call_kwargs[1].get('max_tokens')) == 2000

    def test_dynamic_token_allocation_medium(self, extractor):
        """Events 30k-80k chars should use 4000 max_tokens."""
        response_json = json.dumps({"speakers": [], "event_summary": "Medium event"})
        extractor.client.messages.create.return_value = self._make_mock_response(response_json)

        medium_text = "x" * 50000  # 50k chars
        extractor.extract_speakers("Medium Event", medium_text)

        call_kwargs = extractor.client.messages.create.call_args
        assert call_kwargs.kwargs.get('max_tokens', call_kwargs[1].get('max_tokens')) == 4000

    def test_dynamic_token_allocation_large(self, extractor):
        """Events > 80k chars should use 8000 max_tokens."""
        response_json = json.dumps({"speakers": [], "event_summary": "Large event"})
        extractor.client.messages.create.return_value = self._make_mock_response(response_json)

        large_text = "x" * 100000  # 100k chars
        extractor.extract_speakers("Large Event", large_text)

        call_kwargs = extractor.client.messages.create.call_args
        assert call_kwargs.kwargs.get('max_tokens', call_kwargs[1].get('max_tokens')) == 8000

    def test_tracks_token_usage(self, extractor):
        """Should track input/output tokens from API response."""
        response_json = json.dumps({"speakers": [], "event_summary": "Test"})
        extractor.client.messages.create.return_value = self._make_mock_response(response_json)

        extractor.extract_speakers("Test", "Text")
        assert extractor._last_usage['input_tokens'] == 100
        assert extractor._last_usage['output_tokens'] == 50


class TestSpeakerExtractionErrors:
    @pytest.fixture
    def extractor(self):
        with patch('speaker_extractor.anthropic.Anthropic') as mock_anthropic:
            from speaker_extractor import SpeakerExtractor
            ext = SpeakerExtractor(api_key="test-key")
            ext.client = mock_anthropic.return_value
            return ext

    def test_rate_limit_error(self, extractor):
        """Should handle rate limit errors after retries."""
        import anthropic
        extractor.client.messages.create.side_effect = anthropic.RateLimitError(
            message="Rate limited",
            response=MagicMock(status_code=429, headers={}),
            body={}
        )

        with patch('speaker_extractor.time.sleep'):  # Skip actual sleep
            result = extractor.extract_speakers("Test", "Text")

        assert result['success'] is False
        assert 'Rate limit' in result['error']

    def test_connection_error(self, extractor):
        """Should handle connection errors with transient flag."""
        import anthropic
        extractor.client.messages.create.side_effect = anthropic.APIConnectionError(
            request=MagicMock()
        )

        with patch('speaker_extractor.time.sleep'):
            result = extractor.extract_speakers("Test", "Text")

        assert result['success'] is False
        assert result.get('is_transient') is True

    def test_timeout_error(self, extractor):
        """Should handle timeout errors with transient flag."""
        import anthropic
        extractor.client.messages.create.side_effect = anthropic.APITimeoutError(
            request=MagicMock()
        )

        with patch('speaker_extractor.time.sleep'):
            result = extractor.extract_speakers("Test", "Text")

        assert result['success'] is False
        assert result.get('is_transient') is True

    def test_server_error_retries(self, extractor):
        """Should retry on 5xx server errors."""
        import anthropic

        response_mock = MagicMock()
        response_mock.status_code = 500
        response_mock.headers = {}

        # Fail twice, succeed on third
        success_response = MagicMock()
        success_response.content = [MagicMock(text=json.dumps({"speakers": [], "event_summary": "OK"}))]
        success_response.usage = MagicMock(input_tokens=10, output_tokens=5)

        extractor.client.messages.create.side_effect = [
            anthropic.APIStatusError(
                message="Server error",
                response=response_mock,
                body={}
            ),
            anthropic.APIStatusError(
                message="Server error",
                response=response_mock,
                body={}
            ),
            success_response
        ]

        with patch('speaker_extractor.time.sleep'):
            result = extractor.extract_speakers("Test", "Text")

        assert result['success'] is True


class TestBatchExtraction:
    @pytest.fixture
    def extractor(self):
        with patch('speaker_extractor.anthropic.Anthropic') as mock_anthropic:
            from speaker_extractor import SpeakerExtractor
            ext = SpeakerExtractor(api_key="test-key")
            ext.client = mock_anthropic.return_value
            return ext

    def test_batch_extract(self, extractor):
        """Should process multiple events in batch."""
        response_json = json.dumps({
            "speakers": [{"name": "Speaker", "title": None, "affiliation": None,
                         "primary_affiliation": None, "role_in_event": None, "bio": None}],
            "event_summary": "An event"
        })

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=response_json)]
        mock_msg.usage = MagicMock(input_tokens=50, output_tokens=25)
        extractor.client.messages.create.return_value = mock_msg

        events = [
            (1, "https://ex.com/e1", "Event 1", "Text 1"),
            (2, "https://ex.com/e2", "Event 2", "Text 2"),
        ]

        results = extractor.batch_extract_speakers(events)
        assert len(results) == 2
        # batch_extract returns dicts with 'event_id', 'url', 'title', 'extraction'
        assert all('extraction' in r for r in results)
        assert all(r['extraction']['success'] for r in results)
