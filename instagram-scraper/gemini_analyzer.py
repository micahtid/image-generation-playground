import base64
import json
import re
import time
from datetime import datetime
from io import BytesIO

import requests
from PIL import Image

from config import OPENROUTER_API_KEY, OPENROUTER_API_URL, OPENROUTER_MODEL, MAX_IMAGES_PER_POST


CATEGORY_DETECTION_PROMPT = """
You are analyzing 5 Instagram posts to identify HOLISTIC TREND CATEGORIES.

A category is defined by CONTENT THEME + VISUAL STYLE combined:
- Content theme: What the post is about (activism call-to-action, behind-the-scenes, testimonial, announcement, educational content, product showcase, community spotlight)
- Visual style: How it's presented (vibrant gradients, minimalist text-only, photo-heavy collage, nature-inspired, bold typography, soft pastels)
- Purpose correlation: Track if certain purposes always use certain themes (e.g., "All announcements use landscape photography")

CRITICAL RULES:
1. Categories are NOT component-level details (don't say "minimalist text overlays" - instead say "Educational content with minimalist text-on-solid-background style")
2. Define categories based on the OVERALL design of each post as a whole
3. Identify 2-4 categories when possible; only use 5 if ALL posts are truly distinct (avoid over-segmentation)
4. A category can be single-post if it is truly unique; DO NOT force unrelated posts together just to reach 2+ posts
5. Post 1 (newest) ALWAYS gets included in a category OR defines a new one if truly unique
6. Track logo placement consistency PER CATEGORY (not globally)
7. If posts share the SAME content theme + layout + typography style but differ only by color, they should be in the SAME category (color variation within a style is valid)
8. Color palettes CAN be categories themselves ONLY when color treatment is the PRIMARY differentiator (e.g., monochrome duotone vs full-color gradients)
9. A category CAN have multiple color palettes (e.g., "Nature posts" might use both "Spring greens" and "Autumn oranges")

TREND TYPE CLASSIFICATION:
Each category must be classified by its PRIMARY trend type. This helps identify what fundamentally defines the category:

- nature-based: Defined by natural elements (outdoor scenes, seasons, landscapes, organic textures)
- color-based: Defined by specific color palette or color treatment (monochrome, vibrant neons, pastels)
- layout-based: Defined by spatial arrangement (grid layout, asymmetric design, centered composition)
- content-based: Defined by subject matter (testimonials, products, events, announcements)
- style-based: Defined by visual aesthetic (minimalist, bold, editorial, playful, professional)
- compositional-based: Defined by visual structure (layered collage, single-focus, split-screen)
- typographic-based: Defined by text treatment (text-only, creative typography, handwritten style)
- media-based: Defined by media type (photography-heavy, illustration-based, video stills, mixed media)

A category can have PRIMARY + SECONDARY trend types for nuanced classification.
Example: "Editorial news posts" = PRIMARY: style-based, SECONDARY: media-based + content-based

IMPORTANT: Identify universal elements that are CONSISTENT across ALL 5 posts (100% consistency):
- Canvas dimensions (do all posts use the same size?)
- Logo position (does logo appear in the exact same place in every post?)
- Fonts (are the same fonts used across all posts?)
- Brand colors (do the same core brand colors appear in every post?)

OUTPUT JSON:
{
  "categories": [
    {
      "category_id": "unique_snake_case_id",
      "category_name": "Human-readable name combining content + visual style",
      "category_description": "2-3 sentences describing the holistic theme. Focus on what defines this category as a whole.",
      "trend_type_primary": "style-based",
      "trend_types_secondary": ["media-based", "content-based"],
      "trend_type_reasoning": "This category is primarily defined by its bold editorial visual style (style-based), with secondary emphasis on photography usage (media-based) and announcement content (content-based).",
      "post_assignments": [1, 4],
      "purpose": "call_to_action",
      "purpose_correlation": "All CTAs use vibrant gradients" or "Mixed purposes within this style",
      "color_palette_notes": "Single consistent palette: candy pink + royal blue" or "Multiple palettes: warm tones for indoor, cool for outdoor",
      "logo_consistency": "ALWAYS bottom-right" or "MOSTLY bottom-left (75%)" or "VARIABLE"
    }
  ],
  "universal_elements": {
    "canvas_consistent": true,
    "canvas_dimensions": {"width": 1080, "height": 1350, "aspect_ratio": "4:5"},
    "logo_position_consistent": true,
    "universal_logo_position": "top-right",
    "fonts_consistent": true,
    "universal_fonts": ["League Spartan", "Dancing Script", "Montserrat"],
    "brand_colors_present": true,
    "core_brand_colors": [
      {"hex": "#FF58C1", "name": "vibrant candy pink"},
      {"hex": "#005EB8", "name": "royal blue"}
    ]
  },
  "recommended_category": {
    "category_id": "id_of_recommended_category",
    "reasoning": "Post 1 (most recent) belongs to this category, indicating current brand direction. Also most frequently used style with 3 of 5 posts."
  }
}

CATEGORY RECOMMENDATION LOGIC:
Determine which category is RECOMMENDED for generating new posts:
1. PRIMARY: The category containing Post 1 (newest/most recent) - this represents the current brand direction
2. SECONDARY: If Post 1 is an outlier, recommend the category with the most posts
3. REASONING: Explain why this category is recommended (mention Post 1, frequency, trend alignment)

REMEMBER:
- Categories should be holistic (content + visual style together)
- Focus on what makes each post's OVERALL design distinctive
- Universal elements are those that appear in ALL 5 posts without exception
- Per-category tracking captures variations within each trend
"""


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

## TEMPLATE + VARIATION MODE (NEW)

The output JSON is a BASE TEMPLATE, not a 1:1 reconstruction.
- Capture the core components, hierarchy, and style DNA for the category.
- Provide explicit quantitative specs, PLUS allowable variation ranges so new layouts can differ while staying on-brand.
- Every constraint must be unambiguous; variation is only allowed where you explicitly define it.

