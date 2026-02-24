"""
Unified speaker enrichment module - combines tagging + enrichment in ONE pass
Uses web search + Claude AI to extract: tags, demographics, locations, languages
Saves ~50% cost and time vs running tagging and enrichment separately
"""

import anthropic
import json
import os
import time
import logging
from typing import Dict, List, Optional
from ddgs import DDGS
from dotenv import load_dotenv
from logging_config import enrichment_logger, log_with_context

# Load environment variables
load_dotenv()


class UnifiedSpeakerEnricher:
    def __init__(self, api_key=None):
        """Initialize with Anthropic API key"""
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found. Please set it in .env file or pass it directly.")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        # Using Claude 3 Haiku for 91% cost reduction with equivalent quality
        # Validation: 20-speaker A/B test showed 100% success rate, 0.857 confidence (vs 0.882 Sonnet 4)
        # Cost: $0.0008 vs $0.0096 per speaker. See ENRICHMENT_COST_OPTIMIZATION.md for details.
        self.model = "claude-3-haiku-20240307"
        self.search_delay = 1.5  # Rate limit for DuckDuckGo searches

    def web_search(self, query: str, max_results: int = 5, timeout: int = 30) -> Dict:
        """
        Perform a web search using DuckDuckGo

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            timeout: Timeout in seconds (default: 30)

        Returns a dictionary with search results
        """
        try:
            with DDGS(timeout=timeout) as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            return {
                'success': True,
                'results': results,
                'query': query
            }
        except TimeoutError as e:
            return {
                'success': False,
                'error': f'Search timeout after {timeout}s: {str(e)}',
                'results': [],
                'query': query,
                'is_transient': True
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'results': [],
                'query': query,
                'is_transient': False
            }

    def build_search_query(self, speaker: Dict) -> str:
        """Build comprehensive search query for speaker"""
        name = speaker.get('name', '')
        affiliation = speaker.get('primary_affiliation') or speaker.get('affiliation', '')

        query_parts = [f'"{name}"']
        if affiliation:
            query_parts.append(affiliation)
        # Combined keywords for both tagging and enrichment
        query_parts.append('biography expertise profile demographics nationality languages')

        return ' '.join(query_parts)

    def extract_all_data(self, speaker: Dict, events: List[Dict], search_results: List[Dict]) -> Dict:
        """
        Use Claude to extract ALL data in one pass: tags, demographics, locations, languages

        Returns a dictionary with all extracted data and confidence scores
        """
        # Build context from search results
        search_context = ""
        if search_results:
            search_context = "\n\nWeb Search Results:\n"
            for i, result in enumerate(search_results[:5], 1):
                title = result.get('title', 'No title')
                body = result.get('body', 'No description')
                search_context += f"{i}. {title}\n   {body}\n\n"

        # Build events context
        events_context = ""
        if events:
            events_context = "\n\nEvents participated in:\n"
            for event in events[:10]:  # Limit to 10 events
                event_title = event[1] if len(event) > 1 else 'Unknown'
                role = event[4] if len(event) > 4 else 'participant'
                events_context += f"- {event_title} (Role: {role})\n"

        prompt = f"""You are analyzing information about a speaker to extract comprehensive profile data.

Speaker Information:
- Name: {speaker.get('name', 'Unknown')}
- Title: {speaker.get('title', 'Not specified')}
- Affiliation: {speaker.get('affiliation', 'Not specified')}
- Bio: {speaker.get('bio', 'Not available')}
{events_context}
{search_context}

Extract ALL of the following data from the available information:

1. EXPERTISE TAGS (exactly 3 tags):
   - Represent broad topical areas (e.g., "geopolitics", "china relations", "tech policy", "climate finance")
   - Should be lowercase, 1-3 words each
   - Focus on professional expertise, not job titles
   - If limited information, infer from title/affiliation/events
   - Include confidence score (0.0-1.0) for each tag

2. DEMOGRAPHICS:
   - Gender: male, female, non-binary, or unknown
   - Nationality: ISO 3166-1 alpha-2 country codes (e.g., "US", "CN", "GB"). Can be multiple, comma-separated.
   - Birth year (if available)
   - Include confidence scores

3. LOCATIONS:
   - Current city, country (ISO code), region
   - Region values: "North America", "South America", "Europe", "Africa", "Asia", "Oceania", "Middle East"
   - Location type: "residence" (where they live) or "workplace" (where they work)
   - Mark primary location
   - Include confidence scores

4. LANGUAGES:
   - Languages spoken with proficiency levels
   - Proficiency values: "native", "fluent", "conversational"
   - Infer from nationality if evident (e.g., US nationality → English native)
   - Include confidence scores

Guidelines:
- Only include data where confidence >= 0.5
- Be conservative with confidence scores
- If no information found for a category, return empty array/object
- For nationality, use 2-letter ISO codes

Return your response as a JSON object:
{{
    "tags": [
        {{"text": "tag1", "confidence": 0.9}},
        {{"text": "tag2", "confidence": 0.8}},
        {{"text": "tag3", "confidence": 0.7}}
    ],
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
    "reasoning": "Brief explanation of key findings"
}}

Important: Return ONLY the JSON, no other text."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,  # Increased for comprehensive extraction
                timeout=60.0,  # 60 second timeout to prevent hanging
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
                'tags': result.get('tags', []),
                'demographics': result.get('demographics', {}),
                'locations': result.get('locations', []),
                'languages': result.get('languages', []),
                'reasoning': result.get('reasoning', ''),
                'raw_response': response_text
            }

        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Failed to parse JSON response: {str(e)}',
                'tags': [],
                'demographics': {},
                'locations': [],
                'languages': [],
                'raw_response': response_text if 'response_text' in locals() else None,
                'is_transient': False  # JSON parsing errors are permanent
            }
        except anthropic.APIConnectionError as e:
            return {
                'success': False,
                'error': f'Connection error: {str(e)}',
                'tags': [],
                'demographics': {},
                'locations': [],
                'languages': [],
                'raw_response': None,
                'is_transient': True  # Network errors are transient
            }
        except anthropic.APITimeoutError as e:
            return {
                'success': False,
                'error': f'Timeout: {str(e)}',
                'tags': [],
                'demographics': {},
                'locations': [],
                'languages': [],
                'raw_response': None,
                'is_transient': True  # Timeouts are transient
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'tags': [],
                'demographics': {},
                'locations': [],
                'languages': [],
                'raw_response': None,
                'is_transient': False
            }

    def enrich_speaker(self, speaker_id: int, db) -> Dict:
        """
        Full unified enrichment workflow for a single speaker
        Extracts tags + demographics + locations + languages in ONE pass

        Returns a dictionary with the enrichment result
        """
        # Get speaker info
        speaker_row = db.get_speaker_by_id(speaker_id)
        if not speaker_row:
            return {'success': False, 'error': 'Speaker not found'}

        speaker = {
            'speaker_id': speaker_row[0],
            'name': speaker_row[1],
            'title': speaker_row[2],
            'affiliation': speaker_row[3],
            'primary_affiliation': speaker_row[4],
            'bio': speaker_row[5]
        }

        # Get speaker's events
        events = db.get_speaker_events(speaker_id)

        # Perform web search
        query = self.build_search_query(speaker)
        search_result = self.web_search(query)

        # Log warning if web search failed but continuing
        if not search_result['success']:
            log_with_context(enrichment_logger, logging.WARNING,
                           f"Web search failed for {speaker['name']}, continuing with bio-only enrichment",
                           speaker_name=speaker['name'],
                           error=search_result.get('error', 'Unknown error'))

        # Determine source based on search success
        source = 'web_search' if search_result['success'] and search_result['results'] else 'bio_only'

        # Extract ALL data using Claude
        extraction_result = self.extract_all_data(
            speaker,
            events,
            search_result.get('results', [])
        )

        if not extraction_result['success']:
            # Only mark as failed if it's a permanent error
            is_transient = extraction_result.get('is_transient', False)
            if not is_transient:
                db.mark_speaker_tagged(speaker_id, 'failed')

            return {
                'success': False,
                'error': extraction_result['error'],
                'speaker_name': speaker['name'],
                'is_transient': is_transient
            }

        # Validate extracted data
        def validate_iso_country_code(code):
            """Basic ISO 3166-1 alpha-2 validation (2 uppercase letters)"""
            if not code:
                return None
            codes = [c.strip().upper() for c in str(code).split(',')]
            valid_codes = [c for c in codes if c and len(c) == 2 and c.isalpha()]
            return ','.join(valid_codes) if valid_codes else None

        def validate_gender(gender):
            """Validate gender value"""
            valid_genders = ['male', 'female', 'non-binary', 'unknown']
            return gender.lower() if gender and gender.lower() in valid_genders else None

        # Begin transaction for atomic save
        db.conn.execute('BEGIN')

        try:
            # Save TAGS to database
            tags_saved = []
            for tag_data in extraction_result['tags']:
                tag_text = tag_data.get('text', '')
                confidence = tag_data.get('confidence', 0.5)

                if tag_text and isinstance(tag_text, str):
                    db.add_speaker_tag(speaker_id, tag_text[:100], confidence, source)  # Limit tag length
                    tags_saved.append({'text': tag_text, 'confidence': confidence})

            # Save DEMOGRAPHICS
            demographics = extraction_result.get('demographics', {})
            if demographics and any([
                demographics.get('gender'),
                demographics.get('nationality'),
                demographics.get('birth_year')
            ]):
                validated_gender = validate_gender(demographics.get('gender'))
                validated_nationality = validate_iso_country_code(demographics.get('nationality'))

                db.save_speaker_demographics(
                    speaker_id,
                    gender=validated_gender,
                    gender_confidence=demographics.get('gender_confidence'),
                    nationality=validated_nationality,
                    nationality_confidence=demographics.get('nationality_confidence'),
                    birth_year=demographics.get('birth_year')
                )

            # Save LOCATIONS
            locations = extraction_result.get('locations', [])
            for loc in locations:
                validated_country = validate_iso_country_code(loc.get('country'))
                if validated_country:  # Only save if country code is valid
                    db.save_speaker_location(
                        speaker_id,
                        location_type=loc.get('location_type', 'unknown'),
                        city=loc.get('city'),
                        country=validated_country,
                        region=loc.get('region'),
                        is_primary=loc.get('is_primary', False),
                        confidence=loc.get('confidence'),
                        source=source
                    )

            # Save LANGUAGES
            languages = extraction_result.get('languages', [])
            for lang in languages:
                language_name = lang.get('language')
                if language_name and isinstance(language_name, str):
                    db.save_speaker_language(
                        speaker_id,
                        language=language_name[:50],  # Limit language name length
                        proficiency=lang.get('proficiency'),
                        confidence=lang.get('confidence'),
                        source=source
                    )

            # Commit transaction - all data saved successfully
            db.conn.commit()

            # Mark speaker as tagged AND enriched
            db.mark_speaker_tagged(speaker_id, 'completed')

        except Exception as e:
            # Rollback transaction on any database error
            db.conn.rollback()
            db.mark_speaker_tagged(speaker_id, 'failed')
            return {
                'success': False,
                'error': f'Database error: {str(e)}',
                'speaker_name': speaker['name']
            }

        return {
            'success': True,
            'speaker_name': speaker['name'],
            'tags': tags_saved,
            'demographics': demographics,
            'locations_count': len(locations),
            'languages_count': len(languages),
            'source': source,
            'reasoning': extraction_result.get('reasoning', '')
        }

    def enrich_all_speakers(
        self,
        db,
        limit: Optional[int] = None,
        skip_existing: bool = True
    ) -> Dict:
        """
        Enrich all unenriched speakers with tags + demographics + locations + languages

        Returns a dictionary with batch processing results
        """
        # Get all speakers
        all_speakers = db.get_all_speakers()

        # Filter for unenriched speakers if requested
        speakers_to_process = []
        if skip_existing:
            for speaker_data in all_speakers:
                speaker_id = speaker_data[0]
                # Check if already enriched (has demographics OR tags)
                demographics = db.get_speaker_demographics(speaker_id)
                tags = db.get_speaker_tags(speaker_id)
                if not demographics and not tags:
                    speakers_to_process.append(speaker_data)
        else:
            speakers_to_process = all_speakers

        if not speakers_to_process:
            return {
                'success': True,
                'total_processed': 0,
                'message': 'No unenriched speakers found'
            }

        if limit:
            speakers_to_process = speakers_to_process[:limit]

        results = {
            'success': True,
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'speakers': []
        }

        for speaker_data in speakers_to_process:
            speaker_id = speaker_data[0]
            speaker_name = speaker_data[1]

            print(f"\n🔄 Enriching: {speaker_name}")

            result = self.enrich_speaker(speaker_id, db)

            if result['success']:
                results['successful'] += 1
                tags_str = ', '.join([t['text'] for t in result['tags']])
                print(f"   ✓ Tags: {tags_str}")
                if result.get('demographics'):
                    gender = result['demographics'].get('gender', 'N/A')
                    nationality = result['demographics'].get('nationality', 'N/A')
                    print(f"   ✓ Demographics: {gender}, {nationality}")
                if result.get('locations_count'):
                    print(f"   ✓ Locations: {result['locations_count']}")
                if result.get('languages_count'):
                    print(f"   ✓ Languages: {result['languages_count']}")
            else:
                results['failed'] += 1
                print(f"   ✗ Error: {result['error']}")

            results['total_processed'] += 1
            results['speakers'].append(result)

            # Rate limit between searches
            time.sleep(self.search_delay)

        return results

    def get_last_usage(self) -> Optional[Dict]:
        """Get token usage from last API call"""
        return getattr(self, '_last_usage', None)


# Test function
def test_unified_enricher():
    """Test the unified enricher with a sample speaker"""
    from database import SpeakerDatabase

    enricher = UnifiedSpeakerEnricher()
    db = SpeakerDatabase()

    # Get a sample speaker
    all_speakers = db.get_all_speakers()
    if not all_speakers:
        print("No speakers found in database!")
        return

    # Find an unenriched speaker
    test_speaker_id = None
    for speaker_data in all_speakers:
        speaker_id = speaker_data[0]
        demographics = db.get_speaker_demographics(speaker_id)
        tags = db.get_speaker_tags(speaker_id)
        if not demographics and not tags:
            test_speaker_id = speaker_id
            test_speaker_name = speaker_data[1]
            break

    if not test_speaker_id:
        print("All speakers already enriched! Using first speaker for testing...")
        test_speaker_id = all_speakers[0][0]
        test_speaker_name = all_speakers[0][1]

    print("Testing Unified Speaker Enricher")
    print("=" * 70)
    print(f"\nEnriching: {test_speaker_name}")
    print("-" * 70)

    result = enricher.enrich_speaker(test_speaker_id, db)

    if result['success']:
        print("\n✓ Enrichment successful!")
        print(f"\nTags: {', '.join([t['text'] for t in result['tags']])}")

        demographics = result.get('demographics', {})
        if demographics:
            print(f"\nDemographics:")
            if demographics.get('gender'):
                print(f"  Gender: {demographics['gender']} (confidence: {demographics.get('gender_confidence', 0):.2f})")
            if demographics.get('nationality'):
                print(f"  Nationality: {demographics['nationality']} (confidence: {demographics.get('nationality_confidence', 0):.2f})")

        if result.get('locations_count'):
            print(f"\nLocations: {result['locations_count']} extracted")

        if result.get('languages_count'):
            print(f"Languages: {result['languages_count']} extracted")

        print(f"\nReasoning: {result.get('reasoning', '')}")

        usage = enricher.get_last_usage()
        if usage:
            print(f"\nTokens used: {usage['input_tokens']} in, {usage['output_tokens']} out")

    else:
        print(f"\n✗ Enrichment failed: {result.get('error', 'Unknown error')}")

    db.close()
    print("\n" + "=" * 70)


if __name__ == '__main__':
    test_unified_enricher()
