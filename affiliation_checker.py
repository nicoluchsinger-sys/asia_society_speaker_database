"""
Check and verify speaker affiliation and title changes using web search and AI.

This module performs targeted web searches to find current affiliation and title
information for speakers, then uses AI verification to confirm changes.
"""

import os
import json
from typing import Dict, Optional
import anthropic
import logging

logger = logging.getLogger(__name__)


class AffiliationChecker:
    """Check speaker affiliations and titles via web search and AI analysis"""

    def __init__(self, model='claude-3-haiku-20240307'):
        """
        Initialize affiliation checker

        Args:
            model: Claude model to use for analysis (default: Haiku for cost efficiency)
        """
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')

        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        self.model = model

    def check_current_affiliation(
        self,
        speaker_name: str,
        current_affiliation: Optional[str],
        current_title: Optional[str]
    ) -> Dict:
        """
        Search for current affiliation and title for a speaker.

        Args:
            speaker_name: Full name of the speaker
            current_affiliation: Current affiliation in database (may be outdated)
            current_title: Current title in database (may be outdated)

        Returns:
            Dictionary with:
            {
                'affiliation_changed': bool,
                'new_affiliation': str or None,
                'affiliation_confidence': float,
                'title_changed': bool,
                'new_title': str or None,
                'title_confidence': float,
                'sources': List[str],
                'reasoning': str,
                'tokens_used': int,
                'cost': float
            }
        """
        # Perform web search using DuckDuckGo
        from speaker_enricher_v2 import UnifiedSpeakerEnricher

        search_query = f'"{speaker_name}" current position affiliation 2026'
        logger.info(f"Searching for: {search_query}")

        try:
            enricher = UnifiedSpeakerEnricher()
            search_results = enricher.web_search(search_query, max_results=5)

            if not search_results.get('success'):
                raise Exception(search_results.get('error', 'Unknown search error'))

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return {
                'affiliation_changed': False,
                'new_affiliation': None,
                'affiliation_confidence': 0.0,
                'title_changed': False,
                'new_title': None,
                'title_confidence': 0.0,
                'sources': [],
                'reasoning': f'Web search failed: {str(e)}',
                'tokens_used': 0,
                'cost': 0.0
            }

        # Extract search results
        search_context = self._format_search_results(search_results)
        sources = [r.get('href', '') for r in search_results.get('results', [])]

        # Use Claude to analyze and extract current affiliation/title
        result = self._analyze_with_claude(
            speaker_name,
            current_affiliation,
            current_title,
            search_context
        )

        result['sources'] = sources
        return result

    def _format_search_results(self, search_results: Dict) -> str:
        """Format DuckDuckGo search results for Claude analysis"""
        formatted = []

        for i, result in enumerate(search_results.get('results', []), 1):
            formatted.append(f"Source {i}: {result.get('title', 'Untitled')}")
            formatted.append(f"URL: {result.get('href', 'N/A')}")
            formatted.append(f"Content: {result.get('body', 'No content')}")
            formatted.append("")

        return "\n".join(formatted)

    def _analyze_with_claude(
        self,
        speaker_name: str,
        current_affiliation: Optional[str],
        current_title: Optional[str],
        search_context: str
    ) -> Dict:
        """Use Claude to analyze search results and determine current affiliation/title"""

        prompt = f"""You are helping maintain an accurate speaker database. Your task is to analyze web search results and determine if a speaker's affiliation or title has changed.

Speaker: {speaker_name}
Current Affiliation (in database): {current_affiliation or "Unknown"}
Current Title (in database): {current_title or "Unknown"}

Web Search Results:
{search_context}

Instructions:
1. Analyze the search results to find the speaker's CURRENT (2026) affiliation and title
2. Compare with the database values
3. Determine if changes are needed
4. Provide confidence scores (0.0-1.0) for each finding

Return your analysis as JSON:
{{
    "affiliation_changed": true/false,
    "new_affiliation": "string or null",
    "affiliation_confidence": 0.0-1.0,
    "affiliation_reasoning": "explanation",
    "title_changed": true/false,
    "new_title": "string or null",
    "title_confidence": 0.0-1.0,
    "title_reasoning": "explanation",
    "overall_reasoning": "summary of findings"
}}

Rules:
- Only suggest changes if you find clear, recent evidence (2025-2026)
- Use high confidence (>0.85) only if multiple sources confirm the same information
- If information is ambiguous or outdated, use low confidence
- If no relevant information found, set changed=false and confidence=0.0
- For affiliations, prefer full organization names over abbreviations
- For titles, use standard formats (e.g., "Professor of X" not "Prof. of X")

Return ONLY valid JSON, no other text."""

        try:
            message = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = message.content[0].text.strip()
            tokens_used = message.usage.input_tokens + message.usage.output_tokens

            # Calculate cost (Haiku: $0.25/MTok input, $1.25/MTok output)
            cost = (message.usage.input_tokens / 1_000_000 * 0.25 +
                   message.usage.output_tokens / 1_000_000 * 1.25)

            # Parse JSON response
            analysis = json.loads(response_text)

            return {
                'affiliation_changed': analysis.get('affiliation_changed', False),
                'new_affiliation': analysis.get('new_affiliation'),
                'affiliation_confidence': analysis.get('affiliation_confidence', 0.0),
                'title_changed': analysis.get('title_changed', False),
                'new_title': analysis.get('new_title'),
                'title_confidence': analysis.get('title_confidence', 0.0),
                'reasoning': analysis.get('overall_reasoning', ''),
                'affiliation_reasoning': analysis.get('affiliation_reasoning', ''),
                'title_reasoning': analysis.get('title_reasoning', ''),
                'tokens_used': tokens_used,
                'cost': cost
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.error(f"Response was: {response_text}")
            return {
                'affiliation_changed': False,
                'new_affiliation': None,
                'affiliation_confidence': 0.0,
                'title_changed': False,
                'new_title': None,
                'title_confidence': 0.0,
                'reasoning': f'Failed to parse AI response: {str(e)}',
                'tokens_used': 0,
                'cost': 0.0
            }
        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            return {
                'affiliation_changed': False,
                'new_affiliation': None,
                'affiliation_confidence': 0.0,
                'title_changed': False,
                'new_title': None,
                'title_confidence': 0.0,
                'reasoning': f'AI analysis failed: {str(e)}',
                'tokens_used': 0,
                'cost': 0.0
            }