## ANTI-HALLUCINATION + PRECISION RULES

- Do NOT infer details that are not clearly visible. If you are unsure, omit the detail.
- Rotation/tilt: Only specify rotation if it is clearly present. Otherwise treat text and shapes as perfectly horizontal (no tilt).
- If multiple text orientations exist, list each orientation and assign elements to each; never collapse to a single angle.
- Quantitative mandate: Provide numeric values for size, position, gaps, rotation degrees, line height, and counts for every element.
- Counts: Explicitly state the exact count of icons, decorations, and repeated elements. Do NOT duplicate elements unless they exist in the source.
- Edge contact: If an element touches an edge, set the corresponding `touches_*` to true and `gap_*` to 0 (do not invent margins).
- Layout fidelity: Do NOT normalize or tidy the layout. If spacing or alignment is uneven, staggered, or intentionally irregular, state it explicitly.
- If elements visually interleave or "slide into" each other, document overlap and z-order in `overlap`.

## SPACING AND BREATHING ROOM

- Always specify spacing between components using the `spacing` and `edges` gaps.
- Preserve the observed negative space; ensure the layout does not feel cramped by documenting the real margins and gaps.
- If the layout feels tight, reduce element sizes or increase gaps to create breathing room while keeping overall balance.
- For major elements, name the nearest neighbor above/below/left/right with explicit gaps so spacing is never implicit.
- Avoid vague spacing terms like "distributed"; use numeric gaps or explicit ranges (e.g., 12-18px).

## VARIATION GUIDANCE REQUIREMENTS

- Provide explicit numeric ranges for any allowed variation (position, size, spacing, rotation).
- Specify what can vary vs what must remain fixed (non-negotiables).
- If randomness is desired, define the strength (0-1) and the range for each variable.

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
- Specify the EXACT number of icons and whether they are unique or repeated (do NOT duplicate icons unless they appear multiple times)
- If custom illustrations, describe the illustration style (minimalist, detailed, cartoonish, realistic)

**FOR DECORATIVE ELEMENTS**:
- Describe patterns in detail (e.g., "organic flowing wave shapes curving from bottom-left to top-right")
- Specify if decorations are geometric or organic, symmetrical or asymmetric
- Specify the EXACT count of decorative elements and the coverage area they occupy
- Specify size range relative to nearby text (e.g., "stars range from slightly smaller than the multilingual text height to about 1.5x that height")
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
3. **variation_guidance** - Explicit ranges for allowable layout/style randomness

## ABOUT COLORS

For each color, provide:
- `hex`: The exact color code (for developers/tools). Sample from flat, unshaded areas (avoid shadows or gradients).
- `name`: An optional descriptive name (only if it accurately matches the hex; keep it short and neutral)

Prioritize hex accuracy. Do not "correct" or shift colors to be more aesthetic; match what is visible.
In the prompt_template, prefer palette references (primary/secondary/background) and only use a color name if it is clearly accurate.

## TYPOGRAPHY DETAIL REQUIREMENTS

For each typography style, include BOTH the font name (if known) and a quantitative shape description:
- `x_height_ratio` (0.40-0.80)
- `width_ratio` (condensed <0.90, normal 0.90-1.05, wide >1.05)
- `stroke_contrast` ("none/low/medium/high")
- `terminal_style` ("square/rounded/tapered/bracketed")
- `aperture` ("open/neutral/closed")
- `axis_angle_degrees` (e.g., 0 for upright, -10 for left-leaning)
- `slant_degrees` (0 if upright)
- `curvature` ("geometric/neo-grotesque/humanist/calligraphic")
If the font is script or decorative, describe letter connections, stroke modulation, and loop size in measurable terms (e.g., "ascender loops ~1.2x x-height").

## ABOUT THE prompt_template

The prompt_template is for image generation AI (DALL-E, Midjourney, etc).

**CRITICAL**: These AIs can accidentally render text literally.
- Avoid hex codes in the prompt_template (use palette names like primary/secondary/background).
- You MUST use numeric values for layout precision (percent/px and rotation degrees), but explicitly say: "Do not render numbers as text; numbers are layout constraints only."

**USE PRECISE, LLM-OPTIMIZED LANGUAGE** in the prompt_template:
- Include exact positions, sizes, gaps, and rotation angles using numeric values.
- If there is no visible tilt, explicitly state rotation is 0 degrees.
- If an element touches an edge, say "flush to the edge" or "edge-to-edge" to prevent unintended padding.
- If text uses multiple tilt directions, describe both orientations, counts, and how they interleave.
- Prefer short, directive sentences over poetic language; prioritize constraints and layout facts.
- If variation is allowed, describe the exact numeric range and say "randomize within this range."

**CONTENT NUMBERS ARE FINE**: If the actual content has numbers (like "10 volunteers" or "2024"), those SHOULD appear. DESIGN SPECIFICATION values should be marked as layout constraints and not rendered.

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
          "line_height": 1.0,
          "letter_spacing": 0,
          "color": "text",
          "transform": "uppercase",
          "alignment": "left",
          "rotation": 0,
          "rotation_description": "horizontal",
          "font_characteristics": {{
            "x_height_ratio": 0.72,
            "width_ratio": 0.92,
            "stroke_contrast": "low",
            "terminal_style": "square",
            "aperture": "open",
            "axis_angle_degrees": 0,
            "slant_degrees": 0,
            "curvature": "neo-grotesque"
          }}
        }},
        "subheadline": {{
          "font_family": "Dancing Script",
          "font_weight": 700,
          "size_percent": 11,
          "line_height": 0.95,
          "letter_spacing": 0,
          "color": "text",
          "transform": "none",
          "alignment": "center",
          "rotation": 0,
          "rotation_description": "horizontal",
          "font_characteristics": {{
            "x_height_ratio": 0.55,
            "width_ratio": 1.05,
            "stroke_contrast": "medium",
            "terminal_style": "tapered",
            "aperture": "open",
            "axis_angle_degrees": -8,
            "slant_degrees": -8,
            "curvature": "calligraphic"
          }}
        }},
        "body": {{
          "font_family": "Montserrat",
          "font_weight": 600,
          "size_percent": 4,
          "line_height": 1.3,
          "letter_spacing": 0,
          "color": "text",
          "alignment": "left",
          "font_characteristics": {{
            "x_height_ratio": 0.70,
            "width_ratio": 0.98,
            "stroke_contrast": "low",
            "terminal_style": "square",
            "aperture": "neutral",
            "axis_angle_degrees": 0,
            "slant_degrees": 0,
            "curvature": "geometric"
          }}
        }}
      }},

