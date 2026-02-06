"""
Speaker tagging module using web search and Claude AI
"""

import anthropic
import json
import os
import time
from typing import Dict, List, Optional
from ddgs import DDGS


class SpeakerTagger:
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
        """Build a search query for a speaker"""
        name = speaker.get('name', '')
        affiliation = speaker.get('primary_affiliation') or speaker.get('affiliation', '')

        query_parts = [f'"{name}"']
        if affiliation:
            query_parts.append(affiliation)
        query_parts.append('expertise OR profile OR biography')

        return ' '.join(query_parts)

    def generate_tags_and_enrich(self, speaker: Dict, events: List[Dict], search_results: List[Dict]) -> Dict:
        """
        Use Claude to generate tags AND enrich speaker data from web search results

        Enrichment includes:
        - Updated job title (if more current than database)
        - Enriched biography (if web search provides better info)
        - Expertise tags with confidence scores

        Returns a dictionary with tags, enriched bio, and enriched title
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

        prompt = f"""You are analyzing information about a speaker to generate expertise tags AND enrich their profile data.

Current Database Information:
- Name: {speaker.get('name', 'Unknown')}
- Title: {speaker.get('title', 'Not specified')}
- Affiliation: {speaker.get('affiliation', 'Not specified')}
- Bio: {speaker.get('bio', 'Not available')}
{events_context}
{search_context}

Your tasks:
1. Generate exactly 3 topical tags that describe this person's expertise
2. Extract an enriched/updated job title from the web search results (if available and more current)
3. Extract an enriched biography from the web search results (if available and more comprehensive)

Guidelines for Tags:
- Tags should be lowercase, 1-3 words each
- Tags should represent broad topical areas (e.g., "geopolitics", "china relations", "tech policy")
- Focus on professional expertise, not job titles
- Assign a confidence score (0.0-1.0) to each tag

Guidelines for Enrichment:
- enriched_title: Use the most current title from web search. If web search has no title or database title seems current, return null.
- enriched_bio: Synthesize a comprehensive 2-3 sentence biography from web search results. If web search provides no useful bio info, return null.
- Only enrich if web search provides meaningfully better/newer information than the database

Return your response as a JSON object:
{{
    "tags": [
        {{"text": "tag1", "confidence": 0.9}},
        {{"text": "tag2", "confidence": 0.8}},
        {{"text": "tag3", "confidence": 0.7}}
    ],
    "enriched_title": "Current job title from web search or null",
    "enriched_bio": "Comprehensive 2-3 sentence biography from web search or null",
    "reasoning": "Brief explanation of tags and enrichment decisions"
}}

Return ONLY the JSON, no other text."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,  # Increased from 500 to handle enriched bio
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
                'enriched_title': result.get('enriched_title'),
                'enriched_bio': result.get('enriched_bio'),
                'reasoning': result.get('reasoning', ''),
                'raw_response': response_text
            }

        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Failed to parse JSON response: {str(e)}',
                'tags': [],
                'raw_response': response_text if 'response_text' in locals() else None
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'API call failed: {str(e)}',
                'tags': [],
                'raw_response': None
            }

    def tag_speaker(self, speaker_id: int, db) -> Dict:
        """
        Full tagging workflow for a single speaker

        Returns a dictionary with the tagging result
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

        # Determine source based on search success
        source = 'web_search' if search_result['success'] and search_result['results'] else 'bio_only'

        # Generate tags and enrich data using Claude
        tag_result = self.generate_tags_and_enrich(
            speaker,
            events,
            search_result.get('results', [])
        )

        if not tag_result['success']:
            db.mark_speaker_tagged(speaker_id, 'failed')
            return {
                'success': False,
                'error': tag_result['error'],
                'speaker_name': speaker['name']
            }

        # Save tags to database
        tags_saved = []
        for tag_data in tag_result['tags']:
            tag_text = tag_data.get('text', '')
            confidence = tag_data.get('confidence', 0.5)

            if tag_text:
                db.add_speaker_tag(speaker_id, tag_text, confidence, source)
                tags_saved.append({'text': tag_text, 'confidence': confidence})

        # Save enriched data if available
        enriched_title = tag_result.get('enriched_title')
        enriched_bio = tag_result.get('enriched_bio')

        enrichment_applied = False
        if enriched_title or enriched_bio:
            db.enrich_speaker_data(speaker_id, enriched_title, enriched_bio)
            enrichment_applied = True

        # Mark speaker as tagged
        db.mark_speaker_tagged(speaker_id, 'completed')

        return {
            'success': True,
            'speaker_name': speaker['name'],
            'tags': tags_saved,
            'source': source,
            'enriched': enrichment_applied,
            'enriched_title': enriched_title,
            'enriched_bio': enriched_bio,
            'reasoning': tag_result.get('reasoning', '')
        }

    def tag_all_speakers(self, db, limit: Optional[int] = None) -> Dict:
        """
        Tag all untagged speakers

        Returns a dictionary with batch processing results
        """
        untagged = db.get_untagged_speakers()

        if not untagged:
            return {
                'success': True,
                'total_processed': 0,
                'message': 'No untagged speakers found'
            }

        if limit:
            untagged = untagged[:limit]

        results = {
            'success': True,
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'speakers': []
        }

        for speaker_row in untagged:
            speaker_id = speaker_row[0]
            speaker_name = speaker_row[1]

            print(f"\n🏷️  Tagging: {speaker_name}")

            result = self.tag_speaker(speaker_id, db)

            if result['success']:
                results['successful'] += 1
                tags_str = ', '.join([t['text'] for t in result['tags']])
                print(f"   ✓ Tags: {tags_str}")
            else:
                results['failed'] += 1
                print(f"   ✗ Error: {result['error']}")

            results['total_processed'] += 1
            results['speakers'].append(result)

            # Rate limit between searches
            time.sleep(self.search_delay)

        return results


def test_tagger():
    """Test the speaker tagger with a sample search"""
    tagger = SpeakerTagger()

    # Test web search
    print("Testing web search...")
    result = tagger.web_search('"Klaus Schwab" World Economic Forum expertise')
    print(f"Search success: {result['success']}")
    if result['results']:
        print(f"Found {len(result['results'])} results")
        for r in result['results'][:2]:
            print(f"  - {r.get('title', 'No title')}")

    # Test tag generation with mock data
    print("\nTesting tag generation...")
    mock_speaker = {
        'name': 'Klaus Schwab',
        'title': 'Founder and Executive Chairman',
        'affiliation': 'World Economic Forum',
        'bio': 'Founder of the World Economic Forum'
    }
    mock_events = [
        (1, 'Global Economic Outlook 2024', '2024-01-15', 'url', 'keynote speaker'),
        (2, 'Future of Technology Summit', '2023-11-20', 'url', 'panelist')
    ]

    tag_result = tagger.generate_tags(mock_speaker, mock_events, result.get('results', []))
    print(f"Tag generation success: {tag_result['success']}")
    if tag_result['success']:
        for tag in tag_result['tags']:
            print(f"  - {tag['text']} (confidence: {tag['confidence']})")


if __name__ == "__main__":
    test_tagger()
