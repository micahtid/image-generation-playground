# AI Content Pipeline

Tools for analyzing Instagram design patterns and generating on-brand images.

## Folders

### `instagram-scraper/`
Scrapes Instagram posts and extracts design patterns using AI.

**APIs Used:**
- **Apify** - Scrapes Instagram posts (images, captions, metadata)
- **OpenRouter → Gemini** - Analyzes design patterns from scraped images

**Output:** JSON design system with colors, typography, layout specs, and image generation prompts.

### `image-generation/`
Flask web app for generating and editing images using AI.

**APIs Used:**
- **Replicate** - Image generation (`flux-2-dev`) and editing (`p-image-edit`)

**Input:** Prompts (can use output from instagram-scraper as guidance)

## Workflow

```
Instagram Posts
      ↓
[instagram-scraper] → Apify API → OpenRouter/Gemini
      ↓
Design System JSON (colors, fonts, layout, prompt_template)
      ↓
[image-generation] → Replicate API
      ↓
Generated Images
```

## Setup

1. Create `.env.local` in the root with your API keys:
```env
APIFY_API_KEY=your_key
OPENROUTER_API_KEY=your_key
REPLICATE_API_TOKEN=your_token
APP_SECRET_KEY=your_secret
```

2. See individual folder READMEs for detailed setup instructions.