## VISUAL TAXONOMY (MANDATORY FOR ALL ELEMENTS)

Every element MUST include a comprehensive `visual` object with relevant properties. Token optimization applies ONLY to non-spatial visuals:
- Do NOT omit quantitative layout values (position, size, gaps, rotation)
- ONLY include properties relevant to the specific element type
- Use compact representations where possible for non-spatial fields

## SPATIAL PRECISION REQUIREMENTS

- Provide explicit `position` values for every element (x/y/width/height). Avoid "auto" unless truly unavoidable for text.
- Fill `edges` and `spacing` with real gaps. If an element touches an edge, set the touch flag true and gap to 0.
- If an element appears only once, make that explicit; if repeated, list each instance or clearly describe counts and placements.
- For any edge-touching element, explicitly describe it in the prompt_template as "flush to the [edge]" or "full-bleed/edge-to-edge" with no margin.
- If any element is flush to the canvas edge, set `global_defaults.minimum_margin` to 0.
- Do NOT use vague group placeholders like "12 phrases"; enumerate repeated elements with positions or provide a per-item list.
- For text, always include font size (percent), line height, letter spacing, alignment, and rotation_degrees.
- If layout variation is allowed, provide min/max ranges for position/size/rotation in a dedicated `variation_guidance` object.

### Core Visual Properties

FILL PROPERTIES (shapes, containers, icons, text):
- fill_type: "solid" | "outline" | "gradient" | "pattern" | "none"
- fill_color: Reference to color palette OR descriptive name
- fill_opacity_percent: 0-100 (omit if 100)

STROKE PROPERTIES (icons, shapes, text outlines):
- has_stroke: true (only include if element HAS a stroke, omit if false)
- stroke_color: Color reference
- stroke_width_px: Pixel value
- stroke_style: "solid" | "dashed" | "dotted"

CORNER PROPERTIES (rectangular elements):
- corner_style: "sharp" | "rounded" | "custom"
- corner_radius_px: Exact pixel value (omit if 0)
- corner_description: "sharp corners" | "rounded corners 8px" | etc.

SHADOW PROPERTIES:
- has_shadow: true (only include if element HAS a shadow, omit if false)
- shadow_offset_x_px, shadow_offset_y_px: Pixel offsets
- shadow_blur_px: Blur radius in pixels
- shadow_color: Color with opacity notation (e.g., "soft black 25%")

BORDER PROPERTIES:
- has_border: true (only include if element HAS a border, omit if false)
- border_width_px: Pixel value
- border_style: "solid" | "dashed" | "dotted"
- border_color: Color reference

ELEMENT-SPECIFIC PROPERTIES:
- Images: object_fit ("cover" | "contain" | "fill")
- Containers: background_color
- Any element: rotation_degrees (omit if 0)

GRADIENT PROPERTIES (only if fill_type = "gradient"):
- gradient_type: "linear" | "radial"
- gradient_colors: ["color1", "color2", ...]
- gradient_direction: "top to bottom" | "left to right" | etc.

PATTERN PROPERTIES (only if fill_type = "pattern"):
- pattern_type: Description of pattern
- pattern_opacity_percent: 0-100

### Examples

Simple Text (no stroke, shadow, or border):
"visual": {{
  "fill_type": "solid",
  "fill_color": "pure white"
}}

Complex Shape (with stroke and shadow):
"visual": {{
  "fill_type": "solid",
  "fill_color": "bright cyan",
  "has_stroke": true,
  "stroke_color": "deep navy",
  "stroke_width_px": 3,
  "corner_style": "rounded",
  "corner_radius_px": 12,
  "has_shadow": true,
  "shadow_offset_x_px": 0,
  "shadow_offset_y_px": 4,
  "shadow_blur_px": 8,
  "shadow_color": "soft black 20%"
}}

Image with Mask:
"visual": {{
  "object_fit": "cover",
  "corner_style": "rounded",
  "corner_radius_px": 16
}}

### TOKEN OPTIMIZATION RULES

