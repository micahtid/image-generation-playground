import base64
import json
import re
import time
from io import BytesIO

import requests
from PIL import Image

from config import OPENROUTER_API_KEY, OPENROUTER_API_URL, OPENROUTER_MODEL, MAX_IMAGES_PER_POST


ANALYSIS_PROMPT = """
You are creating a REUSABLE DESIGN SYSTEM for generating Instagram posts.

## ANALYSIS METHODOLOGY

You have multiple posts. Post 1 is the NEWEST (most recent).

**PRIMARY REFERENCE**: Base your design system on POST 1 - this represents the current style.

**PATTERN VALIDATION**: Check if elements from Post 1 also appear consistently in Posts 2-5.
- If an element appears in 4+ posts -> It's a CORE PATTERN (definitely include)
- If an element appears in 2-3 posts -> It's a COMMON PATTERN (include if prominent in Post 1)
- If an element appears in only 1 post -> It's likely a ONE-OFF (exclude unless it's in Post 1)

**RESULT**: The design system should primarily reflect Post 1, validated by patterns from other posts.

## IMAGE SEQUENCE DIRECTION (CAROUSEL POSTS)

If a post contains multiple images (carousel), you MUST analyze each image's role and provide specific direction for each position:

**IMAGE 1 (THUMBNAIL/COVER)**: This is the hook. Users see this first in the feed.
- Describe its unique attention-grabbing elements
- Note if it differs from subsequent images (often more bold, provocative, or simplified)
- Specify text treatment (often shorter, punchier headlines)

**IMAGES 2-N (CONTENT SLIDES)**: These are the payoff. Users swipe to see these.
- Describe how they differ from the thumbnail (often more detailed, educational, or informational)
- Note if there's a consistent template across slides 2-N
- Identify any slide-specific variations (e.g., slide 2 = intro, slides 3-5 = bullet points, slide N = CTA)

**CONSISTENCY PATTERNS**:
- Which elements remain IDENTICAL across all slides? (logo position, background color, frame)
- Which elements CHANGE per slide? (main text, supporting images, icons)
- Is there a visual "thread" connecting slides? (color bar, numbering, progress indicator)

In the JSON output, include an `image_sequence` object that explicitly defines:
- `thumbnail_style`: Specific direction for image 1
- `content_slide_style`: Template for images 2-N
- `slide_variations`: Any per-slide differences
- `consistent_elements`: What stays the same across ALL slides
- `changing_elements`: What varies per slide

## ASSET RECREATION INSTRUCTIONS

The image generation model will NOT have access to the original photos, icons, decorations, or brand assets. You MUST provide explicit instructions for recreating every visual element.

**FOR PHOTOGRAPHS/IMAGES WITHIN THE DESIGN**:
- Describe the subject matter explicitly (e.g., "a diverse group of 5-6 young adults, ages 20-30, smiling and engaged in conversation")
- Specify the photography style (candid vs posed, indoor vs outdoor, lighting mood)
- Describe the color grading/filter applied (warm tones, high contrast, desaturated, etc.)
- Specify the crop/framing (close-up, medium shot, full body, etc.)
- If the image is masked/cropped into a shape, describe that shape precisely

**FOR ICONS AND ILLUSTRATIONS**:
- Describe the icon style (flat, outlined, filled, 3D, hand-drawn, etc.)
- Specify the stroke weight relative to the overall design (thin/medium/thick lines)
- Describe the exact icon concept (e.g., "a simple calendar icon showing a checkmark on a date")
- If custom illustrations, describe the illustration style (minimalist, detailed, cartoonish, realistic)

**FOR DECORATIVE ELEMENTS**:
- Describe patterns in detail (e.g., "organic flowing wave shapes curving from bottom-left to top-right")
- Specify if decorations are geometric or organic, symmetrical or asymmetric
- Describe any texture overlays (grain, noise, paper texture, etc.)
- Specify opacity and blending with background

**FOR LOGOS/WORDMARKS** (when brand logo isn't provided):
- Describe the placeholder: "A text-based logo placeholder reading '[BRAND]' in [font style] at [position]"
- This allows users to replace with their actual logo later

Include an `asset_recreation` object in the JSON that provides generation-ready descriptions for EVERY non-text visual element.

## PLACEHOLDER CONTENT DIRECTION

When generating new posts, the image generation model needs content to display. Provide guidance for creating RELEVANT placeholder content:

**FOR HEADLINES/TEXT**:
- Suggest thematic alternatives that match the brand voice (e.g., "Use action-oriented headlines like 'Join the Movement' or 'Your Impact Starts Here'")
- Specify text length constraints (e.g., "Headlines should be 2-4 words maximum")
- If the brand uses specific phrases or CTAs, list them as options

**FOR NUMBERS/STATISTICS**:
- Suggest realistic placeholder ranges (e.g., "Use impactful numbers between 100-10,000 for volunteer counts")
- Specify number formatting (with commas, abbreviated like '10K', etc.)

**FOR SUPPORTING IMAGERY**:
- Provide 3-5 alternative subject suggestions that fit the brand (e.g., "community gatherings, nature scenes, hands helping, diverse faces")
- Ensure suggestions align with the brand's mood and values

**FOR DATES/EVENTS**:
- Suggest format patterns (e.g., "Use format like 'March 15, 2024' or 'THIS SATURDAY'")
- Recommend generic event types that fit the brand

Include a `placeholder_guidance` object with these recommendations so the image generator can create coherent, on-brand content.

## OUTPUT STRUCTURE

Create a JSON with:
1. **design_system** - All specifications (colors, fonts, layout, decorations)
2. **prompt_template** - A natural language prompt for image generators

## ABOUT COLORS

For each color, provide:
- `hex`: The exact color code (for developers/tools)
- `name`: A descriptive name (for image generation prompts)

Image generators understand "vibrant magenta" better than "#FF58C1".
Use the `name` field in prompt_template, keep `hex` for reference.

## ABOUT THE prompt_template

The prompt_template is for image generation AI (DALL-E, Midjourney, etc).

**CRITICAL**: These AIs can accidentally render text literally.
- If you write "#FF58C1", it might appear AS TEXT in the image
- If you write "-5 degrees", those characters might appear AS TEXT

**USE DESCRIPTIVE LANGUAGE** in the prompt_template:
- "vibrant magenta background" NOT "#FF58C1 background"
- "slightly tilted to the left" NOT "-5 degrees rotation"
- "large bold text" NOT "9% font size"

**CONTENT NUMBERS ARE FINE**: If the actual content has numbers (like "10 volunteers" or "2024"), those SHOULD appear. Only DESIGN SPECIFICATION values should be avoided.

## JSON STRUCTURE

```json
{{
  "design_system": {{
    "canvas": {{
      "width": 1080,
      "height": 1350,
      "aspect_ratio": "4:5"
    }},

    "colors": {{
      "primary": {{
        "hex": "#FF58C1",
        "name": "vibrant magenta"
      }},
      "secondary": {{
        "hex": "#005EB8",
        "name": "royal blue"
      }},
      "accent": {{
        "hex": "#FFD700",
        "name": "golden yellow"
      }},
      "background": {{
        "hex": "#FF58C1",
        "name": "vibrant magenta"
      }},
      "text": {{
        "hex": "#FFFFFF",
        "name": "white"
      }}
    }},

    "typography": {{
      "headline": {{
        "font_family": "League Spartan",
        "font_weight": 800,
        "size_percent": 9,
        "color": "text",
        "transform": "uppercase",
        "alignment": "left",
        "rotation": 0,
        "rotation_description": "horizontal"
      }},
      "subheadline": {{
        "font_family": "Dancing Script",
        "font_weight": 700,
        "size_percent": 11,
        "color": "text",
        "transform": "none",
        "alignment": "center",
        "rotation": 0,
        "rotation_description": "horizontal"
      }},
      "body": {{
        "font_family": "Montserrat",
        "font_weight": 600,
        "size_percent": 4,
        "color": "text",
        "alignment": "left"
      }}
    }},

    "elements": [
      {{
        "name": "unique identifier for this element",
        "type": "text/image/shape/logo/container",
        "description": "what this element is",
        "position": {{
          "x_percent": 8,
          "y_percent": 12,
          "width_percent": 50,
          "height_percent": "auto or specific value",
          "anchor": "top-left/center/bottom-right/etc"
        }},
        "edges": {{
          "touches_top": false,
          "touches_bottom": false,
          "touches_left": false,
          "touches_right": false,
          "gap_to_top": 12,
          "gap_to_bottom": null,
          "gap_to_left": 8,
          "gap_to_right": null
        }},
        "spacing": {{
          "element_above": "name of element or null",
          "gap_above": 5,
          "element_below": "name of element or null",
          "gap_below": 8,
          "element_left": null,
          "gap_left": null,
          "element_right": null,
          "gap_right": null
        }},
        "visual": {{
          "corner_radius": 0,
          "corner_description": "sharp corners or rounded with X radius",
          "shadow": "none or full shadow specs",
          "border": "none or full border specs",
          "opacity": 100
        }},
        "overlap": {{
          "overlaps_with": null,
          "overlap_description": "none or describe overlap"
        }},
        "notes": "any additional clarification about this element"
      }}
    ],

    "element_groups": [
      {{
        "group_name": "name this group",
        "elements": ["element1", "element2"],
        "arrangement": "horizontal/vertical/grid",
        "gap_between": 3,
        "alignment": "top/center/bottom for horizontal, left/center/right for vertical"
      }}
    ],

    "background": {{
      "type": "solid with pattern",
      "base_color": "primary",
      "pattern": {{
        "type": "organic waves",
        "description": "Subtle flowing wave shapes in a lighter shade of the base color",
        "opacity_percent": 15
      }},
      "overlay": {{
        "enabled": false,
        "color": null,
        "opacity_percent": 0
      }}
    }},

    "logo": {{
      "position": "top-right",
      "x_percent": 92,
      "y_percent": 8,
      "size_percent": 12,
      "style": "white text wordmark"
    }},

    "decorative_elements": [
      {{
        "type": "wave pattern",
        "description": "Organic flowing curves",
        "color": "lighter shade of background",
        "opacity_percent": 20,
        "position": "background layer"
      }}
    ],

    "global_defaults": {{
      "minimum_margin": 8,
      "default_corner_radius": 0,
      "default_shadow": "none",
      "default_border": "none",
      "notes": "Defaults that apply unless overridden in individual elements"
    }}
  }},

  "brand_style": {{
    "mood": "Youthful, energetic, hopeful, community-focused",
    "keywords": ["vibrant", "clean", "modern", "playful", "accessible"],
    "avoid": ["dark colors", "harsh shadows", "cluttered layouts", "thin fonts"]
  }},

  "prompt_template": "YOUR TASK: Write a detailed natural language prompt here that describes the COMPLETE design. This prompt will be given to an image generation AI. It must describe every element, its position, its styling, and its relationship to other elements and edges. Use color NAMES not hex codes. Use relative sizes (large, medium, small) not percentages. Describe edge relationships explicitly (extends to bottom edge, has margin on all sides, etc.). An artist reading this should be able to recreate the design exactly.",

  "generation_instructions": {{
    "required": [
      "List the visual elements that MUST appear in every post"
    ],
    "forbidden": [
      "DO NOT render hex color codes (like #FF58C1) as visible text",
      "DO NOT render design metrics (font sizes, percentages, coordinates) as visible text",
      "DO NOT render degree symbols or rotation values as visible text",
      "NOTE: Content numbers ARE allowed (e.g., '10 volunteers', 'Chapter 5', '2024')",
      "NOTE: Only DESIGN SPECIFICATION values should be hidden, not content"
    ],
    "notes": "Technical values in design_system are for programmatic reference. The prompt_template uses descriptive names for image generation."
  }},

  "image_sequence": {{
    "is_carousel": true,
    "total_slides": 5,
    "thumbnail_style": {{
      "description": "The first slide is the hook - bold, attention-grabbing, minimal text",
      "unique_elements": ["Large headline only", "No body text", "Hero image prominent"],
      "text_approach": "Single punchy headline, 2-4 words maximum",
      "visual_intensity": "High contrast, bold colors, simplified layout"
    }},
    "content_slide_style": {{
      "description": "Slides 2-N deliver the content - more detailed, educational",
      "template": "Each slide follows the same structure with varying content",
      "text_approach": "Subheadline + 2-3 bullet points or short paragraphs",
      "visual_intensity": "Consistent with thumbnail but allows more text density"
    }},
    "slide_variations": [
      {{"slide": 2, "role": "Introduction/Context"}},
      {{"slide": 3, "role": "Main content point 1"}},
      {{"slide": 4, "role": "Main content point 2"}},
      {{"slide": 5, "role": "Call-to-action/Conclusion"}}
    ],
    "consistent_elements": ["Logo position", "Background color", "Frame/border treatment", "Font choices"],
    "changing_elements": ["Headline text", "Body text", "Supporting imagery", "Icons"]
  }},

  "asset_recreation": {{
    "photographs": [
      {{
        "element_name": "hero_image",
        "subject": "Describe exactly what should be in the photo",
        "style": "candid/posed, indoor/outdoor",
        "lighting": "natural/studio, warm/cool, high-key/low-key",
        "color_grading": "warm tones, slight desaturation, high contrast",
        "framing": "medium shot, subject centered, shallow depth of field",
        "mask_shape": "circular crop with 2px white border"
      }}
    ],
    "icons": [
      {{
        "element_name": "calendar_icon",
        "concept": "A monthly calendar with one date circled",
        "style": "flat filled icon, single color",
        "stroke_weight": "N/A for filled icons",
        "color": "Uses 'accent' color from palette"
      }}
    ],
    "decorative_elements": [
      {{
        "element_name": "background_waves",
        "description": "Organic flowing curves emanating from bottom-left corner",
        "style": "Smooth bezier curves, varying thickness",
        "opacity": "15-20% opacity",
        "color": "Lighter tint of primary color"
      }}
    ],
    "logo_placeholder": {{
      "text": "[BRAND]",
      "style": "Bold sans-serif wordmark",
      "color": "White on colored backgrounds",
      "position": "Top-right corner with comfortable margin"
    }}
  }},

  "placeholder_guidance": {{
    "headlines": {{
      "voice": "Action-oriented, empowering, community-focused",
      "length": "2-5 words",
      "examples": ["Join the Movement", "Make Your Impact", "Together We Rise", "Your Story Matters"],
      "avoid": ["Negative framing", "Overly corporate language", "Jargon"]
    }},
    "statistics": {{
      "format": "Use commas for thousands, spell out 'million/billion'",
      "realistic_ranges": {{
        "volunteers": "500-50,000",
        "donations": "$10,000-$500,000",
        "impact_numbers": "1,000-100,000"
      }},
      "display_style": "Large bold number + smaller descriptor"
    }},
    "supporting_imagery": {{
      "on_brand_subjects": [
        "Diverse groups of people collaborating",
        "Hands joined or helping",
        "Community gatherings outdoors",
        "Close-up authentic smiles",
        "Nature scenes representing growth"
      ],
      "style_notes": "Authentic, candid moments preferred over staged stock photos"
    }},
    "dates_and_events": {{
      "date_format": "MONTH DD, YYYY or 'THIS SATURDAY'",
      "event_types": ["Community Meetup", "Volunteer Day", "Workshop", "Celebration"],
      "time_format": "10 AM - 2 PM (use AM/PM, not 24-hour)"
    }}
  }}
}}
```

## YOUR TASK

1. **Analyze Post 1 thoroughly** - this is your primary reference
2. **Validate patterns** - check which elements from Post 1 appear in other posts
3. **Extract design_system** - all colors (hex + name), fonts, layout, decorations
4. **Write prompt_template** - using DESCRIPTIVE language only (no hex codes, no percentages, no degree values)
5. **Fill generation_instructions** - list required and forbidden elements

## ZERO AMBIGUITY RULE

Every description must be EXHAUSTIVELY SPECIFIC. An image generator should have ZERO questions. If there is ANY room for interpretation, you have FAILED.

**THE GOLDEN RULE**: After reading your output, an artist in a completely different country who has NEVER seen the original posts should be able to recreate the design with 95%+ accuracy. If they would need to guess ANYTHING, your description is incomplete.

**FOR EVERY ELEMENT YOU IDENTIFY, SPECIFY:**

1. **Edge Relationship** (MANDATORY - never skip)
   - Does this element touch the top edge of the canvas? Yes/No
   - Does this element touch the bottom edge? Yes/No
   - Does this element touch the left edge? Yes/No
   - Does this element touch the right edge? Yes/No
   - If no, what is the EXACT gap to each edge? (use % of canvas)
   - NEVER say "near the edge" - specify EXACTLY how near

2. **Adjacent Element Spacing** (MANDATORY - never skip)
   - What element is DIRECTLY above this one? EXACT gap between them?
   - What element is DIRECTLY below this one? EXACT gap between them?
   - What element is DIRECTLY to the left? EXACT gap?
   - What element is DIRECTLY to the right? EXACT gap?
   - If no adjacent element, state "nothing adjacent on [side]"

3. **Visual Properties** (MANDATORY - never skip)
   - Are corners rounded? If yes, specify radius as % of element width. If no, state "sharp corners (0 radius)".
   - Is there a shadow? If yes: direction, blur radius, spread, color, opacity. If no, state "no shadow".
   - Is there a border? If yes: width, style (solid/dashed), color. If no, state "no border".
   - What is the opacity? State as percentage. If fully visible, state "100% opacity (fully opaque)".

4. **Grouping** (MANDATORY for repeated elements)
   - If multiple similar elements exist (e.g., row of images), what's the EXACT gap between each?
   - Are they aligned? How? (top-aligned, center-aligned, bottom-aligned, baseline-aligned)
   - Is the group centered on canvas? Specify horizontal AND vertical centering separately.

5. **Overlap** (MANDATORY - never skip)
   - Does this element overlap with any other? State "no overlap" or list exactly which elements
   - If overlapping: which element is in FRONT? By how much does it overlap (% or px)?
   - What is the z-index order of all overlapping elements?

6. **Text-Specific** (MANDATORY for all text elements)
   - Exact text content or placeholder pattern (e.g., "[HEADLINE - 2-4 words]")
   - Text alignment within its container (left/center/right/justified)
   - Line height / letter spacing if notable
   - Text color AND background color (or "transparent background")
   - Does text have outline/stroke? Shadow? Gradient fill?

7. **Image-Specific** (MANDATORY for all image elements)
   - Is the image masked/cropped? What shape? (rectangle, circle, rounded rectangle, custom path)
   - Does the image have a border/frame? Specs?
   - Is there an overlay on the image? (color tint, gradient, etc.)
   - Object-fit behavior: cover, contain, or stretched?

**FORBIDDEN VAGUE TERMS** (never use these):
- "approximately" → use exact percentage
- "near" → specify exact position
- "slightly" → quantify the amount
- "somewhat" → be specific
- "around" → give exact value
- "a bit" → measure it
- "fairly" → define precisely
- "pretty much" → state exactly

**UNIVERSAL CHECKLIST (apply to EVERY element - no exceptions):**
- [ ] Position defined (x%, y%, width%, height%)
- [ ] All four edge relationships specified with exact gaps
- [ ] Spacing to adjacent elements specified (or "none adjacent")
- [ ] Corner treatment specified (including "sharp corners")
- [ ] Shadow specified (including "no shadow")
- [ ] Border specified (including "no border")
- [ ] Opacity specified (including "100% fully opaque")
- [ ] Overlap status specified (including "no overlap")
- [ ] Z-index/layer order specified if relevant

## FINAL CHECKLIST

Before submitting, verify ALL of the following:

**Core Requirements:**
- [ ] Based primarily on Post 1?
- [ ] Patterns validated across posts?
- [ ] Every color has `hex` AND `name`?
- [ ] prompt_template has NO technical values (hex codes, numbers, percentages)?
- [ ] Every element passes the universal checklist above?

**New Section Requirements:**
- [ ] `image_sequence` filled out if post is a carousel (or `is_carousel: false` if single image)?
- [ ] `asset_recreation` includes generation instructions for EVERY photo, icon, and decoration?
- [ ] `placeholder_guidance` provides on-brand content suggestions for text, numbers, images, and dates?

**Zero Ambiguity Test:**
- [ ] Could an artist who has NEVER seen the original recreate it with 95%+ accuracy?
- [ ] Are there ANY vague words like "approximately", "near", "slightly", "somewhat"?
- [ ] Is EVERY element's position, spacing, and styling explicitly defined?
- [ ] Does the prompt_template describe exact placement using natural language (not just "top-right" but "positioned in the top-right corner, with an 8% margin from the top edge and 5% margin from the right edge")?

Here is the metadata for each post (images are attached):

{posts_data}

Return ONLY the JSON object. No markdown code blocks. No explanations.
"""


