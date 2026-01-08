# Instagram Design Pattern Analyzer

Scrapes Instagram posts and uses AI (Gemini) to extract comprehensive design systems for image generation.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure API keys in `.env.local` (root directory):
   - `APIFY_API_KEY` - [Get from Apify](https://console.apify.com/account/integrations)
   - `OPENROUTER_API_KEY` - [Get from OpenRouter](https://openrouter.ai/keys)

## Usage

```bash
python main.py
```

**What it does:**
1. Scrapes 5 posts from the configured Instagram account via Apify
2. Downloads up to 10 images per post
3. Sends images + metadata to Gemini for design analysis
4. Saves results to `output/`

## Configuration

Edit `config.py`:
- `INSTAGRAM_PROFILE` - Account to scrape
- `MAX_POSTS` - Number of posts (default: 5)
- `MAX_IMAGES_PER_POST` - Images per post (default: 10)

## Output JSON Structure

The analyzer produces a comprehensive JSON with:

| Section | Purpose |
|---------|---------|
| `design_system` | Colors, typography, elements, layout specs |
| `brand_style` | Mood, keywords, things to avoid |
| `prompt_template` | Natural language prompt for image generators |
| `generation_instructions` | Required/forbidden elements |
| `image_sequence` | Carousel slide-by-slide direction (thumbnail vs content slides) |
| `asset_recreation` | Instructions for recreating photos, icons, decorations |
| `placeholder_guidance` | On-brand content suggestions for text, numbers, images |

## Key Features

- **Pattern Validation**: Uses Post 1 (newest) as primary reference, validates against Posts 2-5
- **Zero Ambiguity**: Every element has explicit position, spacing, and styling
- **Carousel Support**: Different direction for thumbnail vs. content slides
- **Asset Recreation**: Detailed instructions for generating supporting visuals
- **Placeholder Content**: Brand-aligned suggestions for headlines, stats, and imagery

## Files

- `main.py` - Orchestration
- `apify_scraper.py` - Instagram scraping via Apify
- `gemini_analyzer.py` - Design analysis via Gemini (contains the analysis prompt)
- `config.py` - Configuration
