"""
Speaker Correction Verification Module

Uses AI to verify user-submitted corrections to speaker profiles.
Combines web search with Claude Haiku for cost-effective verification.
"""

import os
import json
from typing import Dict, List, Optional
import anthropic
from dotenv import load_dotenv

load_dotenv()


class CorrectionVerifier:
    """Verifies speaker corrections using web search + AI"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize verifier with Anthropic API credentials.

        Args:
            api_key: Anthropic API key (defaults to env var)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found. Please set it in .env file or pass it directly."
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)
        # Use Haiku for cost-effective verification (~$0.0005 per correction)
        self.model = "claude-3-haiku-20240307"

    def verify_correction(
        self,
        speaker_name: str,
        field_name: str,
        current_value: Optional[str],
        suggested_value: str,
        search_results: List[Dict],
        user_context: Optional[str] = None
    ) -> Dict:
        """
        Verify a suggested correction using AI and web search results.

        Args:
            speaker_name: Name of the speaker
            field_name: Field being corrected (affiliation, title, etc.)
            current_value: Current value of the field
            suggested_value: Proposed new value
            search_results: Web search results for verification
            user_context: Optional user explanation

        Returns:
            Dictionary with:
            - is_correct: bool
            - confidence: float (0.0-1.0)
            - reasoning: str (explanation)
            - sources: List[str] (URLs that support the correction)
        """
        # Format search results for the prompt
        search_text = self._format_search_results(search_results)

        # Build verification prompt
        prompt = f"""You are verifying a user-suggested correction to a speaker's profile.

Current Speaker Data:
- Name: {speaker_name}
- Current {field_name}: {current_value or 'Not set'}

User Suggestion:
- New {field_name}: {suggested_value}
{f'- User explanation: {user_context}' if user_context else ''}

Web Search Results:
{search_text}

Task: Determine if the suggested correction is accurate based on the search results.

Return ONLY a JSON object (no other text) with this structure:
{{
    "is_correct": true or false,
    "confidence": 0.0 to 1.0,
    "reasoning": "Brief explanation of why you accepted or rejected this",
    "sources": ["url1", "url2"]
}}

Guidelines:
- Only return confidence >= 0.85 if you find clear, recent evidence supporting the suggestion
- Check dates - is this the CURRENT {field_name} or an old one?
- If multiple sources confirm the suggestion, increase confidence
- If uncertain or sources conflict, return lower confidence (< 0.85)
- List specific URLs that support your decision
- Be conservative - it's better to flag for review than apply incorrect data
"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()

            # Claude sometimes wraps JSON in markdown code fences
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text

            response_text = response_text.strip()

            # Parse JSON response
            result = json.loads(response_text)

            return {
                'is_correct': result.get('is_correct', False),
                'confidence': result.get('confidence', 0.0),
                'reasoning': result.get('reasoning', ''),
                'sources': result.get('sources', [])
            }

        except json.JSONDecodeError as e:
            # If AI returns invalid JSON, treat as low confidence
            return {
                'is_correct': False,
                'confidence': 0.0,
                'reasoning': f'Failed to parse AI response: {str(e)}',
                'sources': []
            }

        except Exception as e:
            # Handle other errors
            return {
                'is_correct': False,
                'confidence': 0.0,
                'reasoning': f'Verification error: {str(e)}',
                'sources': []
            }

    def _format_search_results(self, results: List[Dict]) -> str:
        """Format search results for the AI prompt"""
        if not results:
            return "No search results available"

        formatted = []
        for idx, result in enumerate(results[:5], 1):  # Top 5 results
            title = result.get('title', 'Untitled')
            url = result.get('url', '')
            snippet = result.get('snippet', '')

            formatted.append(f"{idx}. {title}\n   URL: {url}\n   {snippet}")

        return '\n\n'.join(formatted)


def verify_with_web_search(
    speaker_name: str,
    field_name: str,
    current_value: Optional[str],
    suggested_value: str,
    user_context: Optional[str] = None
) -> Dict:
    """
    Complete verification workflow: web search + AI verification.

    This is a convenience function that combines web search and AI verification.

    Args:
        speaker_name: Name of the speaker
        field_name: Field being corrected
        current_value: Current value
        suggested_value: Proposed new value
        user_context: Optional user explanation

    Returns:
        Verification result dictionary
    """
    from speaker_enricher_v2 import UnifiedSpeakerEnricher

    # Perform web search
    enricher = UnifiedSpeakerEnricher()
    search_query = f"{speaker_name} {suggested_value}"
    search_results = enricher.web_search(search_query)

    # Verify with AI
    verifier = CorrectionVerifier()
    return verifier.verify_correction(
        speaker_name=speaker_name,
        field_name=field_name,
        current_value=current_value,
        suggested_value=suggested_value,
        search_results=search_results.get('results', []),
        user_context=user_context
    )