def compress_image(image_data, max_size=800, quality=85):
    """Compress image to reduce payload size."""
    try:
        img = Image.open(BytesIO(image_data))

        # Convert to RGB if necessary (handles PNG with alpha)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        # Resize if larger than max_size
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Compress to JPEG
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        return buffer.getvalue(), 'image/jpeg'
    except Exception as e:
        print(f"  Warning: Could not compress image: {e}")
        return image_data, 'image/jpeg'


def download_image_as_base64(url, max_retries=3):
    """Download an image from URL with retry logic and compression."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                image_data = response.content

                # Compress image to reduce payload size
                compressed_data, media_type = compress_image(image_data)

                base64_data = base64.b64encode(compressed_data).decode('utf-8')
                return base64_data, media_type

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s, 6s
                print(f"  Retry {attempt + 1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"  Warning: Failed after {max_retries} attempts: {e}")
        except Exception as e:
            print(f"  Warning: Failed to download image: {e}")
            break

    return None, None


def collect_image_urls(posts):
    """Collect all image URLs from posts."""
    image_urls = []

    for i, post in enumerate(posts, 1):
        post_images = []

        if post.get('displayUrl'):
            post_images.append(post['displayUrl'])

        child_posts = post.get('childPosts', [])
        for child in child_posts[:MAX_IMAGES_PER_POST]:
            if child.get('displayUrl') and child['displayUrl'] not in post_images:
                post_images.append(child['displayUrl'])

        images_array = post.get('images', [])
        for img_url in images_array[:MAX_IMAGES_PER_POST]:
            if img_url and img_url not in post_images:
                post_images.append(img_url)

        post_images = post_images[:MAX_IMAGES_PER_POST]

        for j, url in enumerate(post_images, 1):
            image_urls.append((i, j, url))

    return image_urls


def validate_prompt_template(analysis_json):
    """Check if prompt_template contains raw technical values."""
    if 'prompt_template' not in analysis_json:
        return

    prompt = analysis_json['prompt_template']
    issues = []

    # Check for hex codes
    if re.search(r'#[0-9A-Fa-f]{3,8}', prompt):
        issues.append("hex codes (e.g., #FF58C1)")

    # Check for percentages
    if re.search(r'\d+%', prompt):
        issues.append("percentage values (e.g., 8%)")

    # Check for degree measurements
    if re.search(r'-?\d+\s*(degrees?|deg|\u00b0)', prompt, re.IGNORECASE):
        issues.append("degree measurements")

    # Check for pixel measurements
    if re.search(r'\d+\s*px', prompt, re.IGNORECASE):
        issues.append("pixel values")

    if issues:
        print(f"Warning: prompt_template contains raw values: {', '.join(issues)}")
        print("  These may render as visible text. Use descriptive names instead.")


def analyze_posts_with_gemini(posts):
    """Analyze Instagram posts using Gemini via OpenRouter."""

    # Prepare posts metadata - Post 1 is NEWEST
    posts_for_analysis = []
    for i, post in enumerate(posts, 1):
        post_data = {
            "post_number": i,
            "is_primary_reference": i == 1,
            "url": post.get('url', 'N/A'),
            "caption": post.get('caption', 'N/A'),
            "type": post.get('type', 'N/A'),
            "timestamp": post.get('timestamp', 'N/A')
        }
        posts_for_analysis.append(post_data)

    # Collect all image URLs
    image_urls = collect_image_urls(posts)
    print(f"Found {len(image_urls)} images across {len(posts)} posts")

    # Build multimodal content array
    content = []

    # Add the text prompt first
    formatted_prompt = ANALYSIS_PROMPT.format(
        posts_data=json.dumps(posts_for_analysis, indent=2)
    )
    content.append({
        "type": "text",
        "text": formatted_prompt
    })

    # Download and add images as base64
    print("Downloading images for analysis...")
    successful_images = 0
    for post_num, img_num, url in image_urls:
        print(f"  Downloading Post {post_num}, Image {img_num}...")
        base64_data, media_type = download_image_as_base64(url)

        if base64_data:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{base64_data}"
                }
            })
            successful_images += 1
        else:
            print(f"  Skipping Post {post_num}, Image {img_num} (download failed)")

    print(f"Successfully downloaded {successful_images}/{len(image_urls)} images")

    if successful_images == 0:
        raise Exception("No images could be downloaded for analysis")

    print("Sending posts and images to Gemini for analysis...")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ]
    }

    # Retry logic for API call
    max_retries = 3
    response = None
    for attempt in range(max_retries):
        try:
            response = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=120  # 2 minute timeout for large payloads
            )
            break  # Success, exit retry loop
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                print(f"  API connection failed, retry {attempt + 1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise Exception(f"API connection failed after {max_retries} attempts: {e}")

    if response is None or response.status_code != 200:
        error_msg = response.text if response else "No response"
        raise Exception(f"OpenRouter API error: {error_msg}")

    response_data = response.json()
    analysis_text = response_data['choices'][0]['message']['content']

    print("Analysis complete!")

    # Clean up response - remove markdown if present
    analysis_text = analysis_text.strip()
    if analysis_text.startswith("```json"):
        analysis_text = analysis_text[7:]
    if analysis_text.startswith("```"):
        analysis_text = analysis_text[3:]
    if analysis_text.endswith("```"):
        analysis_text = analysis_text[:-3]
    analysis_text = analysis_text.strip()

    try:
        analysis_json = json.loads(analysis_text)
        validate_prompt_template(analysis_json)
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse JSON response: {e}")
        print("Raw response:", analysis_text[:500])
        analysis_json = {"raw_analysis": analysis_text, "error": "Failed to parse JSON"}

    return analysis_json


if __name__ == "__main__":
    test_posts = [
        {
            "url": "https://instagram.com/p/test",
            "caption": "Test caption",
            "displayUrl": "https://example.com/image.jpg",
            "type": "Image"
        }
    ]

    result = analyze_posts_with_gemini(test_posts)
    print(json.dumps(result, indent=2))
