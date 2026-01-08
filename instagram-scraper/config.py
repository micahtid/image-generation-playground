import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env.local in the root directory.
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env.local')

# API keys.
APIFY_API_KEY = os.getenv('APIFY_API_KEY')
if not APIFY_API_KEY:
    print('ERROR: APIFY_API_KEY is not set in .env.local')
    sys.exit(1)

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    print('ERROR: OPENROUTER_API_KEY is not set in .env.local')
    sys.exit(1)

# Instagram scraping settings
INSTAGRAM_PROFILE = "https://www.instagram.com/restoring_rainbows_official/"
MAX_POSTS = 5
MAX_IMAGES_PER_POST = 10

# Apify Actor ID (using the specific actor ID from the URL)
APIFY_ACTOR_ID = "shu8hvrXbJbY3Eb9W"

# OpenRouter settings
OPENROUTER_MODEL = "google/gemini-3-flash-preview"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Output settings
OUTPUT_DIR = Path(__file__).parent / "output"
