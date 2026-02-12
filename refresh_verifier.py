"""
Helper module to detect and verify speaker data changes during refresh.

This module compares current speaker data with enriched data and uses
AI verification to confirm changes before applying them.
"""

from typing import Dict, List, Optional
from database import SpeakerDatabase
from correction_verifier import verify_with_web_search
import logging

logger = logging.getLogger(__name__)


def detect_and_verify_changes(
    speaker_id: int,
    current_data: Dict,
    enriched_data: Dict,
    database: SpeakerDatabase,
    auto_apply_threshold: float = 0.85
) -> Dict:
    """
    Detect changes between current and enriched speaker data, verify with AI,
    and apply high-confidence updates.

    Args:
        speaker_id: ID of the speaker
        current_data: Current speaker data from database (name, title, affiliation, bio)
        enriched_data: Freshly enriched data from web search
        database: Database connection
        auto_apply_threshold: Confidence threshold for auto-applying (default: 0.85)

    Returns:
        Dictionary with change detection results:
        {
            'changes_detected': bool,
            'changes_applied': int,
            'changes_pending': int,
            'details': List[Dict]  # List of change details
        }
    """
    results = {
        'changes_detected': False,
        'changes_applied': 0,
        'changes_pending': 0,
        'details': []
    }

    # Fields to check for changes
    fields_to_check = ['affiliation', 'title']

    for field_name in fields_to_check:
        current_value = current_data.get(field_name)

        # For affiliation, check web search results from enrichment
        if field_name == 'affiliation':
            # Extract affiliation from web search results if available
            new_value = _extract_affiliation_from_enrichment(enriched_data)
        elif field_name == 'title':
            # Extract title from web search results if available
            new_value = _extract_title_from_enrichment(enriched_data)
        else:
            continue

        # Skip if no new value found or same as current
        if not new_value or new_value == current_value:
            continue

        # Skip if values are very similar (fuzzy match)
        if _are_similar(current_value, new_value):
            continue

        # Change detected - verify with AI
        logger.info(f"Change detected for {current_data['name']} {field_name}: '{current_value}' -> '{new_value}'")

        verification = verify_with_web_search(
            speaker_name=current_data['name'],
            field_name=field_name,
            current_value=current_value,
            suggested_value=new_value,
            user_context=f"Detected during automated refresh on {enriched_data.get('enriched_at', 'unknown date')}"
        )

        # Determine if we should auto-apply
        verified = verification['confidence'] >= auto_apply_threshold and verification['is_correct']

        # Save correction to database
        correction_id = database.save_correction(
            speaker_id=speaker_id,
            field_name=field_name,
            current_value=current_value,
            suggested_value=new_value,
            suggestion_context="Detected during automated monthly refresh",
            submitted_by="automated_refresh",
            verified=verified,
            confidence=verification['confidence'],
            reasoning=verification['reasoning'],
            sources=verification['sources']
        )

        # Apply if high confidence
        if verified:
            database.apply_correction(speaker_id, field_name, new_value)
            results['changes_applied'] += 1
            logger.info(f"✓ Applied {field_name} change for {current_data['name']} (confidence: {verification['confidence']:.0%})")
        else:
            results['changes_pending'] += 1
            logger.info(f"⚠ Pending {field_name} change for {current_data['name']} (confidence: {verification['confidence']:.0%})")

        results['changes_detected'] = True
        results['details'].append({
            'field': field_name,
            'old_value': current_value,
            'new_value': new_value,
            'confidence': verification['confidence'],
            'applied': verified,
            'correction_id': correction_id
        })

    return results


def _extract_affiliation_from_enrichment(enriched_data: Dict) -> Optional[str]:
    """
    Extract updated affiliation from enrichment results.

    The enrichment process includes web search that may reveal current affiliation.
    We can extract this from demographics or location data.
    """
    # Check if demographics includes affiliation hint
    demographics = enriched_data.get('demographics', {})

    # Check locations for institutional affiliation
    locations = enriched_data.get('locations', [])
    for loc in locations:
        # Primary location often indicates current affiliation
        if loc.get('is_primary') and loc.get('location_type') == 'work':
            # This would need to be extracted from the web search context
            # For now, we'll return None and rely on the web search in verification
            pass

    # For now, return None - the actual affiliation will be found during verification
    # via web search. This function is a placeholder for future enhancement.
    return None


def _extract_title_from_enrichment(enriched_data: Dict) -> Optional[str]:
    """
    Extract updated title from enrichment results.

    Similar to affiliation, title might be found in web search results.
    """
    # Placeholder - actual title will be found during verification via web search
    return None


def _are_similar(str1: Optional[str], str2: Optional[str], threshold: float = 0.9) -> bool:
    """
    Check if two strings are similar using fuzzy matching.

    Args:
        str1: First string
        str2: Second string
        threshold: Similarity threshold (0-1)

    Returns:
        True if strings are similar enough to be considered the same
    """
    if not str1 or not str2:
        return False

    # Normalize
    s1 = str1.lower().strip()
    s2 = str2.lower().strip()

    if s1 == s2:
        return True

    # Simple fuzzy matching - check if one contains the other
    if s1 in s2 or s2 in s1:
        return True

    # Check for common abbreviations
    # e.g., "NYU" vs "New York University"
    common_abbrevs = {
        'nyu': 'new york university',
        'mit': 'massachusetts institute of technology',
        'ucla': 'university of california los angeles',
        'stanford': 'stanford university',
        'harvard': 'harvard university',
    }

    s1_norm = common_abbrevs.get(s1, s1)
    s2_norm = common_abbrevs.get(s2, s2)

    if s1_norm == s2_norm or s1_norm in s2_norm or s2_norm in s1_norm:
        return True

    return False
