"""
Embedding engine for speaker search
Supports multiple providers: Gemini (default, free), OpenAI (fallback), Voyage (optional)
"""

import os
import numpy as np
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
import pickle

# Load environment variables
load_dotenv()


class EmbeddingEngine:
    def __init__(self, provider='gemini', api_key=None):
        """
        Initialize embedding engine with specified provider

        Args:
            provider: 'gemini' (default, free), 'openai' (fallback), or 'voyage' (optional)
            api_key: API key for the provider (or loaded from env vars)
        """
        self.provider = provider.lower()
        self._last_usage = None

        # Initialize the appropriate client
        if self.provider == 'gemini':
            self._init_gemini(api_key)
        elif self.provider == 'openai':
            self._init_openai(api_key)
        elif self.provider == 'voyage':
            self._init_voyage(api_key)
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'gemini', 'openai', or 'voyage'")

    def _init_gemini(self, api_key=None):
        """Initialize Gemini client"""
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeai not installed. Run: pip install google-generativeai")

        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found. Please set it in .env file or pass it directly.")

        genai.configure(api_key=self.api_key)
        self.client = genai
        self.model = "models/text-embedding-004"
        self.dimension = 768
        print(f"✓ Using Gemini embeddings (FREE, 1500 requests/day, 768 dimensions)")

    def _init_openai(self, api_key=None):
        """Initialize OpenAI client"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")

        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found. Please set it in .env file or pass it directly.")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "text-embedding-3-small"
        self.dimension = 1536
        print(f"✓ Using OpenAI embeddings ($0.02/1M tokens, 1536 dimensions)")

    def _init_voyage(self, api_key=None):
        """Initialize Voyage client"""
        try:
            import voyageai
        except ImportError:
            raise ImportError("voyageai not installed. Run: pip install voyageai")

        self.api_key = api_key or os.getenv('VOYAGE_API_KEY')
        if not self.api_key:
            raise ValueError("VOYAGE_API_KEY not found. Please set it in .env file or pass it directly.")

        self.client = voyageai.Client(api_key=self.api_key)
        self.model = "voyage-3"
        self.dimension = 1024
        print(f"✓ Using Voyage embeddings ($0.06/1M tokens, 1024 dimensions)")

    def build_embedding_text(self, speaker: Dict) -> str:
        """
        Build text representation of a speaker for embedding

        Combines: name + title + affiliation + bio + tags

        Args:
            speaker: Dictionary with speaker data including optional 'tags' list

        Returns:
            Text string for embedding
        """
        parts = []

        # Name (always present)
        if speaker.get('name'):
            parts.append(f"Name: {speaker['name']}")

        # Title
        if speaker.get('title'):
            parts.append(f"Title: {speaker['title']}")

        # Affiliation
        affiliation = speaker.get('affiliation') or speaker.get('primary_affiliation')
        if affiliation:
            parts.append(f"Affiliation: {affiliation}")

        # Bio
        if speaker.get('bio'):
            parts.append(f"Bio: {speaker['bio']}")

        # Tags (if provided)
        if speaker.get('tags'):
            tag_texts = [tag[0] if isinstance(tag, tuple) else tag for tag in speaker['tags']]
            parts.append(f"Expertise: {', '.join(tag_texts)}")

        return '\n'.join(parts)

    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text

        Args:
            text: Text to embed

        Returns:
            Embedding vector as numpy array
        """
        if self.provider == 'gemini':
            result = self.client.embed_content(
                model=self.model,
                content=text,
                task_type="retrieval_document"
            )
            embedding = result['embedding']
            self._last_usage = {'total_tokens': len(text.split())}  # Approximate

        elif self.provider == 'openai':
            result = self.client.embeddings.create(
                input=[text],
                model=self.model
            )
            embedding = result.data[0].embedding
            self._last_usage = {'total_tokens': result.usage.total_tokens}

        elif self.provider == 'voyage':
            result = self.client.embed([text], model=self.model, input_type='document')
            embedding = result.embeddings[0]
            self._last_usage = {'total_tokens': result.total_tokens}

        return np.array(embedding)

    def generate_embeddings_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts in a batch

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        if self.provider == 'gemini':
            # Gemini doesn't support batch embedding in the same way
            # Process one by one (still fast and free!)
            embeddings = []
            total_tokens = 0
            for text in texts:
                result = self.client.embed_content(
                    model=self.model,
                    content=text,
                    task_type="retrieval_document"
                )
                embeddings.append(result['embedding'])
                total_tokens += len(text.split())

            self._last_usage = {'total_tokens': total_tokens}

        elif self.provider == 'openai':
            result = self.client.embeddings.create(
                input=texts,
                model=self.model
            )
            embeddings = [item.embedding for item in result.data]
            self._last_usage = {'total_tokens': result.usage.total_tokens}

        elif self.provider == 'voyage':
            result = self.client.embed(texts, model=self.model, input_type='document')
            embeddings = result.embeddings
            self._last_usage = {'total_tokens': result.total_tokens}

        return [np.array(emb) for emb in embeddings]

    def generate_query_embedding(self, query: str) -> np.ndarray:
        """
        Generate embedding for a search query

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        if self.provider == 'gemini':
            result = self.client.embed_content(
                model=self.model,
                content=query,
                task_type="retrieval_query"  # Different task type for queries
            )
            embedding = result['embedding']
            self._last_usage = {'total_tokens': len(query.split())}

        elif self.provider == 'openai':
            result = self.client.embeddings.create(
                input=[query],
                model=self.model
            )
            embedding = result.data[0].embedding
            self._last_usage = {'total_tokens': result.usage.total_tokens}

        elif self.provider == 'voyage':
            result = self.client.embed([query], model=self.model, input_type='query')
            embedding = result.embeddings[0]
            self._last_usage = {'total_tokens': result.total_tokens}

        return np.array(embedding)

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Normalize vectors
        vec1_norm = vec1 / np.linalg.norm(vec1)
        vec2_norm = vec2 / np.linalg.norm(vec2)

        # Compute dot product
        similarity = np.dot(vec1_norm, vec2_norm)

        return float(similarity)

    def search_by_similarity(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: List[Tuple[int, np.ndarray]],
        top_k: int = 50
    ) -> List[Tuple[int, float]]:
        """
        Find top-k most similar candidates to query

        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of (speaker_id, embedding) tuples
            top_k: Number of top results to return

        Returns:
            List of (speaker_id, similarity_score) tuples, sorted by score descending
        """
        similarities = []

        for speaker_id, embedding in candidate_embeddings:
            score = self.cosine_similarity(query_embedding, embedding)
            similarities.append((speaker_id, score))

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top-k
        return similarities[:top_k]

    def serialize_embedding(self, embedding: np.ndarray) -> bytes:
        """
        Serialize embedding for database storage

        Args:
            embedding: Numpy array

        Returns:
            Serialized bytes
        """
        return pickle.dumps(embedding)

    def deserialize_embedding(self, data: bytes) -> np.ndarray:
        """
        Deserialize embedding from database

        Args:
            data: Serialized bytes

        Returns:
            Numpy array
        """
        return pickle.loads(data)

    def get_last_usage(self) -> Optional[Dict]:
        """Get token usage from last API call"""
        return self._last_usage


# Test function
def test_embedding_engine():
    """Test the embedding engine with all providers"""
    print("Testing Embedding Engine")
    print("=" * 60)

    # Test speaker data
    speaker = {
        'name': 'Jane Doe',
        'title': 'Professor of Economics',
        'affiliation': 'Harvard University',
        'bio': 'Expert in Chinese economic policy and US-China trade relations',
        'tags': [('china', 0.9), ('economics', 0.95), ('trade-policy', 0.85)]
    }

    # Try providers in order: Gemini (free), OpenAI (fallback), Voyage (last resort)
    providers = ['gemini', 'openai', 'voyage']

    for provider in providers:
        print(f"\n{'='*60}")
        print(f"Testing {provider.upper()}")
        print("=" * 60)

        try:
            engine = EmbeddingEngine(provider=provider)

            # Build embedding text
            text = engine.build_embedding_text(speaker)
            print("\nEmbedding text:")
            print(text[:200] + "..." if len(text) > 200 else text)
            print("-" * 60)

            # Generate embedding
            print("\nGenerating embedding...")
            embedding = engine.generate_embedding(text)
            print(f"Embedding shape: {embedding.shape}")
            print(f"Embedding dtype: {embedding.dtype}")
            print(f"First 5 values: {embedding[:5]}")

            usage = engine.get_last_usage()
            if usage:
                print(f"Tokens used: {usage['total_tokens']}")
            print("-" * 60)

            # Test query embedding
            query = "chinese economy experts"
            print(f"\nGenerating query embedding for: '{query}'")
            query_emb = engine.generate_query_embedding(query)
            print(f"Query embedding shape: {query_emb.shape}")
            print("-" * 60)

            # Test similarity
            similarity = engine.cosine_similarity(embedding, query_emb)
            print(f"\nSimilarity between speaker and query: {similarity:.4f}")
            print("-" * 60)

            # Test batch embedding
            texts = [
                "Expert in climate policy",
                "Technology entrepreneur and investor",
                "Geopolitics and international relations specialist"
            ]
            print(f"\nGenerating batch embeddings for {len(texts)} texts...")
            batch_embeddings = engine.generate_embeddings_batch(texts)
            print(f"Generated {len(batch_embeddings)} embeddings")

            usage = engine.get_last_usage()
            if usage:
                print(f"Total tokens used: {usage['total_tokens']}")
            print("-" * 60)

            # Test serialization
            print("\nTesting serialization...")
            serialized = engine.serialize_embedding(embedding)
            print(f"Serialized size: {len(serialized)} bytes")

            deserialized = engine.deserialize_embedding(serialized)
            print(f"Deserialized shape: {deserialized.shape}")
            print(f"Arrays equal: {np.array_equal(embedding, deserialized)}")
            print("-" * 60)

            print(f"\n✓ {provider.upper()} tests passed!")
            break  # Success, no need to test other providers

        except Exception as e:
            print(f"\n✗ {provider.upper()} failed: {e}")
            if provider == providers[-1]:
                print("\nAll providers failed. Please check your API keys in .env file.")


if __name__ == '__main__':
    test_embedding_engine()