CRITICAL: Precision overrides brevity for spatial and typographic fields.
1. Do NOT omit quantitative layout values (position, size, gaps, rotation_degrees) even if they are 0.
2. ONLY include fields relevant to the specific element type (don't add stroke properties to elements without strokes)
3. Use compact representations for non-spatial visuals (e.g., "shadow_color: 'soft black 20%'" instead of separate opacity field)
4. Be comprehensive but concise: include every detail needed for recreation, nothing more

Goal: prioritize accuracy over token reduction when in conflict.

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

  "prompt_template": "YOUR TASK: Write a detailed natural language prompt here that describes the COMPLETE base template. This prompt will be given to an image generation AI. It must describe every element, its position, its styling, and its relationship to other elements and edges. Use palette references (primary/secondary/background) and only use color NAMES if they are clearly accurate; never use hex codes. Use explicit numeric sizes and placements (percent/px), and include rotation degrees where relevant. Add a clear instruction: 'Do not render numbers as text; numbers are layout constraints only.' Describe the full spatial extent of every element (where it starts AND ends in all directions), not just its starting position. If variation is allowed, include numeric ranges and say 'randomize within this range'. An artist reading this should be able to recreate the base template and its allowed variations.",

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
    "notes": "Technical values in design_system are for programmatic reference. The prompt_template uses palette references and only uses color names when they are clearly accurate."
  }},

  "variation_guidance": {{
    "randomness_level": 0.35,
    "layout_variation_percent": 15,
    "position_jitter_percent": 4,
    "scale_range_percent": [90, 110],
    "rotation_jitter_degrees": [-8, 8],
    "allowed_variations": [
      "Shuffle the relative placement of secondary elements while keeping primary hierarchy",
      "Vary spacing within the specified gap ranges",
      "Alternate between two tilt directions if specified"
    ],
    "non_negotiables": [
      "Keep required elements present",
      "Respect edge-touching elements as flush",
      "Do not violate minimum spacing rules"
    ]
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
4. **Write prompt_template** - use precise, LLM-optimized language with numeric layout constraints (percent/px and rotation degrees), and explicitly instruct not to render numbers as text
5. **Fill generation_instructions** - list required and forbidden elements
6. **Fill variation_guidance** - define allowable randomness ranges and non-negotiables

## ZERO AMBIGUITY RULE

Every description must be EXHAUSTIVELY SPECIFIC. An image generator should have ZERO questions. If there is ANY room for interpretation, you have FAILED.
- Do not hallucinate: omit details that are not clearly visible (e.g., tilt, extra icons, extra decorations).
- Specify exact counts and placements of repeated elements.
- Call out edge-touching elements explicitly (gap = 0 where relevant).
- If the layout is intentionally uneven or staggered, state that explicitly (do not imply uniform spacing).

**THE GOLDEN RULE**: After reading your output, an artist in a completely different country who has NEVER seen the original posts should be able to recreate the BASE TEMPLATE and apply the allowed variation ranges with 95%+ accuracy. If they would need to guess ANYTHING, your description is incomplete.

**SPATIAL COMPLETENESS**: For every element, describe its FULL extent in all directions - not just where it starts, but where it ends. State explicit boundaries: "extends from X to Y" or "fills the entire bottom third" or "occupies 50% width centered". Never describe only position without also describing complete coverage. If variation is allowed, give explicit min/max bounds.

**FOR EVERY ELEMENT YOU IDENTIFY, SPECIFY:**

  0. **Quantitative Metrics** (MANDATORY - never skip)
     - Exact width/height as % of canvas (and px if possible)
     - Exact x/y position as % of canvas
     - Rotation degrees (0 if none)
     - Text line height and letter spacing (if text)

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
- [ ] VISUAL TAXONOMY COMPLETE (token-optimized):
  - [ ] fill_type specified for shapes/containers/text
  - [ ] stroke properties specified ONLY if has_stroke: true
  - [ ] corner_style specified (omit radius if sharp/0)
  - [ ] shadow properties specified ONLY if has_shadow: true
  - [ ] border properties specified ONLY if has_border: true
  - [ ] element-specific properties (object_fit for images, background_color for containers)
  - [ ] gradient/pattern properties ONLY if relevant
- [ ] Overlap status specified (including "no overlap")
- [ ] Z-index/layer order specified if relevant

## FINAL CHECKLIST

Before submitting, verify ALL of the following:

**Core Requirements:**
- [ ] Based primarily on Post 1?
- [ ] Patterns validated across posts?
- [ ] Every color has `hex` AND `name`?
- [ ] prompt_template includes numeric layout constraints AND explicitly says not to render numbers as text?
- [ ] Every element passes the universal checklist above?
- [ ] Are gaps and edge contacts explicitly defined (no missing spacing)?
- [ ] Are counts of icons/decorations explicit with no duplicates added?
- [ ] `variation_guidance` includes numeric ranges and non-negotiables?

**New Section Requirements:**
- [ ] `image_sequence` filled out if post is a carousel (or `is_carousel: false` if single image)?
- [ ] `asset_recreation` includes generation instructions for EVERY photo, icon, and decoration?
- [ ] `placeholder_guidance` provides on-brand content suggestions for text, numbers, images, and dates?

**Zero Ambiguity Test:**
- [ ] Could an artist who has NEVER seen the original recreate the base template + variation ranges with 95%+ accuracy?
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

    if issues:
        print(f"Warning: prompt_template contains raw values: {', '.join(issues)}")
        print("  These may render as visible text. Avoid hex codes and use palette names instead.")
    if "do not render numbers" not in prompt.lower():
        print("Warning: prompt_template missing numeric constraint note (e.g., 'Do not render numbers as text').")


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


def detect_categories(posts):
    """
    Phase 1: Detect trend categories from posts.
    Returns category metadata including post assignments and universal elements.
    """
    # Prepare posts metadata - Post 1 is NEWEST
    posts_for_analysis = []
    for i, post in enumerate(posts, 1):
        post_data = {
            "post_number": i,
            "is_newest": i == 1,
            "url": post.get('url', 'N/A'),
            "caption": post.get('caption', 'N/A')[:200],  # First 200 chars
            "type": post.get('type', 'N/A'),
            "timestamp": post.get('timestamp', 'N/A')
        }
        posts_for_analysis.append(post_data)

    # Collect all image URLs
    image_urls = collect_image_urls(posts)
    print(f"Phase 1: Category Detection - Found {len(image_urls)} images across {len(posts)} posts")

    # Build multimodal content array
    content = []

    # Add the category detection prompt
    formatted_prompt = CATEGORY_DETECTION_PROMPT + "\n\nHere are the posts to analyze:\n" + json.dumps(posts_for_analysis, indent=2)
    content.append({
        "type": "text",
        "text": formatted_prompt
    })

    # Download and add images as base64 (use lower resolution for Phase 1 to save tokens)
    print("Downloading images for category detection...")
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
        raise Exception("No images could be downloaded for category detection")

    print("Sending posts to Gemini for category detection...")

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
                timeout=120
            )
            break
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"  API connection failed, retry {attempt + 1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise Exception(f"API connection failed after {max_retries} attempts: {e}")

    if response is None or response.status_code != 200:
        error_msg = response.text if response else "No response"
        raise Exception(f"OpenRouter API error: {error_msg}")

    response_data = response.json()
    category_text = response_data['choices'][0]['message']['content']

    print("Category detection complete!")

    # Clean up response - remove markdown if present
    category_text = category_text.strip()
    if category_text.startswith("```json"):
        category_text = category_text[7:]
    if category_text.startswith("```"):
        category_text = category_text[3:]
    if category_text.endswith("```"):
        category_text = category_text[:-3]
    category_text = category_text.strip()

    try:
        category_json = json.loads(category_text)
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse JSON response: {e}")
        print("Raw response:", category_text[:500])
        category_json = {
            "categories": [
                {
                    "category_id": "fallback_all_posts",
                    "category_name": "All Posts",
                    "category_description": "Failed to detect categories, treating all as one category",
                    "post_assignments": list(range(1, len(posts) + 1)),
                    "purpose": "mixed",
                    "purpose_correlation": "Failed to detect",
                    "color_palette_notes": "Unknown",
                    "logo_consistency": "Unknown"
                }
            ],
            "universal_elements": {
                "canvas_consistent": False,
                "logo_position_consistent": False,
                "fonts_consistent": False,
                "brand_colors_present": False
            }
        }

    return category_json


def filter_posts_by_category(posts, category_metadata):
    """Extract posts belonging to a specific category."""
    post_numbers = category_metadata['post_assignments']
    return [posts[i-1] for i in post_numbers]  # Convert 1-indexed to 0-indexed


def extract_universal_elements(category_data, category_analyses):
    """
    Identify elements that appear in ALL 5 posts (100% consistency).
    Extract: canvas dimensions, fonts, logo position, brand colors.
    """
    universal_elements = category_data.get('universal_elements', {})

    # Build comprehensive universal design elements section
    result = {
        "description": "Design elements that are CONSISTENT across ALL posts, regardless of category"
    }

    # Canvas
    if universal_elements.get('canvas_consistent'):
        canvas_dims = universal_elements.get('canvas_dimensions', {})
        result["canvas"] = {
            "width": canvas_dims.get('width', 1080),
            "height": canvas_dims.get('height', 1350),
            "aspect_ratio": canvas_dims.get('aspect_ratio', '4:5'),
            "note": "All posts use the same canvas dimensions"
        }
    else:
        result["canvas"] = {
            "consistent": False,
            "note": "Canvas dimensions vary across posts"
        }

    # Fonts
    if universal_elements.get('fonts_consistent'):
        result["fonts"] = {
            "consistent": True,
            "universal_fonts": universal_elements.get('universal_fonts', []),
            "note": "These fonts appear across all categories"
        }
    else:
        result["fonts"] = {
            "consistent": False,
            "note": "Font usage varies by category"
        }

    # Logo
    if universal_elements.get('logo_position_consistent'):
        result["logo"] = {
            "consistent_position": True,
            "universal_position": universal_elements.get('universal_logo_position', 'unknown'),
            "consistency_score": "ALWAYS (100%)",
            "note": f"Logo always appears in {universal_elements.get('universal_logo_position', 'unknown')} across all posts"
        }
    else:
        result["logo"] = {
            "consistent_position": False,
            "note": "Logo position varies by category (see per-category tracking)"
        }

    # Brand colors
    if universal_elements.get('brand_colors_present'):
        result["brand_colors"] = {
            "core_colors": universal_elements.get('core_brand_colors', []),
            "note": "These brand colors appear in every post, though usage varies by category"
        }
    else:
        result["brand_colors"] = {
            "note": "No consistent brand colors detected across all posts"
        }

    # Other universal elements (detected from category analyses)
    result["other_universal_elements"] = []
    result["note"] = "When generating new posts, ALWAYS include these universal elements unless specifically instructed otherwise"

    return result


def infer_cross_category_patterns(category_analyses):
    """
    Compare patterns across categories.
    Identifies: logo positions, font consistency, color palette strategies, carousel usage.
    """
    if not category_analyses:
        return {}

    # Analyze logo consistency across categories
    logo_positions = []
    for cat in category_analyses:
        logo_tracking = cat.get('consistency_tracking', {}).get('logo_placement', {})
        if logo_tracking.get('primary_position'):
            logo_positions.append(logo_tracking['primary_position'])

    unique_logo_positions = list(set(logo_positions))
    if len(unique_logo_positions) == 1:
        global_logo = f"CONSISTENT - logo always {unique_logo_positions[0]} across all posts"
    elif len(unique_logo_positions) <= 2:
        global_logo = f"MOSTLY CONSISTENT - logo typically in {' or '.join(unique_logo_positions)}"
    else:
        global_logo = f"VARIABLE - logo varies by category ({', '.join(unique_logo_positions)})"

    # Analyze font consistency
    all_fonts = set()
    for cat in category_analyses:
        design_system = cat.get('design_system', {})
        typography = design_system.get('typography', {})
        for text_style in typography.values():
            if isinstance(text_style, dict) and 'font_family' in text_style:
                all_fonts.add(text_style['font_family'])

    if len(all_fonts) > 0:
        font_consistency = f"CONSISTENT - {', '.join(sorted(all_fonts))} used across all categories"
    else:
        font_consistency = "Unknown - no font data available"

    # Analyze color palette strategy
    palette_notes = [cat.get('color_palette_notes', '') for cat in category_analyses]
    if any('multiple' in note.lower() for note in palette_notes):
        color_strategy = "Category-specific palettes with some categories using multiple palettes"
    elif len(set(palette_notes)) == 1:
        color_strategy = "Uniform color palette across all categories"
    else:
        color_strategy = "Category-specific palettes using universal brand colors"

    # Analyze carousel usage
    carousel_usage = []
    for cat in category_analyses:
        cat_name = cat.get('category_name', 'Unknown')
        image_sequence = cat.get('image_sequence', {})
        is_carousel = image_sequence.get('is_carousel', False)
        carousel_usage.append(f"{cat_name}: {'carousel' if is_carousel else 'single image'}")

    # Analyze canvas consistency
    canvas_sizes = set()
    for cat in category_analyses:
        canvas = cat.get('design_system', {}).get('canvas', {})
        if canvas:
            canvas_sizes.add(f"{canvas.get('width', 'unknown')}x{canvas.get('height', 'unknown')}")

    canvas_consistency = "CONSISTENT - All posts use same dimensions" if len(canvas_sizes) <= 1 else "VARIABLE - Multiple canvas sizes detected"

    return {
        "global_logo_consistency": global_logo,
        "font_consistency": font_consistency,
        "color_palette_strategy": color_strategy,
        "carousel_usage": ", ".join(carousel_usage) if carousel_usage else "No carousel data",
        "canvas_consistency": canvas_consistency
    }


def build_category_selector(category_data):
    """
    Extract keywords from category names/descriptions.
    Build matching rules for auto-selection during generation.
    """
    if 'categories' not in category_data:
        return {
            "available_categories": [],
            "selection_logic": {}
        }

    available_categories = [cat['category_id'] for cat in category_data['categories']]
    selection_logic = {}

    # Common keyword patterns for different purposes
    purpose_keywords = {
        "call_to_action": ["apply", "join", "recruit", "volunteer", "hiring", "position", "sign up", "register"],
        "announcement": ["deadline", "announcement", "reminder", "save the date", "upcoming", "launching", "new"],
        "storytelling": ["story", "impact", "event", "community", "volunteers", "testimonial", "experience"],
        "educational": ["learn", "guide", "how to", "tips", "tutorial", "facts", "information"],
        "testimonial": ["testimonial", "review", "feedback", "experience", "story", "success"],
        "behind_the_scenes": ["behind", "team", "process", "making", "work", "volunteers"],
        "product": ["product", "service", "feature", "offer", "sale", "discount", "pricing"]
    }

    for cat in category_data['categories']:
        cat_id = cat['category_id']
        cat_name = cat['category_name'].lower()
        cat_desc = cat['category_description'].lower()
        cat_purpose = cat.get('purpose', '').lower()

        # Extract keywords from category name and description
        keywords = []

        # Add purpose-specific keywords
        if cat_purpose in purpose_keywords:
            keywords.extend(purpose_keywords[cat_purpose])

        # Add keywords from category name (split by spaces and common separators)
        name_words = cat_name.replace('-', ' ').replace('_', ' ').split()
        keywords.extend([word for word in name_words if len(word) > 3])  # Words longer than 3 chars

        # Content indicators from description
        content_indicators = []
        if "gradient" in cat_desc:
            content_indicators.append("uses gradients or vibrant colors")
        if "photo" in cat_desc or "image" in cat_desc:
            content_indicators.append("features photographs or imagery")
        if "text" in cat_desc:
            content_indicators.append("text-heavy content")
        if "nature" in cat_desc or "landscape" in cat_desc:
            content_indicators.append("nature or landscape themes")

        selection_logic[cat_id] = {
            "keywords": list(set(keywords)),  # Remove duplicates
            "content_indicators": content_indicators,
            "purpose": cat_purpose
        }

    return {
        "available_categories": available_categories,
        "selection_logic": selection_logic
    }


def assemble_final_json(category_data, category_analyses, posts, instagram_profile):
    """
    Combine Phase 1 + Phase 2 results.
    Returns a tuple: (main_json, category_jsons_dict)
    - main_json: Contains organization info, metadata, universal elements, cross-category patterns
    - category_jsons_dict: {category_id: category_json} for each category
    """
    from datetime import datetime

    primary_category_id = category_data['categories'][0]['category_id'] if category_data['categories'] else None
    primary_category = category_data['categories'][0] if category_data['categories'] else None

    # Build recommendation reasoning
    recommendation_reasoning = "No categories detected"
    recommended_category_id = primary_category_id
    confidence = "none"

    if primary_category:
        confidence = "high"
        trend_types = [primary_category.get('trend_type_primary', '')]
        if primary_category.get('trend_types_secondary'):
            trend_types.extend(primary_category.get('trend_types_secondary', []))

        reasoning_parts = [
            f"Category: {primary_category.get('category_name', 'Unknown')}",
            f"Trend types: {', '.join([t for t in trend_types if t])}",
            f"Post 1 (newest) uses this style",
            f"Purpose: {primary_category.get('purpose', 'unknown')}"
        ]
        recommendation_reasoning = ". ".join(reasoning_parts) + "."

    # Check if there's a recommended_category from Phase 1
    if 'recommended_category' in category_data:
        rec = category_data['recommended_category']
        recommended_category_id = rec.get('category_id', primary_category_id)
        if rec.get('reasoning'):
            recommendation_reasoning = rec['reasoning']

    # Extract organization name from Instagram profile URL
    org_name = instagram_profile.rstrip('/').split('/')[-1].replace('_', ' ').title()

    # Build minimal main JSON with only essential generation info
    universal_elements = extract_universal_elements(category_data, category_analyses)

    main_json = {
        "organization_name": org_name,
        "generation_directives": {
            "follow_json_strictly": True,
            "ignore_model_defaults": True,
            "note": "Follow this JSON exactly. Ignore any default padding, layout heuristics, or prior restrictions that conflict with these rules."
        },
        "randomness": {
            "layout_variation_strength": 0.35,
            "random_seed": int(datetime.utcnow().timestamp())
        }
    }

    # Only include universal elements that are actually consistent and useful for generation
    if universal_elements.get('canvas', {}).get('width'):
        main_json['canvas'] = {
            "width": universal_elements['canvas']['width'],
            "height": universal_elements['canvas']['height'],
            "aspect_ratio": universal_elements['canvas']['aspect_ratio']
        }

    if universal_elements.get('fonts', {}).get('consistent') and universal_elements['fonts'].get('universal_fonts'):
        main_json['fonts'] = universal_elements['fonts']['universal_fonts']

    if universal_elements.get('logo', {}).get('consistent_position'):
        main_json['logo_position'] = universal_elements['logo']['universal_position']

    if universal_elements.get('brand_colors', {}).get('core_colors'):
        main_json['brand_colors'] = universal_elements['brand_colors']['core_colors']

    # Build category JSONs - one for each category
    category_jsons = {}
    for cat_analysis in category_analyses:
        category_id = cat_analysis.get('category_id', 'unknown')

        # Build category JSON with all design system details
        category_json = {
            "category_info": {
                "category_id": category_id,
                "category_name": cat_analysis.get('category_name', 'Unknown'),
                "category_description": cat_analysis.get('category_description', ''),
                "posts_included": cat_analysis.get('posts_included', []),
                "post_count": cat_analysis.get('post_count', 0)
            },
            "trend_classification": {
                "trend_type_primary": cat_analysis.get('trend_type_primary', 'unknown'),
                "trend_types_secondary": cat_analysis.get('trend_types_secondary', []),
                "trend_type_reasoning": cat_analysis.get('trend_type_reasoning', '')
            },
            "purpose_analysis": {
                "purpose": cat_analysis.get('purpose', 'unknown'),
                "purpose_correlation": cat_analysis.get('purpose_correlation', ''),
                "color_palette_notes": cat_analysis.get('color_palette_notes', '')
            },
            "consistency_tracking": cat_analysis.get('consistency_tracking', {}),
            "design_system": cat_analysis.get('design_system', {}),
            "brand_style": cat_analysis.get('brand_style', {}),
            "prompt_template": cat_analysis.get('prompt_template', ''),
            "generation_instructions": cat_analysis.get('generation_instructions', {}),
            "variation_guidance": cat_analysis.get('variation_guidance', {}),
            "image_sequence": cat_analysis.get('image_sequence', {}),
            "asset_recreation": cat_analysis.get('asset_recreation', {}),
            "placeholder_guidance": cat_analysis.get('placeholder_guidance', {})
        }

        category_jsons[category_id] = category_json

    return main_json, category_jsons


def analyze_category_with_gemini(posts, category_metadata):
    """
    Phase 2: Analyze a specific category's design system.
    Takes posts filtered to a single category and the category metadata from Phase 1.
    """
    category_id = category_metadata['category_id']
    category_name = category_metadata['category_name']
    category_description = category_metadata['category_description']

    print(f"Phase 2: Analyzing category '{category_name}' ({len(posts)} posts)...")

    # Prepare posts metadata
    posts_for_analysis = []
    for i, post in enumerate(posts, 1):
        post_data = {
            "post_number": i,
            "url": post.get('url', 'N/A'),
            "caption": post.get('caption', 'N/A'),
            "type": post.get('type', 'N/A'),
            "timestamp": post.get('timestamp', 'N/A')
        }
        posts_for_analysis.append(post_data)

    # Collect all image URLs for this category's posts
    image_urls = collect_image_urls(posts)
    print(f"  Found {len(image_urls)} images for this category")

    # Build multimodal content array
    content = []

    # Modify the ANALYSIS_PROMPT to include category context
    category_context = f"""
CATEGORY CONTEXT:
These posts belong to the "{category_name}" category.
Category description: {category_description}

Focus your analysis on the design patterns specific to this category.
"""

    formatted_prompt = category_context + "\n" + ANALYSIS_PROMPT.format(
        posts_data=json.dumps(posts_for_analysis, indent=2)
    )

    content.append({
        "type": "text",
        "text": formatted_prompt
    })

    # Download and add images as base64
    print("  Downloading images for analysis...")
    successful_images = 0
    for post_num, img_num, url in image_urls:
        base64_data, media_type = download_image_as_base64(url)

        if base64_data:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{base64_data}"
                }
            })
            successful_images += 1

    print(f"  Successfully downloaded {successful_images}/{len(image_urls)} images")

    if successful_images == 0:
        raise Exception(f"No images could be downloaded for category '{category_name}'")

    print(f"  Sending to Gemini for analysis...")

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
                timeout=120
            )
            break
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"    API connection failed, retry {attempt + 1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise Exception(f"API connection failed after {max_retries} attempts: {e}")

    if response is None or response.status_code != 200:
        error_msg = response.text if response else "No response"
        raise Exception(f"OpenRouter API error: {error_msg}")

    response_data = response.json()
    analysis_text = response_data['choices'][0]['message']['content']

    print(f"  Analysis complete for category '{category_name}'")

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
        print(f"  Warning: Could not parse JSON response: {e}")
        print("  Raw response:", analysis_text[:500])
        analysis_json = {"raw_analysis": analysis_text, "error": "Failed to parse JSON"}

    # Add category metadata to the analysis
    analysis_json['category_id'] = category_id
    analysis_json['category_name'] = category_name
    analysis_json['category_description'] = category_description
    analysis_json['posts_included'] = category_metadata.get('post_assignments', [])
    analysis_json['post_count'] = len(posts)
    analysis_json['purpose'] = category_metadata.get('purpose', 'unknown')
    analysis_json['purpose_correlation'] = category_metadata.get('purpose_correlation', 'Unknown')
    analysis_json['color_palette_notes'] = category_metadata.get('color_palette_notes', 'Unknown')

    # Add trend type classification
    analysis_json['trend_type_primary'] = category_metadata.get('trend_type_primary', 'unknown')
    analysis_json['trend_types_secondary'] = category_metadata.get('trend_types_secondary', [])
    analysis_json['trend_type_reasoning'] = category_metadata.get('trend_type_reasoning', '')

    # Add consistency tracking
    logo_consistency = category_metadata.get('logo_consistency', 'Unknown')
    if logo_consistency.startswith('ALWAYS'):
        consistency_score = "ALWAYS (100%)"
        variations = []
    elif logo_consistency.startswith('MOSTLY'):
        consistency_score = "MOSTLY (75%)"
        variations = [{"note": "Minor variations detected"}]
    else:
        consistency_score = "VARIABLE"
        variations = [{"note": "Logo position varies within this category"}]

    analysis_json['consistency_tracking'] = {
        "logo_placement": {
            "primary_position": category_metadata.get('logo_consistency', 'Unknown').split()[-1] if logo_consistency != 'VARIABLE' else 'varies',
            "consistency_score": consistency_score,
            "variations": variations
        },
        "color_scheme": {
            "consistent": 'multiple' not in category_metadata.get('color_palette_notes', '').lower(),
            "palette_variations": []
        }
    }

    return analysis_json


