"""
Speaker enrichment module using web search and Claude AI
Extracts demographics, location, and language information
"""

import anthropic
import json
import os
import time
from typing import Dict, List, Optional
from ddgs import DDGS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class SpeakerEnricher:
    def __init__(self, api_key=None):
        """Initialize with Anthropic API key"""
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found. Please set it in .env file or pass it directly.")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"
        self.search_delay = 1.5  # Rate limit for DuckDuckGo searches

    def web_search(self, query: str, max_results: int = 5) -> Dict:
        """
        Perform a web search using DuckDuckGo

        Returns a dictionary with search results
        """
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            return {
                'success': True,
                'results': results,
                'query': query
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'results': [],
                'query': query
            }

    def build_search_query(self, speaker: Dict) -> str:
        """Build a search query for enrichment"""
        name = speaker.get('name', '')
        affiliation = speaker.get('primary_affiliation') or speaker.get('affiliation', '')

        query_parts = [f'"{name}"']
        if affiliation:
            query_parts.append(affiliation)
        query_parts.append('biography demographics nationality languages')

        return ' '.join(query_parts)

    def extract_enrichment_data(self, speaker: Dict, search_results: List[Dict]) -> Dict:
        """
        Use Claude to extract demographics, location, and language data

        Returns a dictionary with enrichment data and confidence scores
        """
        # Build context from search results
        search_context = ""
        if search_results:
            search_context = "\n\nWeb Search Results:\n"
            for i, result in enumerate(search_results[:5], 1):
                title = result.get('title', 'No title')
                body = result.get('body', 'No description')
                search_context += f"{i}. {title}\n   {body}\n\n"

        prompt = f"""You are analyzing information about a speaker to extract demographic and location data.

Speaker Information:
- Name: {speaker.get('name', 'Unknown')}
- Title: {speaker.get('title', 'Not specified')}
- Affiliation: {speaker.get('affiliation', 'Not specified')}
- Bio: {speaker.get('bio', 'Not available')}
{search_context}

Based on all available information, extract the following data with confidence scores:

1. **Gender**: male, female, non-binary, or unknown
2. **Nationality**: ISO 3166-1 alpha-2 country codes (e.g., "US", "CN", "GB"). Can be multiple, comma-separated.
3. **Current Location**: City, country (ISO code), and region
   - Region values: "North America", "South America", "Europe", "Africa", "Asia", "Oceania", "Middle East"
4. **Languages**: Languages spoken with proficiency levels
   - Proficiency values: "native", "fluent", "conversational"

Guidelines:
- Only include data if you find evidence in the provided information
- Assign confidence scores (0.0-1.0) based on how certain you are
- Only include fields where confidence >= 0.5
- For nationality, use 2-letter ISO codes
- For languages, infer from nationality if explicitly mentioned (e.g., US nationality → English native)
- Location type is "residence" for where they live or "workplace" for where they work

Return your response as a JSON object:
{{
    "demographics": {{
        "gender": "female",
        "gender_confidence": 0.9,
        "nationality": "US,GB",
        "nationality_confidence": 0.8,
        "birth_year": null
    }},
    "locations": [
        {{
            "location_type": "workplace",
            "city": "New York",
            "country": "US",
            "region": "North America",
            "is_primary": true,
            "confidence": 0.85
        }}
    ],
    "languages": [
        {{
            "language": "English",
            "proficiency": "native",
            "confidence": 0.95
        }},
        {{
            "language": "Mandarin",
            "proficiency": "fluent",
            "confidence": 0.7
        }}
    ],
    "reasoning": "Brief explanation of findings"
}}

Important:
- If no information is found for a category, use an empty object/array
- Only include fields where you have at least 0.5 confidence
- Be conservative with confidence scores
- Return ONLY the JSON, no other text"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Track token usage
            self._last_usage = {
                'input_tokens': message.usage.input_tokens,
                'output_tokens': message.usage.output_tokens
            }

            response_text = message.content[0].text.strip()

            # Remove markdown code fences if present
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:])
            if response_text.endswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[:-1])

            response_text = response_text.strip()
            result = json.loads(response_text)

            return {
                'success': True,
                'demographics': result.get('demographics', {}),
                'locations': result.get('locations', []),
                'languages': result.get('languages', []),
                'reasoning': result.get('reasoning', ''),
                'raw_response': response_text
            }

        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'JSON decode error: {e}',
                'raw_response': response_text if 'response_text' in locals() else ''
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def enrich_speaker(self, speaker: Dict, max_search_results: int = 5, search_delay: bool = True) -> Dict:
        """
        Perform full enrichment for a speaker: web search + Claude extraction

        Args:
            speaker: Speaker dictionary
            max_search_results: Number of search results to fetch
            search_delay: Whether to delay between searches (rate limiting)

        Returns:
            Dictionary with enrichment results
        """
        # Build search query
        query = self.build_search_query(speaker)

        # Perform web search
        if search_delay:
            time.sleep(self.search_delay)

        search_results = self.web_search(query, max_results=max_search_results)

        if not search_results['success']:
            return {
                'success': False,
                'error': f"Search failed: {search_results.get('error', 'Unknown error')}",
                'speaker_id': speaker.get('speaker_id')
            }

        # Extract enrichment data
        enrichment = self.extract_enrichment_data(speaker, search_results['results'])

        if not enrichment['success']:
            return {
                'success': False,
                'error': enrichment.get('error', 'Extraction failed'),
                'speaker_id': speaker.get('speaker_id')
            }

        # Add metadata
        enrichment['speaker_id'] = speaker.get('speaker_id')
        enrichment['query'] = query
        enrichment['search_result_count'] = len(search_results['results'])

        return enrichment

    def get_last_usage(self) -> Optional[Dict]:
        """Get token usage from last API call"""
        return getattr(self, '_last_usage', None)


# Test function
def test_enricher():
    """Test the enricher with a sample speaker"""
    enricher = SpeakerEnricher()

    test_speaker = {
        'speaker_id': 1,
        'name': 'Condoleezza Rice',
        'title': 'Former U.S. Secretary of State',
        'affiliation': 'Stanford University',
        'bio': 'Political scientist and diplomat who served as the 66th United States Secretary of State'
    }

    print("Testing Speaker Enricher")
    print("=" * 60)
    print(f"\nEnriching: {test_speaker['name']}")
    print("-" * 60)

    result = enricher.enrich_speaker(test_speaker)

    if result['success']:
        print("\n✓ Enrichment successful!")
        print(f"\nQuery used: {result['query']}")
        print(f"Search results found: {result['search_result_count']}")

        demographics = result.get('demographics', {})
        if demographics:
            print("\nDemographics:")
            if demographics.get('gender'):
                print(f"  Gender: {demographics['gender']} (confidence: {demographics.get('gender_confidence', 0):.2f})")
            if demographics.get('nationality'):
                print(f"  Nationality: {demographics['nationality']} (confidence: {demographics.get('nationality_confidence', 0):.2f})")

        locations = result.get('locations', [])
        if locations:
            print(f"\nLocations ({len(locations)}):")
            for loc in locations:
                print(f"  - {loc.get('city', '')}, {loc.get('country', '')} ({loc.get('region', '')})")
                print(f"    Type: {loc.get('location_type', '')}, Confidence: {loc.get('confidence', 0):.2f}")

        languages = result.get('languages', [])
        if languages:
            print(f"\nLanguages ({len(languages)}):")
            for lang in languages:
                print(f"  - {lang['language']} ({lang.get('proficiency', 'unknown')}), Confidence: {lang.get('confidence', 0):.2f}")

        print(f"\nReasoning: {result.get('reasoning', '')}")

        usage = enricher.get_last_usage()
        if usage:
            print(f"\nTokens used: {usage['input_tokens']} in, {usage['output_tokens']} out")

    else:
        print(f"\n✗ Enrichment failed: {result.get('error', 'Unknown error')}")

    print("\n" + "=" * 60)


if __name__ == '__main__':
    test_enricher()
