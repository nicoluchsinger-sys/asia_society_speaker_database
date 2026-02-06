"""
Natural language query parser for speaker search
Uses Claude API to parse queries into structured search criteria
"""

import anthropic
import json
import os
import time
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class QueryParser:
    def __init__(self, api_key=None):
        """Initialize with Anthropic API key"""
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found. Please set it in .env file or pass it directly.")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"

    def parse_query(self, query: str) -> Dict:
        """
        Parse a natural language query into structured search criteria

        Args:
            query: Natural language search query (e.g., "3 speakers on chinese economy, ideally women based in Europe")

        Returns:
            Dictionary with parsed criteria:
            {
                "count": 3,
                "hard_requirements": [
                    {"type": "expertise", "value": "chinese economy", "keywords": ["china", "economy", "economics"]}
                ],
                "soft_preferences": [
                    {"type": "gender", "value": "female", "weight": 0.7},
                    {"type": "location_region", "value": "Europe", "weight": 0.6}
                ]
            }
        """

        prompt = f"""You are parsing a natural language search query for a speaker database.
Extract structured search criteria from the user's query.

User Query: "{query}"

Parse this query and identify:
1. **Count**: How many speakers are requested (default: unlimited if not specified)
2. **Hard Requirements**: Things the user NEEDS or REQUIRES (keywords: "need", "must", "require", "on", "about", "expert in")
3. **Soft Preferences**: Things the user would PREFER or LIKE (keywords: "ideally", "prefer", "would like", "bonus if")

For each requirement/preference, identify the TYPE and VALUE:

**Types available:**
- expertise: Topic/field expertise OR geographic expertise (e.g., "climate policy", "chinese economy", "technology", "Southeast Asia expert", "Korea specialist", "Myanmar politics")
- gender: Gender preference (values: "male", "female", "non-binary")
- location_country: Specific country WHERE THE SPEAKER IS BASED (e.g., "based in United States", "living in China")
- location_region: Geographic region WHERE THE SPEAKER IS BASED - ONLY broad regions (e.g., "based in Europe", "located in Asia", "based in North America")
- location_city: Specific city WHERE THE SPEAKER IS BASED (e.g., "based in New York", "living in London")
- language: Language spoken (e.g., "Mandarin", "Spanish", "French")
- affiliation: Organization/institution (e.g., "Harvard", "UN", "Google")
- career_stage: Career level (values: "early", "mid", "senior")

**IMPORTANT DISTINCTION:**
- Geographic EXPERTISE (what someone studies): Use "expertise" type
  Examples: "Southeast Asia expert", "China scholar", "Korea specialist", "Myanmar politics"
- Geographic LOCATION (where someone is based): Use "location_*" types
  Examples: "based in Singapore", "located in Asia", "living in New York"

If the query mentions a country/region WITHOUT "based in" or "located in", treat it as EXPERTISE.

**Weight scale for soft preferences:** 0.0 (very soft) to 1.0 (strong preference)
- "ideally", "would be nice": 0.3-0.5
- "prefer", "would like": 0.6-0.7
- "strongly prefer": 0.8-0.9

**For expertise requirements:**
- Extract main keywords from the topic for search matching
- Example: "chinese economy" → keywords: ["china", "chinese", "economy", "economics", "economic"]

Return ONLY a JSON object with this structure:
{{
    "count": <number or null>,
    "hard_requirements": [
        {{
            "type": "expertise",
            "value": "full topic description",
            "keywords": ["keyword1", "keyword2", ...]
        }}
    ],
    "soft_preferences": [
        {{
            "type": "gender",
            "value": "female",
            "weight": 0.7
        }}
    ],
    "original_query": "the original query text"
}}

Guidelines:
- If no count is specified, use null
- "On/about/expert in [topic]" = hard requirement for expertise
- Location preferences without strong language = soft preference (weight 0.5-0.6)
- Gender/demographic mentions without "must" = soft preference
- Extract ALL relevant keywords for expertise topics
- Return ONLY valid JSON, no other text
"""

        # Retry logic for API overload errors
        max_retries = 3
        base_delay = 2  # seconds

        for attempt in range(max_retries):
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

                # Extract response text
                response_text = message.content[0].text.strip()

                # Remove markdown code fences if present
                if response_text.startswith('```'):
                    lines = response_text.split('\n')
                    response_text = '\n'.join(lines[1:])
                    if response_text.endswith('```'):
                        response_text = response_text[:-3]

                # Parse JSON
                parsed = json.loads(response_text)

                # Validate and normalize the structure
                result = {
                    'count': parsed.get('count'),
                    'hard_requirements': parsed.get('hard_requirements', []),
                    'soft_preferences': parsed.get('soft_preferences', []),
                    'original_query': parsed.get('original_query', query)
                }

                return result

            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse Claude's response as JSON: {e}\nResponse: {response_text}")
            except anthropic.APIError as e:
                # Check if it's an overload error (529) or rate limit error
                if hasattr(e, 'status_code') and e.status_code in [429, 529]:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff: 2s, 4s, 8s
                        print(f"API overloaded (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        raise RuntimeError(f"Error parsing query after {max_retries} retries: {e}")
                else:
                    # Other API errors, don't retry
                    raise RuntimeError(f"Error parsing query: {e}")
            except Exception as e:
                raise RuntimeError(f"Error parsing query: {e}")

    def get_last_usage(self) -> Optional[Dict]:
        """Get token usage from last API call"""
        return getattr(self, '_last_usage', None)

# Test function
def test_query_parser():
    """Test the query parser with sample queries"""
    parser = QueryParser()

    test_queries = [
        "3 speakers on chinese economy, ideally women based in Europe",
        "climate policy experts",
        "women in tech policy",
        "5 geopolitics experts from Asia",
        "mandarin-speaking economists",
        "speakers about AI ethics, prefer academics",
        "need 2 experts on US-China relations",
        "technology policy specialists based in United States",
    ]

    print("Testing Query Parser")
    print("=" * 60)

    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            result = parser.parse_query(query)
            print(f"Count: {result['count']}")
            print(f"Hard Requirements: {len(result['hard_requirements'])}")
            for req in result['hard_requirements']:
                print(f"  - {req['type']}: {req['value']}")
            print(f"Soft Preferences: {len(result['soft_preferences'])}")
            for pref in result['soft_preferences']:
                print(f"  - {pref['type']}: {pref['value']} (weight: {pref['weight']})")

            usage = parser.get_last_usage()
            if usage:
                print(f"Tokens: {usage['input_tokens']} in, {usage['output_tokens']} out")
        except Exception as e:
            print(f"ERROR: {e}")
        print("-" * 60)

if __name__ == '__main__':
    test_query_parser()
