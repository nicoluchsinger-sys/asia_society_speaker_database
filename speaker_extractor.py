"""
Speaker extraction using Anthropic's Claude API.

This module provides intelligent speaker extraction from event descriptions using
Claude AI. It uses structured prompts to extract speaker names, titles, affiliations,
roles, and biographical information from unstructured event text.

Key features:
- Dynamic token allocation based on event size
- Robust JSON parsing with markdown fence removal
- Detailed error handling for API failures
- Token usage tracking for cost monitoring
"""

import anthropic
import json
import os
import time
from typing import List, Dict, Optional


class SpeakerExtractor:
    """
    Extracts speaker information from event descriptions using Claude AI.

    This class handles API communication with Anthropic's Claude API and manages
    the extraction of structured speaker data from unstructured event text. It
    implements intelligent token allocation to handle events of varying sizes,
    from small single-speaker talks to large multi-panel conferences.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the speaker extractor with Anthropic API credentials.

        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var

        Raises:
            ValueError: If API key is not provided and not found in environment
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found. Please set it in .env file or pass it directly."
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)
        # Using Claude 3 Haiku for 91% cost reduction with equivalent quality
        # Validation: 5-event A/B test showed 100% success rate, actually found MORE speakers
        # Cost: $0.0025 vs $0.0290 per event. See test_extraction_models.py for details.
        self.model = "claude-3-haiku-20240307"
        self._last_usage = {}
    
    def extract_speakers(self, event_title: str, event_text: str) -> Dict:
        """
        Extract structured speaker information from event text using Claude AI.

        This method sends the event text to Claude with a structured prompt requesting
        JSON-formatted speaker data. It handles response parsing, including removal of
        markdown code fences that Claude sometimes includes.

        Dynamic Token Allocation:
        The max_tokens parameter is adjusted based on event size to handle large
        multi-panel events that may have dozens of speakers:
        - Standard events (<30k chars): 2,000 tokens
        - Medium events (30k-80k chars): 4,000 tokens
        - Large events (>80k chars): 8,000 tokens

        Args:
            event_title: Event title
            event_text: Full event description text

        Returns:
            Dictionary with structure:
            {
                'success': bool,
                'speakers': [  # Only present if success=True
                    {
                        'name': str,
                        'title': str | None,
                        'affiliation': str | None,
                        'primary_affiliation': str | None,
                        'role_in_event': str | None,
                        'bio': str | None
                    },
                    ...
                ],
                'event_summary': str,  # Only present if success=True
                'raw_response': str,
                'error': str  # Only present if success=False
            }

        Note:
            Token usage is tracked in self._last_usage for cost monitoring.
        """

        prompt = f"""You are analyzing an event description to extract information about speakers, panelists, moderators, and other participants.

Event Title: {event_title}

Event Description:
{event_text}

Please extract ALL speakers/participants mentioned in this event description. For each person, provide:
1. Full name
2. Title/role (e.g., "CEO", "Professor", "Director")
3. Affiliation/organization (full list of all organizations mentioned)
4. Primary affiliation (single main organization for deduplication)
5. Role in the event (e.g., "keynote speaker", "panelist", "moderator", "host")
6. Any relevant biographical information mentioned

Return your response as a JSON object with this structure:
{{
    "speakers": [
        {{
            "name": "Full Name",
            "title": "Their professional title",
            "affiliation": "All organizations they represent (comma-separated if multiple)",
            "primary_affiliation": "Their single main/primary organization",
            "role_in_event": "Their role in this specific event",
            "bio": "Any biographical information mentioned"
        }}
    ],
    "event_summary": "Brief 1-2 sentence summary of what this event was about"
}}

