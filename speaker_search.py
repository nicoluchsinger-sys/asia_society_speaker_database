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

        Hybrid approach:
        1. First check for exact/partial name matches (fast, guaranteed)
        2. Then do semantic search (comprehensive)
        3. Combine with name matches prioritized

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

        # Stage 1: Candidate Retrieval (Name + Semantic)
        candidates = self._retrieve_candidates(parsed, query, top_k * 2)  # Get more for re-ranking

        # Stage 2: Ranking & Scoring
        scored_speakers = self._score_and_rank(candidates, parsed, explain)

        # Stage 3: Filtering & Return
        results = scored_speakers[:top_k]

        return results

    def _find_speakers_by_name(self, query: str) -> List[Dict]:
        """
        Find speakers by exact or partial name match

        Args:
            query: Search query (checked against speaker names)

        Returns:
            List of matching speakers with 'name_match' flag
        """
        # Clean query for name matching
        query_clean = query.strip().lower()

        # Skip if query is too short or looks like a topic search
        if len(query_clean) < 3:
            return []

        # Get all speakers and filter by name match
        all_speakers = self.db.get_all_speakers()
        matches = []

        for speaker_data in all_speakers:
            speaker_id, name, title, affiliation, bio, first_seen, last_updated = speaker_data

            if not name:
                continue

            name_lower = name.lower()

            # Check for match (exact or partial)
            if query_clean in name_lower or name_lower in query_clean:
                # Get full speaker data
                speaker_dict = self._get_speaker_data(speaker_id)
                if speaker_dict:
                    speaker_dict['name_match'] = True
                    speaker_dict['semantic_similarity'] = 1.0  # High base score for name matches
                    matches.append(speaker_dict)

        return matches

    def _retrieve_candidates(
        self,
        parsed_query: Dict,
        query: str,
        candidate_count: int
    ) -> List[Dict]:
        """
        Stage 1: Retrieve candidates using hybrid approach

        1. Name matching (exact/partial)
        2. Semantic search (topic/expertise)
        3. Combine and deduplicate

        Returns list of candidate speakers with their data
        """
        # Step 1: Try name matching first
        name_matches = self._find_speakers_by_name(query)
        name_match_ids = {s['speaker_id'] for s in name_matches}

        # Step 2: Semantic search
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
            semantic_candidates = []
            for speaker_id, similarity in similar_speakers:
                # Skip if already in name matches (avoid duplicates)
                if speaker_id in name_match_ids:
                    continue

                speaker_data = self._get_speaker_data(speaker_id)
                if speaker_data:
                    speaker_data['semantic_similarity'] = similarity
                    semantic_candidates.append(speaker_data)

            # Combine: name matches first (high priority), then semantic matches
            all_candidates = name_matches + semantic_candidates
            return all_candidates
        else:
            # No expertise requirements
            # If we have name matches, return those
            if name_matches:
                return name_matches

            # Otherwise return all speakers for filtering
            return self._get_all_speakers_data()

    def _score_and_rank(
        self,
        candidates: List[Dict],
        parsed_query: Dict,
        explain: bool
    ) -> List[Dict]:
        """
        Stage 2: Score and rank candidates

        Scoring formula with name match boost:
        final_score = ((semantic_score * 0.6) + (preference_score * 0.4)) * quality_multiplier + name_boost

        - Semantic score (60%): Topic relevance from embeddings
        - Preference score (40%): Match on gender/location/language preferences
        - Quality multiplier (1.0-1.5x): Boost for high-quality profiles
        - Name match boost (+0.5): Added when query matches speaker name
        """
        scored_candidates = []

        for candidate in candidates:
            # 1. Semantic similarity score (0.0 to 1.0) - topic relevance
            semantic_score = candidate.get('semantic_similarity', 0.5)

            # 2. Preference match score (0.0 to 1.0)
            preference_score, pref_explanations = self._calculate_preference_score(
                candidate, parsed_query
            )

            # 3. Quality multiplier (1.0 to 1.5)
            quality_multiplier = 1.0
            quality_explanations = []

            tags = candidate.get('tags', [])
            if tags:
                # High confidence tags
                high_conf_tags = [t for t in tags if t[1] > 0.8]
                if high_conf_tags:
                    quality_multiplier += 0.15
                    quality_explanations.append(f"High-confidence tags ({len(high_conf_tags)})")

                # Multiple matching tags
                if len(tags) >= 5:
                    quality_multiplier += 0.1
                    quality_explanations.append(f"Multiple expertise tags ({len(tags)})")

            # Bio completeness
            bio = candidate.get('bio', '')
            if bio and len(bio) > 200:
                quality_multiplier += 0.1
                quality_explanations.append("Detailed bio available")

            # Active speaker
            event_count = candidate.get('event_count', 0)
            if event_count > 5:
                quality_multiplier += 0.15
                quality_explanations.append(f"Active speaker ({event_count} events)")

            # 4. Name match boost (if applicable)
            name_match_boost = 0.0
            if candidate.get('name_match'):
                name_match_boost = 0.5  # Significant boost for exact name matches
                quality_explanations.append("Exact name match")

            # Calculate final score
            # Topic relevance (60%) + Preference match (40%), boosted by quality + name match
            combined_score = (semantic_score * 0.6) + (preference_score * 0.4)
            final_score = (combined_score * quality_multiplier) + name_match_boost

            # Build result
            result = {
                'speaker_id': candidate['speaker_id'],
                'name': candidate['name'],
                'title': candidate.get('title'),
                'affiliation': candidate.get('affiliation'),
                'bio': candidate.get('bio'),
                'tags': tags,
                'event_count': event_count,
                'location': candidate.get('location'),
                'score': final_score,
                'semantic_score': semantic_score,
                'preference_score': preference_score,
                'quality_multiplier': quality_multiplier
            }

            if explain:
                explanations = []
                explanations.append(f"Topic relevance: {semantic_score:.2f}")
                explanations.append(f"Preference match: {preference_score:.2f}")
                if pref_explanations:
                    explanations.extend(pref_explanations)
                if quality_explanations:
                    explanations.extend(quality_explanations)
                result['explanation'] = explanations

            scored_candidates.append(result)

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)

        return scored_candidates

    def _calculate_preference_score(
        self,
        speaker: Dict,
        parsed_query: Dict
    ) -> Tuple[float, List[str]]:
        """
        Calculate preference match score (0.0 to 1.0)

        Returns (score, explanations) tuple where:
        - score: 0.0 (no matches) to 1.0 (all preferences matched)
        - explanations: List of matched preference descriptions
        """
        preferences = parsed_query.get('soft_preferences', [])

        # If no preferences specified, return neutral score
        if not preferences:
            return 0.5, []

        total_weight = 0.0
        matched_weight = 0.0
        explanations = []

        for pref in preferences:
            pref_type = pref['type']
            pref_value = pref['value']
            pref_weight = pref.get('weight', 0.5)

            # Add to total weight (this is what we're measuring against)
            total_weight += pref_weight

            if pref_type == 'gender':
                # Check demographics
                demographics = self.db.get_speaker_demographics(speaker['speaker_id'])
                if demographics:
                    gender = demographics[0]  # First field is gender
                    if gender and gender.lower() == pref_value.lower():
                        matched_weight += pref_weight
                        explanations.append(f"✓ Gender: {pref_value}")
                    else:
                        explanations.append(f"✗ Gender: wanted {pref_value}, is {gender or 'unknown'}")
                else:
                    explanations.append(f"✗ Gender: wanted {pref_value}, no data")

            elif pref_type == 'location_region':
                # Check locations
                locations = self.db.get_speaker_locations(speaker['speaker_id'])
                matched = False
                if locations:
                    for loc in locations:
                        region = loc[4]  # Region is 5th field
                        if region and region.lower() == pref_value.lower():
                            matched_weight += pref_weight
                            explanations.append(f"✓ Region: {pref_value}")
                            matched = True
                            break

                if not matched:
                    speaker_regions = [loc[4] for loc in locations if loc[4]] if locations else []
                    actual = ', '.join(speaker_regions) if speaker_regions else 'unknown'
                    explanations.append(f"✗ Region: wanted {pref_value}, is {actual}")

            elif pref_type == 'location_country':
                # Check locations
                locations = self.db.get_speaker_locations(speaker['speaker_id'])
                matched = False
                if locations:
                    for loc in locations:
                        country = loc[3]  # Country is 4th field
                        if country and country.lower() == pref_value.lower():
                            matched_weight += pref_weight
                            explanations.append(f"✓ Country: {pref_value}")
                            matched = True
                            break

                if not matched:
                    speaker_countries = [loc[3] for loc in locations if loc[3]] if locations else []
                    actual = ', '.join(speaker_countries) if speaker_countries else 'unknown'
                    explanations.append(f"✗ Country: wanted {pref_value}, is {actual}")

            elif pref_type == 'language':
                # Check languages
                languages = self.db.get_speaker_languages(speaker['speaker_id'])
                matched = False
                if languages:
                    for lang in languages:
                        language = lang[0]  # Language is first field
                        if language and language.lower() == pref_value.lower():
                            matched_weight += pref_weight
                            explanations.append(f"✓ Language: {pref_value}")
                            matched = True
                            break

                if not matched:
                    speaker_langs = [lang[0] for lang in languages if lang[0]] if languages else []
                    actual = ', '.join(speaker_langs) if speaker_langs else 'unknown'
                    explanations.append(f"✗ Language: wanted {pref_value}, speaks {actual}")

        # Calculate normalized score (0.0 to 1.0)
        if total_weight > 0:
            preference_score = matched_weight / total_weight
        else:
            preference_score = 0.5  # Neutral if no preferences

        return preference_score, explanations

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

        # Get primary location
        locations = self.db.get_speaker_locations(speaker_id)
        primary_location = None
        if locations:
            # Find primary location or use first location
            for loc in locations:
                if loc[5]:  # is_primary field
                    primary_location = {
                        'city': loc[2],
                        'country': loc[3],
                        'region': loc[4]
                    }
                    break
            # If no primary, use first location
            if not primary_location and locations:
                loc = locations[0]
                primary_location = {
                    'city': loc[2],
                    'country': loc[3],
                    'region': loc[4]
                }

        return {
            'speaker_id': speaker_id,
            'name': name,
            'title': title,
            'affiliation': affiliation or primary_affiliation,
            'primary_affiliation': primary_affiliation,
            'bio': bio,
            'tags': tags,
            'event_count': event_count,
            'location': primary_location
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

            # Get primary location
            locations = self.db.get_speaker_locations(speaker_id)
            primary_location = None
            if locations:
                # Find primary location or use first location
                for loc in locations:
                    if loc[5]:  # is_primary field
                        primary_location = {
                            'city': loc[2],
                            'country': loc[3],
                            'region': loc[4]
                        }
                        break
                # If no primary, use first location
                if not primary_location and locations:
                    loc = locations[0]
                    primary_location = {
                        'city': loc[2],
                        'country': loc[3],
                        'region': loc[4]
                    }

            results.append({
                'speaker_id': speaker_id,
                'name': name,
                'title': title,
                'affiliation': affiliation,
                'bio': bio,
                'tags': tags,
                'event_count': event_count,
                'location': primary_location,
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
