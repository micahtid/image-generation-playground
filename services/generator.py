"""
Image generation and editing service.
- Initial generation: Uses OpenRouter Gemini 2.5 Flash Image
- Editing: Uses Replicate p-image-edit
"""
import base64
import json
import mimetypes
import os
import uuid

import replicate
import requests

from config import (
    COST_PER_MEGAPIXEL_GO_FAST, MEGAPIXELS_1024x1024, REPLICATE_API_TOKEN,
    OPENROUTER_API_KEY, OPENROUTER_API_URL
)


# =============================================================================
# Prompt Utilities
# =============================================================================

def get_editing_prompt(user_task):
    """Optimize prompt for p-image-edit model."""
    return f"{user_task}, maintaining the same style, color, size, shape, font, case, position, lighting, and background for everything not explicitly changed"


def get_model_optimized_prompt(user_task, model):
    """Get optimized prompt for the specified model."""
    return get_editing_prompt(user_task)


# =============================================================================
# Image Utilities
# =============================================================================

def image_file_to_data_url(image_path):
    """Convert a local image file into a base64 data URL for API uploads."""
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = 'application/octet-stream'

    with open(image_path, 'rb') as image_file:
        encoded = base64.b64encode(image_file.read()).decode('utf-8')

    return f'data:{mime_type};base64,{encoded}'


def persist_data_url_image(data_url, upload_folder):
    """Persist large data URLs to disk to avoid oversized session cookies."""
    header, encoded = data_url.split(',', 1)
    mime_type = header.split(';')[0].replace('data:', '') if 'data:' in header else 'image/png'
    extension = mimetypes.guess_extension(mime_type) or '.png'
    filename = f'replicate_edit_{uuid.uuid4().hex}{extension}'
    filepath = os.path.join(upload_folder, filename)

    with open(filepath, 'wb') as image_file:
        image_file.write(base64.b64decode(encoded))

    return filepath, f'/uploads/{filename}'


def is_data_url(value):
    """Check if a value is a data URL."""
    return isinstance(value, str) and value.startswith('data:image/')


# =============================================================================
# Image Generator
# =============================================================================

class ImageGenerator:
    """Generate images using OpenRouter Gemini 2.5 Flash Image."""
    
    def __init__(self, api_key=OPENROUTER_API_KEY):
        if not api_key:
            print("Warning: OPENROUTER_API_KEY is missing")
        self.api_key = api_key
        # Config already has full path: https://openrouter.ai/api/v1/chat/completions
        self.api_url = OPENROUTER_API_URL or "https://openrouter.ai/api/v1/chat/completions"

    def calculate_cost(self, has_input_image=False):
        """Estimate cost. Gemini Flash is very cheap, setting a nominal/low estimate."""
        return 0.005  # Nominal cost for generating an image

    def generate_image(self, prompt, input_image=None):
        """Generate an image using Gemini via OpenRouter."""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/micahtid/image-generation-playground",
            "X-Title": "Image Gen Playground",
            "Content-Type": "application/json"
        }
        
        # Gemini 2.5 Flash Image via OpenRouter
        # We ask it to generate an image. It usually returns a markdown link.
        payload = {
            "model": "google/gemini-2.5-flash-image",
            "messages": [
                {
                    "role": "user", 
                    "content": f"Generate an image based on this description. The image should be high quality. Description: {prompt}"
                }
            ]
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=60
            )
            
            if response.status_code != 200:
                error_msg = f"OpenRouter API Error: {response.status_code} - {response.text}"
                print(error_msg)
                raise Exception(error_msg)
                
            result = response.json()
            
            if 'choices' not in result or not result['choices']:
                raise Exception("No choices returned from OpenRouter")
            
            message = result['choices'][0]['message']
            content = message.get('content', '')
            
            # Debug: Print first 500 chars of content
            print(f"[DEBUG] Gemini Response Content: {content[:500]}")
            
            # Strategy 0: Check for OpenRouter/Gemini specific 'images' field in message
            # The debug output shows the image comes in message['images'][0]['image_url']['url']
            if 'images' in message and message['images']:
                try:
                    return message['images'][0]['image_url']['url']
                except (KeyError, IndexError) as e:
                    print(f"[DEBUG] Failed to parse images field: {e}")

            # Strategy 1: Look for markdown image syntax ![...](url)
            match = re.search(r'!\[.*?\]\((https?://[^\)]+)\)', content)
            if match:
                return match.group(1)
                
            # Strategy 2: Look for markdown link syntax [text](url) - sometimes it returns this
            match = re.search(r'\[.*?\]\((https?://[^\)]+)\)', content)
            if match:
                return match.group(1)
                
            # Strategy 3: Look for explicit http urls ending in image extensions
            match = re.search(r'(https?://[^\s)]+\.(?:jpg|jpeg|png|webp))', content, re.IGNORECASE)
            if match:
                return match.group(1)
                
            # Strategy 4: Look for any googleusercontent or similar generated image URL pattern
            # Often generated images are hosted on distinct domains
            match = re.search(r'(https?://[a-zA-Z0-9-]+\.googleusercontent\.com/[^\s)]+)', content)
            if match:
                return match.group(1)

            # Strategy 5: Aggressive fallback - find ANY http url if content is short enough
            if len(content) < 1000:
                match = re.search(r'(https?://[^\s)"]+)', content)
                if match:
                    # Filter out common non-image URLs if needed, but for now accept it
                    return match.group(1)
            
            # If no URL found, raise error with the content for debugging
            # Also dump the full message to see if we missed where the image is
            raise Exception(f"Could not find image URL. Message keys: {list(message.keys())}. Content: {content[:200]}...")

        except Exception as e:
            raise Exception(f"Error generating image with Gemini: {str(e)}")