Important guidelines:
- Only include people who are SPEAKERS/PARTICIPANTS in the event, not people who are just mentioned in passing
- If title, affiliation, or bio information is not mentioned, use null for that field
- primary_affiliation should be ONE organization (the most relevant/current one) for deduplication purposes
- Be thorough - extract all participants, not just the main speakers
- If someone has multiple roles (e.g., "moderator and panelist"), include both in role_in_event
- Return ONLY the JSON, no other text"""

        # Dynamically scale max_tokens based on event size
        # Reasoning: Large multi-panel events with 20-50 speakers need more tokens
        # to return complete JSON. Claude needs ~100 tokens per speaker on average.
        # We've seen events with 80k+ characters that have 50+ speakers, requiring
        # up to 8k tokens for the full response.
        event_size = len(event_text)
        if event_size > 80000:
            max_tokens = 8000  # Very large multi-panel events (50+ speakers possible)
        elif event_size > 30000:
            max_tokens = 4000  # Medium-large events (15-25 speakers typical)
        else:
            max_tokens = 2000  # Standard events (5-10 speakers typical)

        # Retry logic for API resilience at scale
        # Handles transient failures and rate limits with exponential backoff (1s, 2s, 4s)
        max_retries = 3
        message = None

        for attempt in range(max_retries):
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                break  # Success, exit retry loop

            except anthropic.RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s exponential backoff
                    print(f"⚠ Rate limit hit, waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                # Final attempt failed, return error
                return {
                    'success': False,
                    'error': f'Rate limit exceeded after {max_retries} attempts: {str(e)}',
                    'raw_response': None,
                    'retry_after': getattr(e, 'retry_after', 60)
                }

            except anthropic.APIStatusError as e:
                status_code = getattr(e, 'status_code', 'unknown')
                # Retry only on 5xx server errors (transient), not 4xx client errors (permanent)
                if isinstance(status_code, int) and status_code >= 500 and attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s exponential backoff
                    print(f"⚠ API error {status_code}, waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                # 4xx error or final attempt failed, return error
                return {
                    'success': False,
                    'error': f'API error (status {status_code}): {str(e)}',
                    'raw_response': None
                }

        # If we got here without a message, something unexpected went wrong
        if message is None:
            return {
                'success': False,
                'error': 'API call failed after retries without raising exception',
                'raw_response': None
            }

        try:
            # Track token usage for cost monitoring and debugging
            # Input tokens = prompt length, Output tokens = response length
            self._last_usage = {
                'input_tokens': message.usage.input_tokens,
                'output_tokens': message.usage.output_tokens
            }

            # Extract the response text
            response_text = message.content[0].text

            # Claude sometimes wraps JSON in markdown code fences (```json ... ```)
            # We need to strip these before parsing
            response_text = response_text.strip()
            if response_text.startswith('```'):
                # Remove first line (```json or ```)
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:])
            if response_text.endswith('```'):
                # Remove last line (```)
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[:-1])

            response_text = response_text.strip()

            # Parse JSON response into structured data
            result = json.loads(response_text)

            return {
                'success': True,
                'speakers': result.get('speakers', []),
                'event_summary': result.get('event_summary', ''),
                'raw_response': response_text
            }

        except json.JSONDecodeError as e:
            # Claude returned invalid JSON - this is rare but can happen if the
            # response was truncated due to max_tokens limit or if Claude misunderstood
            # the prompt format
            return {
                'success': False,
                'error': f'Failed to parse JSON response: {str(e)}',
                'raw_response': response_text if 'response_text' in locals() else None
            }

        except Exception as e:
            # Catch-all for unexpected errors (network issues, response processing errors, etc.)
            return {
                'success': False,
                'error': f'Unexpected error: {type(e).__name__}: {str(e)}',
                'raw_response': None
            }
    
    def batch_extract_speakers(self, events: List[tuple]) -> List[Dict]:
        """
        Process multiple events sequentially, extracting speakers from each.

        This is a convenience method that processes a list of events and returns
        all results. It prints progress information to stdout as it processes each
        event, making it suitable for interactive CLI usage.

        Args:
            events: List of tuples in format (event_id, url, title, body_text)

        Returns:
            List of dictionaries, one per event:
            [
                {
                    'event_id': int,
                    'url': str,
                    'title': str,
                    'extraction': dict  # Result from extract_speakers()
                },
                ...
            ]

        Note:
            This method does NOT handle rate limiting automatically. For large batches,
            the caller should implement rate limiting and retry logic to avoid hitting
            API limits. Consider adding time.sleep() between calls if processing many
            events.
        """
        results = []

        for event_id, url, title, body_text in events:
            print(f"\nProcessing: {title}")
            print(f"URL: {url}")

            extraction_result = self.extract_speakers(title, body_text)

            if extraction_result['success']:
                num_speakers = len(extraction_result['speakers'])
                print(f"✓ Found {num_speakers} speaker(s)")

                # Show extracted speaker names for verification
                for speaker in extraction_result['speakers']:
                    role = speaker.get('role_in_event', 'participant')
                    print(f"  - {speaker['name']} ({role})")
            else:
                print(f"✗ Error: {extraction_result['error']}")

            results.append({
                'event_id': event_id,
                'url': url,
                'title': title,
                'extraction': extraction_result
            })

        return results


def test_extraction():
    """Test the speaker extraction with a sample event"""
    extractor = SpeakerExtractor()
    
    sample_title = "Innovation in Healthcare: A Conversation with Dr. Sarah Chen"
    sample_text = """
    Join us for an engaging discussion with Dr. Sarah Chen, Chief Medical Officer at HealthTech 
    Innovations and former Director of the WHO Digital Health Initiative. Dr. Chen will share 
    her insights on the future of telemedicine and AI in healthcare.
    
    The event will be moderated by Professor James Liu, Chair of the Department of Public Health 
    at University of Geneva.
    
    Panelists include:
    - Maria Rodriguez, CEO of SwissMed Technologies
    - Dr. Thomas Weber, Head of Innovation at University Hospital Zurich
    """
    
    result = extractor.extract_speakers(sample_title, sample_text)
    
    print("Test Extraction Results:")
    print(json.dumps(result, indent=2))
    

if __name__ == "__main__":
    test_extraction()
