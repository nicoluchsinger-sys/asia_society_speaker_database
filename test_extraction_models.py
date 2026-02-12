"""
Test different Claude models for speaker extraction from event HTML.

Compares Claude Sonnet 4 vs Claude 3 Haiku on actual events to see if
we can reduce extraction costs by 91% while maintaining quality.
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from speaker_extractor import SpeakerExtractor
from database import SpeakerDatabase

# Load environment variables
load_dotenv()

# Model configurations with pricing (per 1M tokens)
MODELS = {
    'sonnet-4': {
        'model_id': 'claude-sonnet-4-20250514',
        'input_cost_per_1m': 3.00,
        'output_cost_per_1m': 15.00,
    },
    'haiku-3': {
        'model_id': 'claude-3-haiku-20240307',
        'input_cost_per_1m': 0.25,
        'output_cost_per_1m': 1.25,
    }
}


def test_model_on_events(model_name, model_config, events, api_key):
    """Test a specific model on a set of events"""
    print(f"\n{'='*70}")
    print(f"Testing {model_name}: {model_config['model_id']}")
    print(f"{'='*70}")

    # Create extractor and override model
    extractor = SpeakerExtractor(api_key=api_key)
    extractor.model = model_config['model_id']

    results = []
    total_input_tokens = 0
    total_output_tokens = 0

    for idx, event in enumerate(events, 1):
        event_id, title, body_text = event
        print(f"\n[{idx}/{len(events)}] Processing: {title[:60]}...")

        try:
            result = extractor.extract_speakers(title, body_text)

            # Get tokens from extractor's last usage
            usage = getattr(extractor, '_last_usage', {})
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens

            cost = (
                (input_tokens / 1_000_000) * model_config['input_cost_per_1m'] +
                (output_tokens / 1_000_000) * model_config['output_cost_per_1m']
            )

            speakers_found = len(result.get('speakers', []))

            results.append({
                'event_id': event_id,
                'title': title,
                'success': result.get('success', False),
                'speakers_found': speakers_found,
                'speakers': result.get('speakers', []),
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost': cost
            })

            print(f"  ✓ Success: {speakers_found} speakers, ${cost:.4f}")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            results.append({
                'event_id': event_id,
                'title': title,
                'success': False,
                'error': str(e)
            })

    # Calculate summary stats
    successful = sum(1 for r in results if r.get('success'))
    total_speakers = sum(r.get('speakers_found', 0) for r in results)
    total_cost = sum(r.get('cost', 0) for r in results)
    avg_cost = total_cost / len(events) if events else 0

    print(f"\n{model_name} Results:")
    print(f"  Success rate: {successful}/{len(events)} ({successful/len(events)*100:.1f}%)")
    print(f"  Total speakers extracted: {total_speakers}")
    print(f"  Avg speakers per event: {total_speakers/len(events):.1f}")
    print(f"  Total tokens: {total_input_tokens:,} in, {total_output_tokens:,} out")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Avg cost per event: ${avg_cost:.4f}")

    return {
        'model_name': model_name,
        'model_id': model_config['model_id'],
        'results': results,
        'summary': {
            'success_rate': successful / len(events) * 100,
            'successful_count': successful,
            'total_events': len(events),
            'total_speakers': total_speakers,
            'avg_speakers_per_event': total_speakers / len(events) if events else 0,
            'total_input_tokens': total_input_tokens,
            'total_output_tokens': total_output_tokens,
            'total_cost': total_cost,
            'avg_cost_per_event': avg_cost
        }
    }


def compare_results(results_by_model):
    """Compare results across models"""
    print(f"\n{'='*70}")
    print("COMPARISON SUMMARY")
    print(f"{'='*70}")

    # Get baseline (Sonnet 4)
    baseline = results_by_model.get('sonnet-4')
    if not baseline:
        print("No baseline results to compare")
        return

    baseline_cost = baseline['summary']['avg_cost_per_event']

    for model_name, results in results_by_model.items():
        summary = results['summary']
        cost_per_event = summary['avg_cost_per_event']

        # Calculate savings
        if model_name != 'sonnet-4' and baseline_cost > 0:
            savings_pct = (baseline_cost - cost_per_event) / baseline_cost * 100
            savings_amt = baseline_cost - cost_per_event
        else:
            savings_pct = 0
            savings_amt = 0

        print(f"\n{model_name}:")
        print(f"  Success rate: {summary['success_rate']:.1f}%")
        print(f"  Speakers per event: {summary['avg_speakers_per_event']:.1f}")
        print(f"  Cost per event: ${cost_per_event:.4f}")

        if savings_pct != 0:
            print(f"  Savings: {savings_pct:.1f}% (${savings_amt:.4f} per event)")

    # Extrapolate to full pipeline
    print(f"\n{'='*70}")
    print("PROJECTED MONTHLY SAVINGS (60 events/month)")
    print(f"{'='*70}")

    monthly_events = 60  # 20 events × 3 runs per month
    for model_name, results in results_by_model.items():
        if model_name == 'sonnet-4':
            continue

        summary = results['summary']
        cost_per_event = summary['avg_cost_per_event']
        monthly_cost = cost_per_event * monthly_events
        baseline_monthly = baseline_cost * monthly_events
        monthly_savings = baseline_monthly - monthly_cost

        print(f"\n{model_name}:")
        print(f"  Monthly extraction cost: ${monthly_cost:.2f} (vs ${baseline_monthly:.2f})")
        print(f"  Monthly savings: ${monthly_savings:.2f}")
        print(f"  Annual savings: ${monthly_savings * 12:.2f}")


def main():
    """Run extraction model comparison"""
    print("Speaker Extraction Model Comparison")
    print("Testing Claude Sonnet 4 vs Claude 3 Haiku")

    # Get API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found")
        return

    # Get sample events from database
    db = SpeakerDatabase()

    # Get 5 completed events with varying complexity
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT event_id, title, body_text
        FROM events
        WHERE processing_status = 'completed'
        AND body_text IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 5
    ''')
    events = cursor.fetchall()
    db.close()

    if not events:
        print("ERROR: No events found in database")
        return

    print(f"\nTesting on {len(events)} random events:")
    for idx, (event_id, title, _) in enumerate(events, 1):
        print(f"  {idx}. {title[:60]}...")

    # Test each model
    results_by_model = {}
    for model_name, model_config in MODELS.items():
        results = test_model_on_events(model_name, model_config, events, api_key)
        results_by_model[model_name] = results

    # Compare results
    compare_results(results_by_model)

    # Save detailed results
    output_file = 'extraction_comparison.json'
    with open(output_file, 'w') as f:
        json.dump(results_by_model, f, indent=2)
    print(f"\nDetailed results saved to: {output_file}")


if __name__ == '__main__':
    main()
