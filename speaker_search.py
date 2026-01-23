"""
Speaker search engine with natural language query support
Combines semantic embeddings with structured filters and ranking
"""

from typing import List, Dict, Optional, Tuple
from database import SpeakerDatabase
from embedding_engine import EmbeddingEngine
from query_parser import QueryParser
import numpy as np


class SpeakerSearch:
    def __init__(self, db_path='speakers.db', provider='openai'):
        """Initialize search engine

        Args:
            db_path: Path to database
            provider: Embedding provider ('gemini', 'openai', or 'voyage')
                     Should match the provider used to generate embeddings
        """
        self.db = SpeakerDatabase(db_path)
        self.engine = EmbeddingEngine(provider=provider)
        self.parser = QueryParser()

    def search(
        self,
        query: str,
        top_k: int = 50,
        explain: bool = False
    ) -> List[Dict]:
        """
        Search for speakers matching natural language query

        Args:
            query: Natural language search query
            top_k: Maximum number of results to return
            explain: Include explanation of why each speaker matched

        Returns:
            List of speaker dictionaries with scores and explanations
        """
        # Parse query into structured criteria
        parsed = self.parser.parse_query(query)

        # Apply count limit if specified in query
        if parsed.get('count'):
            top_k = min(top_k, parsed['count'])

        # Stage 1: Candidate Retrieval (Semantic Search)
        candidates = self._retrieve_candidates(parsed, top_k * 2)  # Get more for re-ranking

        # Stage 2: Ranking & Scoring
        scored_speakers = self._score_and_rank(candidates, parsed, explain)

        # Stage 3: Filtering & Return
        results = scored_speakers[:top_k]

        return results

    def _retrieve_candidates(
        self,
        parsed_query: Dict,
        candidate_count: int
    ) -> List[Dict]:
        """
        Stage 1: Retrieve candidates using semantic search

        Returns list of candidate speakers with their data
        """
        # Check if there are expertise requirements
        expertise_reqs = [
            req for req in parsed_query.get('hard_requirements', [])
            if req['type'] == 'expertise'
        ]

        if expertise_reqs:
            # Build query text from expertise requirements
            query_texts = [req['value'] for req in expertise_reqs]
            query_text = ' '.join(query_texts)

            # Generate query embedding
            query_embedding = self.engine.generate_query_embedding(query_text)

            # Get all speaker embeddings
            all_embeddings = self.db.get_all_embeddings()

            if not all_embeddings:
                # No embeddings available, return all speakers
                return self._get_all_speakers_data()

            # Deserialize embeddings
            candidate_embeddings = [
                (speaker_id, self.engine.deserialize_embedding(emb_blob))
                for speaker_id, emb_blob in all_embeddings
            ]

            # Search by similarity
            similar_speakers = self.engine.search_by_similarity(
                query_embedding,
                candidate_embeddings,
                top_k=candidate_count
            )

            # Get full speaker data for candidates
            candidates = []
            for speaker_id, similarity in similar_speakers:
                speaker_data = self._get_speaker_data(speaker_id)
                if speaker_data:
                    speaker_data['semantic_similarity'] = similarity
                    candidates.append(speaker_data)

            return candidates
        else:
            # No expertise requirements - return all speakers
            return self._get_all_speakers_data()

    def _score_and_rank(
        self,
        candidates: List[Dict],
        parsed_query: Dict,
        explain: bool
    ) -> List[Dict]:
        """
        Stage 2: Score and rank candidates

        Scoring formula:
        score = semantic_similarity * (1 + preference_bonuses)
        """
        scored_candidates = []

        for candidate in candidates:
            # Base score from semantic similarity (0.0 to 1.0)
            base_score = candidate.get('semantic_similarity', 0.5)

            # Calculate bonuses
            bonus = 0.0
            explanations = []

            # Tag quality bonuses
            tags = candidate.get('tags', [])
            if tags:
                # High confidence tags
                high_conf_tags = [t for t in tags if t[1] > 0.8]
                if high_conf_tags:
                    bonus += 0.2
                    explanations.append(f"High-confidence tags ({len(high_conf_tags)})")

                # Multiple matching tags (rough heuristic)
                if len(tags) >= 5:
                    bonus += 0.1
                    explanations.append(f"Multiple expertise tags ({len(tags)})")

            # Bio completeness
            bio = candidate.get('bio', '')
            if bio and len(bio) > 200:
                bonus += 0.1
                explanations.append("Detailed bio available")

            # Recent events (placeholder - would need event date analysis)
            event_count = candidate.get('event_count', 0)
            if event_count > 5:
                bonus += 0.1
                explanations.append(f"Active speaker ({event_count} events)")

            # Apply soft preferences from query
            pref_explanations = self._apply_preferences(candidate, parsed_query)
            for pref_bonus, pref_explanation in pref_explanations:
                bonus += pref_bonus
                explanations.append(pref_explanation)

            # Calculate final score
            final_score = base_score * (1 + bonus)

            # Build result
            result = {
                'speaker_id': candidate['speaker_id'],
                'name': candidate['name'],
                'title': candidate.get('title'),
                'affiliation': candidate.get('affiliation'),
                'bio': candidate.get('bio'),
                'tags': tags,
                'event_count': event_count,
                'score': final_score,
                'base_score': base_score,
                'bonus': bonus
            }

            if explain:
                result['explanation'] = explanations

            scored_candidates.append(result)

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)

        return scored_candidates

    def _apply_preferences(
        self,
        speaker: Dict,
        parsed_query: Dict
    ) -> List[Tuple[float, str]]:
        """
        Apply soft preferences from query to speaker

        Returns list of (bonus_value, explanation) tuples
        """
        bonuses = []

        preferences = parsed_query.get('soft_preferences', [])

        for pref in preferences:
            pref_type = pref['type']
            pref_value = pref['value']
            pref_weight = pref.get('weight', 0.5)

            if pref_type == 'gender':
                # Check demographics
                demographics = self.db.get_speaker_demographics(speaker['speaker_id'])
                if demographics:
                    gender = demographics[0]  # First field is gender
                    if gender and gender.lower() == pref_value.lower():
                        bonus_value = 0.3 * pref_weight
                        bonuses.append((bonus_value, f"Gender match ({pref_value})"))

            elif pref_type == 'location_region':
                # Check locations
                locations = self.db.get_speaker_locations(speaker['speaker_id'])
                if locations:
                    for loc in locations:
                        region = loc[4]  # Region is 5th field
                        if region and region.lower() == pref_value.lower():
                            bonus_value = 0.4 * pref_weight
                            bonuses.append((bonus_value, f"Region match ({pref_value})"))
                            break

            elif pref_type == 'location_country':
                # Check locations
                locations = self.db.get_speaker_locations(speaker['speaker_id'])
                if locations:
                    for loc in locations:
                        country = loc[3]  # Country is 4th field
                        if country and country.lower() == pref_value.lower():
                            bonus_value = 0.4 * pref_weight
                            bonuses.append((bonus_value, f"Country match ({pref_value})"))
                            break

            elif pref_type == 'language':
                # Check languages
                languages = self.db.get_speaker_languages(speaker['speaker_id'])
                if languages:
                    for lang in languages:
                        language = lang[0]  # Language is first field
                        if language and language.lower() == pref_value.lower():
                            bonus_value = 0.2 * pref_weight
                            bonuses.append((bonus_value, f"Language match ({pref_value})"))
                            break

        return bonuses

    def _get_speaker_data(self, speaker_id: int) -> Optional[Dict]:
        """Get full data for a speaker"""
        speaker = self.db.get_speaker_by_id(speaker_id)
        if not speaker:
            return None

        speaker_id, name, title, affiliation, primary_affiliation, bio = speaker

        # Get tags
        tags = self.db.get_speaker_tags(speaker_id)

        # Get event count
        events = self.db.get_speaker_events(speaker_id)
        event_count = len(events) if events else 0

        return {
            'speaker_id': speaker_id,
            'name': name,
            'title': title,
            'affiliation': affiliation or primary_affiliation,
            'primary_affiliation': primary_affiliation,
            'bio': bio,
            'tags': tags,
            'event_count': event_count
        }

    def _get_all_speakers_data(self) -> List[Dict]:
        """Get data for all speakers (when no semantic search is needed)"""
        speakers = self.db.get_all_speakers()

        results = []
        for speaker_data in speakers:
            speaker_id, name, title, affiliation, bio, first_seen, last_updated = speaker_data

            # Get tags
            tags = self.db.get_speaker_tags(speaker_id)

            # Get event count
            events = self.db.get_speaker_events(speaker_id)
            event_count = len(events) if events else 0

            results.append({
                'speaker_id': speaker_id,
                'name': name,
                'title': title,
                'affiliation': affiliation,
                'bio': bio,
                'tags': tags,
                'event_count': event_count,
                'semantic_similarity': 0.5  # Neutral score when no semantic search
            })

        return results

    def close(self):
        """Close database connection"""
        self.db.close()


# Test function
def test_search():
    """Test the search engine"""
    search = SpeakerSearch()

    test_queries = [
        "3 speakers on chinese economy",
        "climate policy experts",
        "technology policy specialists"
    ]

    print("Testing Speaker Search Engine")
    print("=" * 60)

    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 60)

        try:
            results = search.search(query, top_k=5, explain=True)

            print(f"Found {len(results)} results")

            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result['name']} (Score: {result['score']:.3f})")
                if result.get('title'):
                    print(f"   {result['title']}")
                if result.get('affiliation'):
                    print(f"   {result['affiliation']}")

                tags = result.get('tags', [])
                if tags:
                    tag_str = ', '.join([f"{t[0]} ({t[1]:.2f})" for t in tags[:3]])
                    print(f"   Tags: {tag_str}")

                if result.get('explanation'):
                    print(f"   Match reasons: {', '.join(result['explanation'])}")

        except Exception as e:
            print(f"ERROR: {e}")

        print("-" * 60)

    search.close()


if __name__ == '__main__':
    test_search()