def analyze_posts_with_categories(posts, instagram_profile):
    """
    Full two-phase analysis with category detection and per-category analysis.
    1. Detect categories (Phase 1)
    2. Analyze each category in parallel (Phase 2)
    3. Assemble final JSON structure (split into main + category JSONs)

    Args:
        posts: List of Instagram posts to analyze
        instagram_profile: Instagram profile URL (e.g., "https://www.instagram.com/username/")

    Returns:
        Tuple of (main_json, category_jsons_dict)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    print("=" * 60)
    print("STARTING TWO-PHASE CATEGORY ANALYSIS")
    print("=" * 60)
    print()

    # Phase 1: Detect categories
    print("=" * 60)
    print("PHASE 1: CATEGORY DETECTION")
    print("=" * 60)
    category_data = detect_categories(posts)

    if 'categories' not in category_data or len(category_data['categories']) == 0:
        print("Warning: No categories detected, falling back to single analysis")
        # Fallback: analyze all posts as one category
        analysis = analyze_posts_with_gemini(posts)

        # Build fallback main JSON and category JSON (minimal structure)
        org_name = instagram_profile.rstrip('/').split('/')[-1].replace('_', ' ').title()
        universal_elements = extract_universal_elements(category_data, [analysis])

        main_json = {
            "organization_name": org_name
        }

        # Only include universal elements that are actually consistent
        if universal_elements.get('canvas', {}).get('width'):
            main_json['canvas'] = {
                "width": universal_elements['canvas']['width'],
                "height": universal_elements['canvas']['height'],
                "aspect_ratio": universal_elements['canvas']['aspect_ratio']
            }

        if universal_elements.get('fonts', {}).get('consistent') and universal_elements['fonts'].get('universal_fonts'):
            main_json['fonts'] = universal_elements['fonts']['universal_fonts']

        if universal_elements.get('logo', {}).get('consistent_position'):
            main_json['logo_position'] = universal_elements['logo']['universal_position']

        if universal_elements.get('brand_colors', {}).get('core_colors'):
            main_json['brand_colors'] = universal_elements['brand_colors']['core_colors']

        category_json = {
            "category_info": {
                "category_id": "fallback_single_category",
                "category_name": "All Posts",
                "category_description": "All posts analyzed as single category (fallback)",
                "posts_included": list(range(1, len(posts) + 1)),
                "post_count": len(posts)
            },
            "purpose_analysis": {
                "purpose": "mixed",
                "purpose_correlation": "N/A",
                "color_palette_notes": "N/A"
            },
            **{k: v for k, v in analysis.items() if k not in ['category_id', 'category_name', 'category_description', 'posts_included', 'post_count']}
        }

        return main_json, {"fallback_single_category": category_json}

    num_categories = len(category_data['categories'])
    print(f"\nDetected {num_categories} categories:")
    for cat in category_data['categories']:
        print(f"  - {cat['category_name']} ({len(cat.get('post_assignments', []))} posts)")
    print()

    # Phase 2: Analyze each category in parallel
    print("=" * 60)
    print("PHASE 2: PER-CATEGORY ANALYSIS (PARALLEL)")
    print("=" * 60)

    category_analyses = []

    # Use ThreadPoolExecutor for parallel API calls
    with ThreadPoolExecutor(max_workers=min(num_categories, 3)) as executor:  # Max 3 parallel requests
        future_to_category = {}

        for category_metadata in category_data['categories']:
            # Filter posts for this category
            category_posts = filter_posts_by_category(posts, category_metadata)

            # Submit analysis task
            future = executor.submit(analyze_category_with_gemini, category_posts, category_metadata)
            future_to_category[future] = category_metadata['category_name']

        # Collect results as they complete
        for future in as_completed(future_to_category):
            category_name = future_to_category[future]
            try:
                category_analysis = future.result()
                category_analyses.append(category_analysis)
                print(f"  [OK] Completed analysis for: {category_name}")
            except Exception as e:
                print(f"  [ERROR] Error analyzing category '{category_name}': {e}")
                # Add fallback empty analysis
                category_analyses.append({
                    "category_name": category_name,
                    "error": str(e),
                    "note": "Analysis failed for this category"
                })

    print()
    print(f"Completed analysis for {len(category_analyses)}/{num_categories} categories")
    print()

    # Phase 3: Assemble final JSON
    print("=" * 60)
    print("PHASE 3: ASSEMBLING FINAL RESULTS")
    print("=" * 60)

    main_json, category_jsons = assemble_final_json(category_data, category_analyses, posts, instagram_profile)

    print("[OK] Assembly complete!")
    print()
    print("=" * 60)
    print("TWO-PHASE ANALYSIS COMPLETE")
    print("=" * 60)

    return main_json, category_jsons


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
