# Image Editor

A Flask app that generates and edits images using Replicate's AI models.

## How it works

- **Generate**: if no image is loaded, the prompt is sent to `black-forest-labs/flux-2-dev` on Replicate.
- **Edit**: if an image is loaded, the prompt and image are sent to `prunaai/p-image-edit` on Replicate.
- **State**: the current image, prompt history, and total credits used are stored in the session.
- **Output**: data URL responses are persisted to `uploads/` so session cookies stay small.

## Setup

### 1. Clone and Navigate

```bash
git clone <your-repo-url>
cd playground
```

### 2. Environment Variables

Copy the example environment file and configure it:

```bash
cp .env.example .env.local
```

Edit `.env.local` with your actual values:

```env
# Replicate API Token for image generation and editing
REPLICATE_API_TOKEN=your_replicate_api_token_here

# Flask Application Secret Key
APP_SECRET_KEY=your_secure_random_secret_key_here

# Flask Debug Mode (false for production)
FLASK_DEBUG=false

# Server Port
PORT=5000
```

**Get your Replicate API token**: https://replicate.com/account/api-tokens

**Generate a secure secret key**:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

**Development mode:**
```bash
python app.py
```

**Production mode** (using gunicorn):
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

Then open `http://localhost:5000` in your browser.

## Project Layout

- `app.py`: Flask routes and session orchestration
- `config.py`: Loads environment variables and defines constants
- `services/replicate_generator.py`: Replicate generation client (flux-2-dev)
- `services/replicate_editor.py`: Replicate editing client (p-image-edit)
- `utils/image_utils.py`: Image data URL helpers and persistence
- `templates/index.html`: Single-page UI

## Cost Estimation

- **Generation** (flux-2-dev at 896x896): ~$0.0096 per image (~25% cheaper than 1024x1024)
- **Editing** (p-image-edit): $0.01 per image
- Costs are tracked per session and displayed in the UI

## Production Deployment

### Environment Variables

- Set `FLASK_DEBUG=false` in production
- Use a strong, unique `APP_SECRET_KEY`
- Never commit `.env.local` to version control

### Recommended Setup

1. Use a production WSGI server like **gunicorn** or **uwsgi**
2. Set up a reverse proxy (nginx/Apache)
3. Enable HTTPS with SSL certificates
4. Configure proper file upload limits
5. Set up log rotation for error logs

### Security Checklist

- ✅ API keys stored in environment variables
- ✅ `.env.local` excluded from git
- ✅ Debug mode disabled in production
- ✅ Secret key is cryptographically secure
- ✅ File upload validation enabled
- ✅ Maximum upload size enforced (16MB)

## Notes

- Never commit your `.env.local` file to version control
- Use a secure random value for `APP_SECRET_KEY` in production
- Uploaded images are stored in the `uploads/` directory
- The app validates environment variables on startup