# =============================================================================
# Image Editor
# =============================================================================

class ImageEditor:
    """Edit existing images using Replicate API."""
    
    def __init__(self, api_token=REPLICATE_API_TOKEN):
        if not api_token:
            raise ValueError("REPLICATE_API_TOKEN is required")
        self.client = replicate.Client(api_token=api_token)

    def calculate_cost(self, has_input_image=True, model="prunaai/p-image-edit"):
        """Calculate cost for image editing operation."""
        # Currently only using p-image-edit at $0.01 per image
        return 0.01

    def edit_image(self, prompt, input_image, model="prunaai/p-image-edit"):
        """Edit an image based on prompt instructions."""
        # Use optimized prompt
        enhanced_prompt = get_model_optimized_prompt(prompt, model)

        try:
            if not input_image:
                raise ValueError("input_image is required for editing")

            # Detect region-based edit - turn off turbo for better precision
            is_region_edit = ' in the ' in prompt.lower()

            input_params = {
                "prompt": enhanced_prompt,
                "turbo": not is_region_edit,
                "aspect_ratio": "match_input_image"
            }
            param_name = "images"

            # Handle both URL and local file paths
            if isinstance(input_image, str) and input_image.startswith(('http://', 'https://')):
                input_params[param_name] = [input_image]
                output = self.client.run("prunaai/p-image-edit", input=input_params)
            else:
                if not os.path.exists(input_image):
                    raise FileNotFoundError(f"Input image file not found: {input_image}")

                with open(input_image, 'rb') as image_file:
                    input_params[param_name] = [image_file]
                    output = self.client.run("prunaai/p-image-edit", input=input_params)

            # Calculate cost
            cost = self.calculate_cost(has_input_image=True, model=model)

            # Extract image URL from response
            if isinstance(output, list) and len(output) > 0:
                return output[0], cost
            return output, cost

        except FileNotFoundError:
            raise Exception(f"Input image file not found: {input_image}")
        except Exception as e:
            raise Exception(f"Error editing image with p-image-edit: {str(e)}")


# =============================================================================
# Category Selector (from category_selector.py)
# =============================================================================

def extract_keywords(text: str) -> list:
    """Extract meaningful keywords from user text."""
    import re
    
    stop_words = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
        'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
        'that', 'the', 'to', 'was', 'will', 'with', 'we', 'our',
        'you', 'your', 'this', 'these', 'those', 'about'
    }

    text_lower = text.lower()
    text_clean = re.sub(r'[^\w\s\'-]', ' ', text_lower)
    words = text_clean.split()

    keywords = [w for w in words if len(w) > 3 and w not in stop_words]
    return keywords


def calculate_keyword_score(user_keywords: list, category_keywords: list) -> float:
    """Calculate match score based on keyword overlap."""
    if not user_keywords or not category_keywords:
        return 0.0

    matches = sum(1 for uk in user_keywords if any(ck in uk or uk in ck for ck in category_keywords))
    score = matches / len(user_keywords)
    return min(score, 1.0)


def detect_content_indicators(text: str) -> dict:
    """Detect content indicators in user text."""
    import re
    
    text_lower = text.lower()

    return {
        "has_date": bool(re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december|\d{1,2}/\d{1,2}(/\d{2,4})?)', text_lower)),
        "has_cta": any(word in text_lower for word in ['apply', 'join', 'sign up', 'register', 'volunteer', 'hiring', 'deadline']),
        "has_narrative": any(word in text_lower for word in ['story', 'experience', 'testimonial', 'journey', 'impact']),
        "has_educational": any(word in text_lower for word in ['learn', 'how to', 'tips', 'guide', 'tutorial', 'fact']),
        "has_announcement": any(word in text_lower for word in ['announcing', 'new', 'launching', 'introducing', 'reminder']),
        "has_question": '?' in text
    }


def calculate_indicator_score(user_indicators: dict, category_indicators: list) -> float:
    """Calculate score based on content indicator matches."""
    if not category_indicators:
        return 0.0

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

    score = matches / len(category_indicators) if category_indicators else 0.0
    return min(score, 1.0)


def select_category_for_generation(user_text: str, analysis_json: dict) -> dict:
    """
    Auto-select best category based on user's text/topic.

    Algorithm:
    1. Extract keywords from user_text
    2. Score each category by keyword matches
    3. Analyze content indicators (dates, CTAs, narrative markers)
    4. Combine: final_score = (0.6 * keyword_score) + (0.4 * indicator_score)
    5. Return category with highest score (min threshold: 0.3)
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
        recommendation = analysis_json.get('analysis_metadata', {}).get('recommended_category_for_generation', {})
        recommended_id = recommendation.get('category_id')

        if recommended_id:
            recommended_cat = next((cat for cat in categories if cat.get('category_id') == recommended_id), None)

            return {
                "selected_category_id": recommended_id,
                "confidence_score": best_score,
                "reasoning": f"Low confidence match (score: {best_score:.2f}). Using recommended: {recommendation.get('reasoning', 'Most recent post style')}",
                "category_data": recommended_cat,
                "selection_method": "fallback_to_recommendation"
            }
        else:
            primary_id = analysis_json.get('analysis_metadata', {}).get('primary_category')
            primary_cat = next((cat for cat in categories if cat.get('category_id') == primary_id), None)

            return {
                "selected_category_id": primary_id,
                "confidence_score": best_score,
                "reasoning": f"Low confidence match (score: {best_score:.2f}). Defaulting to primary category (most recent post)",
                "category_data": primary_cat,
                "selection_method": "fallback_to_primary"
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
