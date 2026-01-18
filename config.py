"""
Unified configuration for the Instagram Scraper + Image Generation app.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv('.env.local')

# =============================================================================
# API Keys
# =============================================================================

APIFY_API_KEY = os.getenv('APIFY_API_KEY')
if not APIFY_API_KEY:
    print('ERROR: APIFY_API_KEY is not set in .env.local')
    sys.exit(1)

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    print('ERROR: OPENROUTER_API_KEY is not set in .env.local')
    sys.exit(1)

REPLICATE_API_TOKEN = os.getenv('REPLICATE_API_TOKEN')
if not REPLICATE_API_TOKEN:
    print('ERROR: REPLICATE_API_TOKEN is not set in .env.local')
    sys.exit(1)

APP_SECRET_KEY = os.getenv('APP_SECRET_KEY')
if not APP_SECRET_KEY:
    print('ERROR: APP_SECRET_KEY is not set in .env.local')
    sys.exit(1)

# =============================================================================
# OpenRouter / Gemini Settings
# =============================================================================

OPENROUTER_MODEL = 'google/gemini-2.0-flash-001'
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'

# =============================================================================
# Apify Settings
# =============================================================================

APIFY_ACTOR_ID = 'shu8hvrXbJbY3Eb9W'
MAX_POSTS = 5
MAX_IMAGES_PER_POST = 10

# =============================================================================
# Flask Settings
# =============================================================================

MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
UPLOAD_FOLDER = 'uploads'

# =============================================================================
# Replicate Cost Settings
# =============================================================================

COST_PER_MEGAPIXEL_GO_FAST = 0.012
MEGAPIXELS_1024x1024 = 1.0

# =============================================================================
# Data Directory
# =============================================================================

ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / 'data'
