import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv('.env.local')

# Flask configuration
APP_SECRET_KEY = os.getenv('APP_SECRET_KEY')
if not APP_SECRET_KEY:
    print("ERROR: APP_SECRET_KEY is not set in .env.local")
    sys.exit(1)

MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
UPLOAD_FOLDER = 'uploads'

# Replicate API configuration
REPLICATE_API_TOKEN = os.getenv('REPLICATE_API_TOKEN')
if not REPLICATE_API_TOKEN:
    print("ERROR: REPLICATE_API_TOKEN is not set in .env.local")
    sys.exit(1)

# Cost estimation for Flux models
COST_PER_MEGAPIXEL_GO_FAST = 0.012
MEGAPIXELS_1024x1024 = 1.0
