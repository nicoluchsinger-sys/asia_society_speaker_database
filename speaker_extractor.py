"""
Speaker extraction using Anthropic's Claude API
"""

import anthropic
import json
import os
from typing import List, Dict

class SpeakerExtractor:
    def __init__(self, api_key=None):
        """Initialize with Anthropic API key"""
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found. Please set it in .env file or pass it directly.")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"
    
    def extract_speakers(self, event_title: str, event_text: str) -> Dict:
        """
        Use Claude to extract speaker information from event text
        
        Returns a dictionary with:
        - speakers: list of speaker dictionaries
        - reasoning: Claude's explanation of what it found
        """
        
        prompt = f"""You are analyzing an event description to extract information about speakers, panelists, moderators, and other participants.

Event Title: {event_title}

Event Description:
{event_text}

Please extract ALL speakers/participants mentioned in this event description. For each person, provide:
1. Full name
2. Title/role (e.g., "CEO", "Professor", "Director")
3. Affiliation/organization (e.g., company, university, institution)
4. Role in the event (e.g., "keynote speaker", "panelist", "moderator", "host")
5. Any relevant biographical information mentioned

Return your response as a JSON object with this structure:
{{
    "speakers": [
        {{
            "name": "Full Name",
            "title": "Their professional title",
            "affiliation": "Organization they represent",
            "role_in_event": "Their role in this specific event",
            "bio": "Any biographical information mentioned"
        }}
    ],
    "event_summary": "Brief 1-2 sentence summary of what this event was about"
}}

Important guidelines:
- Only include people who are SPEAKERS/PARTICIPANTS in the event, not people who are just mentioned in passing
- If title, affiliation, or bio information is not mentioned, use null for that field
- Be thorough - extract all participants, not just the main speakers
- If someone has multiple roles (e.g., "moderator and panelist"), include both in role_in_event
- Return ONLY the JSON, no other text"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract the response text
            response_text = message.content[0].text
            
            # Remove markdown code fences if present
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
            
            # Parse JSON response
            result = json.loads(response_text)
            
            return {
                'success': True,
                'speakers': result.get('speakers', []),
                'event_summary': result.get('event_summary', ''),
                'raw_response': response_text
            }
            
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Failed to parse JSON response: {str(e)}',
                'raw_response': response_text if 'response_text' in locals() else None
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'API call failed: {str(e)}',
                'raw_response': None
            }
    
    def batch_extract_speakers(self, events: List[tuple]) -> List[Dict]:
        """
        Process multiple events
        events should be list of tuples: (event_id, url, title, body_text)
        """
        results = []
        
        for event_id, url, title, body_text in events:
            print(f"\nProcessing: {title}")
            print(f"URL: {url}")
            
            extraction_result = self.extract_speakers(title, body_text)
            
            if extraction_result['success']:
                num_speakers = len(extraction_result['speakers'])
                print(f"✓ Found {num_speakers} speaker(s)")
                
                # Print speaker names
                for speaker in extraction_result['speakers']:
                    print(f"  - {speaker['name']} ({speaker.get('role_in_event', 'participant')})")
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
