"""
Test script to compare enrichment quality and cost across different models
Compares Claude Sonnet 4 vs Claude Haiku 4 vs GPT-4o-mini

Tests on sample speakers to measure:
- Extraction accuracy (tags, demographics, locations, languages)
- Confidence scores
- Token usage and cost
- Processing time

Generates detailed comparison report
"""

import os
import json
import time
from typing import Dict, List
import anthropic
from database import SpeakerDatabase
from speaker_enricher_v2 import UnifiedSpeakerEnricher
from dotenv import load_dotenv

load_dotenv()


# Model configurations with pricing
# Note: Using actual available models as of Feb 2026
MODELS = {
    'sonnet-4': {
        'model_id': 'claude-sonnet-4-20250514',
        'input_cost_per_1m': 3.00,
        'output_cost_per_1m': 15.00,
        'description': 'Current production model - highest quality, most expensive'
    },
    'sonnet-3.5': {
        'model_id': 'claude-3-5-sonnet-20241022',
        'input_cost_per_1m': 3.00,
        'output_cost_per_1m': 15.00,
        'description': 'Previous Sonnet generation - same cost as Sonnet 4'
    },
    'haiku-3.5': {
        'model_id': 'claude-3-5-haiku-20241022',
        'input_cost_per_1m': 1.00,
        'output_cost_per_1m': 5.00,
        'description': 'Latest Haiku model - 3-5x cheaper than Sonnet 4'
    },
    'haiku-3': {
        'model_id': 'claude-3-haiku-20240307',
        'input_cost_per_1m': 0.25,
        'output_cost_per_1m': 1.25,
        'description': 'Older Haiku model - 10-12x cheaper than Sonnet 4'
    }
}


