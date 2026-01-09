"""
Category Selector for Instagram Post Generation

This module provides smart category selection based on user's text/topic input.
It analyzes the user's content and matches it to the best category from the analysis.
"""

import re
from typing import Dict, List, Tuple


def extract_keywords(text: str) -> List[str]:
    """
    Extract meaningful keywords from user text.
    Removes stop words and returns lowercase tokens.
    """
    # Common stop words to filter out
    stop_words = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
        'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
        'that', 'the', 'to', 'was', 'will', 'with', 'we', 'our',
        'you', 'your', 'this', 'these', 'those', 'about'
    }

    # Tokenize and clean
    text_lower = text.lower()
    # Remove punctuation except hyphens and apostrophes
    text_clean = re.sub(r'[^\w\s\'-]', ' ', text_lower)
    words = text_clean.split()

    # Filter stop words and short words
    keywords = [w for w in words if len(w) > 3 and w not in stop_words]

    return keywords


def calculate_keyword_score(user_keywords: List[str], category_keywords: List[str]) -> float:
    """
    Calculate match score based on keyword overlap.
    Returns a score between 0 and 1.
    """
    if not user_keywords or not category_keywords:
        return 0.0

    # Count matches
    matches = sum(1 for uk in user_keywords if any(ck in uk or uk in ck for ck in category_keywords))

    # Normalize by user keywords length
    score = matches / len(user_keywords)

    return min(score, 1.0)  # Cap at 1.0


def detect_content_indicators(text: str) -> Dict[str, bool]:
    """
    Detect content indicators in user text.
    Returns a dict of detected indicators.
    """
    text_lower = text.lower()

    return {
        "has_date": bool(re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december|\d{1,2}/\d{1,2}(/\d{2,4})?)', text_lower)),
        "has_cta": any(word in text_lower for word in ['apply', 'join', 'sign up', 'register', 'volunteer', 'hiring', 'deadline']),
        "has_narrative": any(word in text_lower for word in ['story', 'experience', 'testimonial', 'journey', 'impact']),
        "has_educational": any(word in text_lower for word in ['learn', 'how to', 'tips', 'guide', 'tutorial', 'fact']),
        "has_announcement": any(word in text_lower for word in ['announcing', 'new', 'launching', 'introducing', 'reminder']),
        "has_question": '?' in text
    }


def calculate_indicator_score(user_indicators: Dict[str, bool], category_indicators: List[str]) -> float:
    """
    Calculate score based on content indicator matches.
    Returns a score between 0 and 1.
    """
    if not category_indicators:
        return 0.0

    # Map category indicators to user indicator keys
    indicator_map = {
        "call to action": "has_cta",
        "deadline": "has_date",
        "team expansion": "has_cta",
        "past event recap": "has_narrative",
        "volunteer stories": "has_narrative",
        "impact showcase": "has_narrative",
        "event announcement": "has_announcement",
        "deadline reminder": "has_date",
        "date-specific info": "has_date"
    }

    matches = 0
    for cat_indicator in category_indicators:
        indicator_key = indicator_map.get(cat_indicator.lower())
        if indicator_key and user_indicators.get(indicator_key):
            matches += 1

    # Normalize
    score = matches / len(category_indicators) if category_indicators else 0.0

    return min(score, 1.0)


