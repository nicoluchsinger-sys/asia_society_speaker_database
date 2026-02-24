"""
Tests for embedding_engine.py - EmbeddingEngine.

Covers:
- build_embedding_text
- cosine_similarity
- search_by_similarity
- serialize/deserialize embedding
- Provider initialization validation
"""

import pytest
import os
import sys
import numpy as np
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def engine():
    """Create an EmbeddingEngine with mocked provider (Gemini)."""
    with patch('embedding_engine.load_dotenv'):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}):
            with patch('embedding_engine.EmbeddingEngine._init_gemini') as mock_init:
                from embedding_engine import EmbeddingEngine
                eng = EmbeddingEngine.__new__(EmbeddingEngine)
                eng.provider = 'gemini'
                eng._last_usage = None
                eng.dimension = 768
                return eng


class TestBuildEmbeddingText:
    def test_basic_speaker(self, engine):
        speaker = {
            'name': 'Jane Smith',
            'title': 'Professor',
            'affiliation': 'MIT',
            'bio': 'Expert in AI research.',
            'tags': [],
            'events': []
        }
        text = engine.build_embedding_text(speaker)
        assert 'Jane Smith' in text
        assert 'Professor' in text
        assert 'MIT' in text
        assert 'AI research' in text

    def test_speaker_with_tags(self, engine):
        speaker = {
            'name': 'John Doe',
            'title': 'Director',
            'affiliation': 'World Bank',
            'bio': 'Economics expert.',
            'tags': [('climate policy', 0.95), ('economics', 0.85)],
            'events': []
        }
        text = engine.build_embedding_text(speaker)
        assert 'climate policy' in text
        assert 'economics' in text

    def test_speaker_with_events(self, engine):
        # Events are (event_title, role, event_description) tuples
        speaker = {
            'name': 'Maria Garcia',
            'title': None,
            'affiliation': None,
            'bio': None,
            'tags': [],
            'events': [
                ('Climate Summit 2024', 'keynote speaker', 'A summit on climate change.'),
                ('Trade Forum', 'panelist', 'Forum on trade relations.')
            ]
        }
        text = engine.build_embedding_text(speaker)
        assert 'Maria Garcia' in text
        assert 'Climate Summit 2024' in text

    def test_speaker_with_no_optional_fields(self, engine):
        speaker = {
            'name': 'Anonymous Speaker',
            'title': None,
            'affiliation': None,
            'bio': None,
            'tags': [],
            'events': []
        }
        text = engine.build_embedding_text(speaker)
        assert 'Anonymous Speaker' in text


class TestCosineSimilarity:
    def test_identical_vectors(self, engine):
        vec = np.array([1.0, 2.0, 3.0])
        sim = engine.cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_orthogonal_vectors(self, engine):
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 1.0, 0.0])
        sim = engine.cosine_similarity(v1, v2)
        assert abs(sim) < 1e-6

    def test_opposite_vectors(self, engine):
        v1 = np.array([1.0, 2.0, 3.0])
        v2 = np.array([-1.0, -2.0, -3.0])
        sim = engine.cosine_similarity(v1, v2)
        assert abs(sim - (-1.0)) < 1e-6

    def test_similar_vectors(self, engine):
        v1 = np.array([1.0, 2.0, 3.0])
        v2 = np.array([1.1, 2.1, 3.1])
        sim = engine.cosine_similarity(v1, v2)
        assert sim > 0.99  # Very similar

    def test_zero_vector(self, engine):
        v1 = np.array([0.0, 0.0, 0.0])
        v2 = np.array([1.0, 2.0, 3.0])
        # Should handle gracefully (return 0 or nan, not crash)
        sim = engine.cosine_similarity(v1, v2)
        assert sim == 0.0 or np.isnan(sim)


class TestSearchBySimilarity:
    def test_returns_top_k(self, engine):
        query_emb = np.array([1.0, 0.0, 0.0])
        candidates = [
            (1, np.array([1.0, 0.0, 0.0])),   # Most similar
            (2, np.array([0.9, 0.1, 0.0])),   # Similar
            (3, np.array([0.0, 1.0, 0.0])),   # Orthogonal
            (4, np.array([0.5, 0.5, 0.0])),   # Somewhat similar
        ]

        results = engine.search_by_similarity(query_emb, candidates, top_k=2)
        assert len(results) == 2
        # First result should be the most similar (id=1)
        assert results[0][0] == 1
        assert results[0][1] > 0.99

    def test_empty_candidates(self, engine):
        query_emb = np.array([1.0, 0.0, 0.0])
        results = engine.search_by_similarity(query_emb, [], top_k=5)
        assert results == []

    def test_top_k_larger_than_candidates(self, engine):
        query_emb = np.array([1.0, 0.0])
        candidates = [
            (1, np.array([1.0, 0.0])),
            (2, np.array([0.0, 1.0])),
        ]
        results = engine.search_by_similarity(query_emb, candidates, top_k=10)
        assert len(results) == 2


class TestSerializeDeserialize:
    def test_roundtrip(self, engine):
        original = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        serialized = engine.serialize_embedding(original)
        assert isinstance(serialized, bytes)

        deserialized = engine.deserialize_embedding(serialized)
        np.testing.assert_array_almost_equal(original, deserialized)

    def test_high_dimensional(self, engine):
        original = np.random.randn(768)  # Gemini dimension
        serialized = engine.serialize_embedding(original)
        deserialized = engine.deserialize_embedding(serialized)
        np.testing.assert_array_almost_equal(original, deserialized)


class TestProviderInit:
    def test_unknown_provider_raises(self):
        with patch('embedding_engine.load_dotenv'):
            from embedding_engine import EmbeddingEngine
            with pytest.raises(ValueError, match="Unknown provider"):
                EmbeddingEngine(provider='invalid_provider')

    def test_gemini_missing_key_raises(self):
        with patch('embedding_engine.load_dotenv'):
            with patch.dict(os.environ, {}, clear=True):
                env = {k: v for k, v in os.environ.items() if k != 'GEMINI_API_KEY'}
                with patch.dict(os.environ, env, clear=True):
                    from embedding_engine import EmbeddingEngine
                    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                        EmbeddingEngine(provider='gemini')