class EnrichmentTester:
    """Test enrichment quality across different models"""

    def __init__(self, db_path=None):
        if db_path is None:
            if os.path.exists('/data'):
                db_path = '/data/speakers.db'
            else:
                db_path = './speakers.db'

        self.db = SpeakerDatabase(db_path)
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def get_test_speakers(self, limit=20) -> List[Dict]:
        """
        Get sample speakers for testing
        Prioritize speakers with:
        - Multiple events (more context to test with)
        - Existing bio (better quality input)
        - Mix of enriched and unenriched
        """
        cursor = self.db.conn.cursor()

        # Get speakers with events and bio, ordered by event count
        cursor.execute('''
            SELECT
                s.speaker_id,
                s.name,
                s.title,
                s.affiliation,
                s.primary_affiliation,
                s.bio,
                COUNT(es.event_id) as event_count
            FROM speakers s
            LEFT JOIN event_speakers es ON s.speaker_id = es.speaker_id
            WHERE s.bio IS NOT NULL AND LENGTH(s.bio) > 100
            GROUP BY s.speaker_id
            ORDER BY event_count DESC
            LIMIT ?
        ''', (limit,))

        speakers = []
        for row in cursor.fetchall():
            speakers.append({
                'speaker_id': row[0],
                'name': row[1],
                'title': row[2],
                'affiliation': row[3],
                'primary_affiliation': row[4],
                'bio': row[5],
                'event_count': row[6]
            })

        return speakers

    def test_model_on_speaker(self, speaker: Dict, model_name: str) -> Dict:
        """Test a specific model on one speaker"""
        model_config = MODELS[model_name]

        # Use the enricher's logic but with different model
        enricher = UnifiedSpeakerEnricher()
        enricher.model = model_config['model_id']

        # Get speaker events
        events = self.db.get_speaker_events(speaker['speaker_id'])

        # Build search query and get results
        query = enricher.build_search_query(speaker)
        search_result = enricher.web_search(query)

        # Extract data
        start_time = time.time()
        result = enricher.extract_all_data(
            speaker,
            events,
            search_result.get('results', [])
        )
        duration = time.time() - start_time

        # Get token usage
        usage = enricher.get_last_usage()

        # Calculate cost
        if usage:
            input_cost = (usage['input_tokens'] / 1_000_000) * model_config['input_cost_per_1m']
            output_cost = (usage['output_tokens'] / 1_000_000) * model_config['output_cost_per_1m']
            total_cost = input_cost + output_cost
        else:
            input_cost = output_cost = total_cost = 0

        return {
            'success': result.get('success', False),
            'tags': result.get('tags', []),
            'demographics': result.get('demographics', {}),
            'locations': result.get('locations', []),
            'languages': result.get('languages', []),
            'reasoning': result.get('reasoning', ''),
            'usage': usage,
            'cost': {
                'input': input_cost,
                'output': output_cost,
                'total': total_cost
            },
            'duration': duration,
            'error': result.get('error')
        }

    def compare_models(self, test_speakers: List[Dict], models_to_test: List[str]) -> Dict:
        """Compare all models on the same set of speakers"""
        results = {
            'speakers_tested': len(test_speakers),
            'models': models_to_test,
            'comparisons': []
        }

        for i, speaker in enumerate(test_speakers, 1):
            print(f"\n{'='*70}")
            print(f"Testing {i}/{len(test_speakers)}: {speaker['name']}")
            print(f"{'='*70}")

            comparison = {
                'speaker_id': speaker['speaker_id'],
                'speaker_name': speaker['name'],
                'event_count': speaker['event_count'],
                'results': {}
            }

            for model_name in models_to_test:
                print(f"\n  Testing {model_name}...", end=' ')

                try:
                    result = self.test_model_on_speaker(speaker, model_name)
                    comparison['results'][model_name] = result

                    if result['success']:
                        tags_count = len(result['tags'])
                        cost = result['cost']['total']
                        print(f"✓ ({tags_count} tags, ${cost:.4f})")
                    else:
                        print(f"✗ ({result.get('error', 'Unknown error')})")

                except Exception as e:
                    print(f"✗ Exception: {str(e)}")
                    comparison['results'][model_name] = {
                        'success': False,
                        'error': str(e)
                    }

                # Rate limit between API calls
                time.sleep(1.5)

            results['comparisons'].append(comparison)

        # Calculate aggregate statistics
        results['statistics'] = self._calculate_statistics(results['comparisons'], models_to_test)

        return results

    def _calculate_statistics(self, comparisons: List[Dict], models: List[str]) -> Dict:
        """Calculate aggregate statistics across all comparisons"""
        stats = {}

        for model_name in models:
            model_stats = {
                'success_rate': 0,
                'avg_tags': 0,
                'avg_confidence': 0,
                'avg_demographics': 0,
                'avg_locations': 0,
                'avg_languages': 0,
                'avg_cost': 0,
                'total_cost': 0,
                'avg_duration': 0,
                'avg_input_tokens': 0,
                'avg_output_tokens': 0
            }

            successful = 0
            for comp in comparisons:
                result = comp['results'].get(model_name, {})

                if result.get('success'):
                    successful += 1
                    model_stats['avg_tags'] += len(result.get('tags', []))

                    # Average confidence across tags
                    tags = result.get('tags', [])
                    if tags:
                        confidences = [t.get('confidence', 0) for t in tags]
                        model_stats['avg_confidence'] += sum(confidences) / len(confidences)

                    # Count data completeness
                    if result.get('demographics', {}):
                        model_stats['avg_demographics'] += 1

                    model_stats['avg_locations'] += len(result.get('locations', []))
                    model_stats['avg_languages'] += len(result.get('languages', []))

                    # Cost tracking
                    model_stats['avg_cost'] += result['cost']['total']
                    model_stats['total_cost'] += result['cost']['total']
                    model_stats['avg_duration'] += result['duration']

                    # Token tracking
                    if result.get('usage'):
                        model_stats['avg_input_tokens'] += result['usage']['input_tokens']
                        model_stats['avg_output_tokens'] += result['usage']['output_tokens']

            # Calculate averages
            total_tests = len(comparisons)
            model_stats['success_rate'] = successful / total_tests if total_tests > 0 else 0

            if successful > 0:
                model_stats['avg_tags'] /= successful
                model_stats['avg_confidence'] /= successful
                model_stats['avg_demographics'] /= successful
                model_stats['avg_locations'] /= successful
                model_stats['avg_languages'] /= successful
                model_stats['avg_cost'] /= successful
                model_stats['avg_duration'] /= successful
                model_stats['avg_input_tokens'] /= successful
                model_stats['avg_output_tokens'] /= successful

            stats[model_name] = model_stats

        return stats

    def print_report(self, results: Dict):
        """Print detailed comparison report"""
        print("\n" + "="*70)
        print("ENRICHMENT MODEL COMPARISON REPORT")
        print("="*70)

        print(f"\nSpeakers tested: {results['speakers_tested']}")
        print(f"Models compared: {', '.join(results['models'])}")

        print("\n" + "-"*70)
        print("AGGREGATE STATISTICS")
        print("-"*70)

        stats = results['statistics']

        # Print comparison table
        print(f"\n{'Metric':<30} {'Sonnet 4':<15} {'Haiku 4':<15} {'Haiku 3.5':<15}")
        print("-"*75)

        for model in results['models']:
            if model not in stats:
                continue

            s = stats[model]
            print(f"\n{model.upper()}:")
            print(f"  Success rate:           {s['success_rate']*100:.1f}%")
            print(f"  Avg tags extracted:     {s['avg_tags']:.2f}")
            print(f"  Avg tag confidence:     {s['avg_confidence']:.3f}")
            print(f"  Demographics coverage:  {s['avg_demographics']*100:.1f}%")
            print(f"  Avg locations:          {s['avg_locations']:.2f}")
            print(f"  Avg languages:          {s['avg_languages']:.2f}")
            print(f"  Avg cost per speaker:   ${s['avg_cost']:.4f}")
            print(f"  Total cost (all tests): ${s['total_cost']:.2f}")
            print(f"  Avg duration:           {s['avg_duration']:.2f}s")
            print(f"  Avg input tokens:       {s['avg_input_tokens']:.0f}")
            print(f"  Avg output tokens:      {s['avg_output_tokens']:.0f}")

        # Calculate cost savings
        if 'sonnet-4' in stats:
            sonnet_cost = stats['sonnet-4']['avg_cost']

            print(f"\n{'='*70}")
            print("COST SAVINGS ANALYSIS")
            print("="*70)
            print(f"\nCost per speaker:")
            print(f"  Sonnet 4:    ${sonnet_cost:.4f}")

            # Compare with each Haiku model
            for haiku_model in ['haiku-3.5', 'haiku-3']:
                if haiku_model in stats:
                    haiku_cost = stats[haiku_model]['avg_cost']
                    savings = ((sonnet_cost - haiku_cost) / sonnet_cost * 100) if sonnet_cost > 0 else 0

                    # Get success rate for quality assessment
                    haiku_success = stats[haiku_model]['success_rate'] * 100
                    quality_note = "✓" if haiku_success >= 85 else "⚠"

                    print(f"  {haiku_model.upper():12s} ${haiku_cost:.4f}  ({savings:.0f}% savings, {haiku_success:.0f}% success {quality_note})")

            # Extrapolate to full database
            cursor = self.db.conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM speakers')
            total_speakers = cursor.fetchone()[0]

            # Use best Haiku model for projection
            best_haiku = None
            best_haiku_cost = float('inf')
            for haiku_model in ['haiku-3.5', 'haiku-3']:
                if haiku_model in stats and stats[haiku_model]['success_rate'] >= 0.85:
                    if stats[haiku_model]['avg_cost'] < best_haiku_cost:
                        best_haiku = haiku_model
                        best_haiku_cost = stats[haiku_model]['avg_cost']

            if best_haiku:
                print(f"\nExtrapolated to {total_speakers} speakers (using best model: {best_haiku}):")
                print(f"  Sonnet 4 total:     ${sonnet_cost * total_speakers:.2f}")
                print(f"  {best_haiku.upper():12s}  ${best_haiku_cost * total_speakers:.2f}")
                print(f"  Total savings:      ${(sonnet_cost - best_haiku_cost) * total_speakers:.2f}")

        print("\n" + "="*70)

    def save_results(self, results: Dict, filename='enrichment_comparison.json'):
        """Save detailed results to JSON file"""
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✓ Detailed results saved to {filename}")

    def close(self):
        """Close database connection"""
        self.db.close()