def select_category_for_generation(user_text: str, analysis_json: Dict) -> Dict:
    """
    Auto-select best category based on user's text/topic.

    Algorithm:
    1. Extract keywords from user_text
    2. Score each category by keyword matches
    3. Analyze content indicators (dates, CTAs, narrative markers)
    4. Combine: final_score = (0.6 * keyword_score) + (0.4 * indicator_score)
    5. Return category with highest score (min threshold: 0.3)

    Args:
        user_text: User's content description or text for the post
        analysis_json: Full analysis JSON with categories

    Returns:
        {
          "selected_category_id": str,
          "confidence_score": float,
          "reasoning": str,
          "category_data": dict (full category design_system and metadata)
        }
    """
    if not analysis_json or 'generation_category_selector' not in analysis_json:
        return {
            "selected_category_id": None,
            "confidence_score": 0.0,
            "reasoning": "No category selector data available in analysis",
            "category_data": None
        }

    selector_data = analysis_json['generation_category_selector']
    categories = analysis_json.get('categories', [])

    if not categories:
        return {
            "selected_category_id": None,
            "confidence_score": 0.0,
            "reasoning": "No categories available",
            "category_data": None
        }

    # Extract keywords and indicators from user text
    user_keywords = extract_keywords(user_text)
    user_indicators = detect_content_indicators(user_text)

    # Score each category
    category_scores = []

    for category_id in selector_data['available_categories']:
        if category_id not in selector_data['selection_logic']:
            continue

        logic = selector_data['selection_logic'][category_id]
        category_keywords = logic.get('keywords', [])
        category_indicators = logic.get('content_indicators', [])

        # Calculate scores
        keyword_score = calculate_keyword_score(user_keywords, category_keywords)
        indicator_score = calculate_indicator_score(user_indicators, category_indicators)

        # Combined score (weighted)
        final_score = (0.6 * keyword_score) + (0.4 * indicator_score)

        category_scores.append((category_id, final_score, keyword_score, indicator_score))

    if not category_scores:
        # Fallback to primary category
        primary_id = analysis_json.get('analysis_metadata', {}).get('primary_category')
        primary_cat = next((cat for cat in categories if cat.get('category_id') == primary_id), None)

        return {
            "selected_category_id": primary_id,
            "confidence_score": 0.0,
            "reasoning": "No scoring data available, defaulting to primary category (most recent post)",
            "category_data": primary_cat
        }

    # Sort by score descending
    category_scores.sort(key=lambda x: x[1], reverse=True)

    # Get best match
    best_id, best_score, best_kw_score, best_ind_score = category_scores[0]

    # Apply minimum threshold
    if best_score < 0.3:
        # Default to primary category if confidence is too low
        primary_id = analysis_json.get('analysis_metadata', {}).get('primary_category')
        primary_cat = next((cat for cat in categories if cat.get('category_id') == primary_id), None)

        return {
            "selected_category_id": primary_id,
            "confidence_score": best_score,
            "reasoning": f"Low confidence match (score: {best_score:.2f}). Defaulting to primary category (most recent post)",
            "category_data": primary_cat
        }

    # Find the category data
    selected_cat = next((cat for cat in categories if cat.get('category_id') == best_id), None)

    # Build reasoning
    matched_keywords = [uk for uk in user_keywords if any(ck in uk or uk in ck for ck in selector_data['selection_logic'][best_id].get('keywords', []))]
    reasoning_parts = []

    if matched_keywords:
        reasoning_parts.append(f"Detected keywords: {', '.join(matched_keywords[:5])}")

    if best_ind_score > 0:
        active_indicators = [k for k, v in user_indicators.items() if v]
        if active_indicators:
            reasoning_parts.append(f"Content indicators: {', '.join(active_indicators[:3])}")

    reasoning_parts.append(f"High match with '{selected_cat.get('category_name', 'unknown')}' category")
    reasoning = ". ".join(reasoning_parts) + "."

    return {
        "selected_category_id": best_id,
        "confidence_score": round(best_score, 2),
        "reasoning": reasoning,
        "category_data": selected_cat,
        "scores_breakdown": {
            "keyword_score": round(best_kw_score, 2),
            "indicator_score": round(best_ind_score, 2),
            "final_score": round(best_score, 2)
        }
    }


def print_category_selection(selection_result: Dict):
    """
    Pretty-print category selection results.
    Useful for testing and debugging.
    """
    print("=" * 60)
    print("CATEGORY SELECTION RESULT")
    print("=" * 60)
    print(f"Selected Category: {selection_result.get('selected_category_id', 'None')}")
    print(f"Confidence: {selection_result.get('confidence_score', 0):.0%}")
    print(f"Reasoning: {selection_result.get('reasoning', 'N/A')}")

    if 'scores_breakdown' in selection_result:
        breakdown = selection_result['scores_breakdown']
        print()
        print("Score Breakdown:")
        print(f"  Keyword match: {breakdown.get('keyword_score', 0):.0%}")
        print(f"  Indicator match: {breakdown.get('indicator_score', 0):.0%}")
        print(f"  Final score: {breakdown.get('final_score', 0):.0%}")

    if selection_result.get('category_data'):
        cat_data = selection_result['category_data']
        print()
        print("Category Details:")
        print(f"  Name: {cat_data.get('category_name', 'N/A')}")
        print(f"  Purpose: {cat_data.get('purpose', 'N/A')}")
        print(f"  Posts: {cat_data.get('post_count', 0)}")

    print("=" * 60)


if __name__ == "__main__":
    # Example usage and testing
    print("Category Selector Module")
    print("This module is meant to be imported and used with analysis JSON data.")
    print()
    print("Example usage:")
    print("""
    from category_selector import select_category_for_generation

    # Load your analysis JSON
    with open('output/design_analysis_*.json', 'r') as f:
        analysis = json.load(f)

    # Select category based on user input
    user_input = "We're hiring a new social media manager!"
    result = select_category_for_generation(user_input, analysis)

    print(f"Selected: {result['selected_category_id']}")
    print(f"Confidence: {result['confidence_score']:.0%}")
    print(f"Reasoning: {result['reasoning']}")
    """)