def main():
    """Run the model comparison test"""
    import sys

    print("\n" + "="*70)
    print("ENRICHMENT MODEL COMPARISON TEST")
    print("="*70)

    # Configuration - can be overridden via command line
    num_test_speakers = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    # Test Sonnet 4 vs both Haiku models to find the best cost/quality trade-off
    models_to_test = ['sonnet-4', 'haiku-3.5', 'haiku-3']

    print(f"\nConfiguration:")
    print(f"  Test speakers: {num_test_speakers}")
    print(f"  Models to test: {', '.join(models_to_test)}")

    for model_name in models_to_test:
        config = MODELS[model_name]
        print(f"\n  {model_name}:")
        print(f"    Model: {config['model_id']}")
        print(f"    Input cost: ${config['input_cost_per_1m']}/1M tokens")
        print(f"    Output cost: ${config['output_cost_per_1m']}/1M tokens")
        print(f"    {config['description']}")

    # Initialize tester
    tester = EnrichmentTester()

    # Get test speakers
    print(f"\nSelecting {num_test_speakers} test speakers...")
    test_speakers = tester.get_test_speakers(limit=num_test_speakers)
    print(f"✓ Selected {len(test_speakers)} speakers with bios and events")

    # Run comparison
    print("\nStarting model comparison...")
    results = tester.compare_models(test_speakers, models_to_test)

    # Print report
    tester.print_report(results)

    # Save results
    tester.save_results(results)

    # Cleanup
    tester.close()

    print("\n✓ Comparison complete!")


if __name__ == '__main__':
    main()
