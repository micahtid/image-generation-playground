"""
Unified Flask Application: Instagram Scraper + Image Generation
"""
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import requests

from flask import Flask, render_template, request, jsonify, session, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename

import config
from services.scraper import scrape_instagram_posts
from services.analyzer import analyze_posts_with_categories
from services.generator import (
    ImageGenerator, ImageEditor, 
    persist_data_url_image, is_data_url,
    select_category_for_generation
)


# =============================================================================
# Flask App Setup
# =============================================================================

app = Flask(__name__)
app.secret_key = config.APP_SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER

# Set Replicate API token
os.environ['REPLICATE_API_TOKEN'] = config.REPLICATE_API_TOKEN

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
config.DATA_DIR.mkdir(exist_ok=True)

# Service clients
generator = ImageGenerator()
editor = ImageEditor()


# =============================================================================
# Utility Functions
# =============================================================================

def extract_user_prompt(full_prompt):
    """Extract the clean user instruction from technical prompt with region specifications."""
    match = re.search(r'Instruction:\s*["\']([^"\']+)["\']', full_prompt, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    match = re.search(r'Instruction:\s*(.+?)(?:\.|$)', full_prompt, re.IGNORECASE)
    if match:
        instruction = match.group(1).strip()
        instruction = re.sub(r'\s*Do not modify.*$', '', instruction, flags=re.IGNORECASE)
        return instruction.strip()

    return full_prompt.strip()


def get_existing_handles():
    """Get list of existing Instagram handles from data directory."""
    handles = []
    if config.DATA_DIR.exists():
        for folder in config.DATA_DIR.iterdir():
            if folder.is_dir():
                raw_file = folder / 'raw.json'
                main_file = folder / 'main.json'
                
                # Count category files (any .json that's not raw.json or main.json)
                category_files = [f for f in folder.glob('*.json') 
                                 if f.name not in ['raw.json', 'main.json']]
                
                # Get last modified time
                last_modified = None
                if main_file.exists():
                    last_modified = datetime.fromtimestamp(main_file.stat().st_mtime)
                elif raw_file.exists():
                    last_modified = datetime.fromtimestamp(raw_file.stat().st_mtime)
                
                handles.append({
                    'name': folder.name,
                    'has_raw': raw_file.exists(),
                    'has_main': main_file.exists(),
                    'category_count': len(category_files),
                    'analysis_count': len(category_files),  # For backwards compat in template
                    'last_modified': last_modified.isoformat() if last_modified else None,
                    'last_modified_display': last_modified.strftime('%Y-%m-%d %H:%M') if last_modified else 'Never'
                })
    
    # Sort by last modified (newest first)
    handles.sort(key=lambda x: x['last_modified'] or '', reverse=True)
    return handles


def get_analysis_files(handle):
    """Get list of category files for a handle (main.json + category JSONs)."""
    handle_dir = config.DATA_DIR / handle
    if not handle_dir.exists():
        return []
    
    files = []
    
    # Always include main.json first if it exists
    main_file = handle_dir / 'main.json'
    if main_file.exists():
        files.append({
            'filename': 'main.json',
            'path': str(main_file),
            'is_main': True,
            'display_name': 'Universal Elements (main.json)'
        })
    
    # Add category files (any .json that's not raw.json or main.json)
    for f in handle_dir.glob('*.json'):
        if f.name not in ['raw.json', 'main.json']:
            category_id = f.stem
            files.append({
                'filename': f.name,
                'path': str(f),
                'is_main': False,
                'category_id': category_id,
                'display_name': f"Category: {category_id.replace('_', ' ').title()}"
            })
    
    return files


# =============================================================================
# Landing Page Routes
# =============================================================================

@app.route('/')
def index():
    """Landing page with handle selection."""
    handles = get_existing_handles()
    return render_template('index.html', handles=handles)


@app.route('/handles', methods=['GET'])
def list_handles():
    """API: Get list of existing handles."""
    handles = get_existing_handles()
    return jsonify({'handles': handles})


@app.route('/scrape', methods=['POST'])
def scrape():
    """Scrape Instagram posts for a handle."""
    data = request.json
    username = data.get('username', '').strip()
    
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    # Clean username (remove @ if present)
    username = username.lstrip('@')
    
    try:
        # Create handle directory
        handle_dir = config.DATA_DIR / username
        handle_dir.mkdir(parents=True, exist_ok=True)
        
        # Scrape posts
        posts = scrape_instagram_posts(username)
        
        # Save raw posts
        raw_file = handle_dir / 'raw.json'
        with open(raw_file, 'w', encoding='utf-8') as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)
        
        # Analyze posts
        analysis = analyze_posts_with_categories(posts)
        
        # Save main.json (universal elements + metadata)
        main_data = {
            'analysis_metadata': analysis.get('analysis_metadata', {}),
            'universal_design_elements': analysis.get('universal_design_elements', {}),
            'cross_category_patterns': analysis.get('cross_category_patterns', {}),
            'generation_category_selector': analysis.get('generation_category_selector', {}),
            'available_categories': [c.get('category_id', 'unknown') for c in analysis.get('categories', [])]
        }
        main_file = handle_dir / 'main.json'
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(main_data, f, indent=2, ensure_ascii=False)
        
        # Save per-category JSON files
        categories_saved = []
        for category in analysis.get('categories', []):
            category_id = category.get('category_id', 'unknown')
            category_file = handle_dir / f'{category_id}.json'
            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump(category, f, indent=2, ensure_ascii=False)
            categories_saved.append(category_id)
        
        return jsonify({
            'success': True,
            'handle': username,
            'posts_count': len(posts),
            'main_file': 'main.json',
            'category_files': categories_saved
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/analyze', methods=['POST'])
def analyze():
    """Regenerate analysis for an existing handle."""
    data = request.json
    username = data.get('username', '').strip()
    
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    handle_dir = config.DATA_DIR / username
    raw_file = handle_dir / 'raw.json'
    
    if not raw_file.exists():
        return jsonify({'error': 'No raw data found. Please scrape first.'}), 404
    
    try:
        # Load existing posts
        with open(raw_file, 'r', encoding='utf-8') as f:
            posts = json.load(f)
        
        # Analyze posts
        analysis = analyze_posts_with_categories(posts)
        
        # Save main.json (universal elements + metadata)
        main_data = {
            'analysis_metadata': analysis.get('analysis_metadata', {}),
            'universal_design_elements': analysis.get('universal_design_elements', {}),
            'cross_category_patterns': analysis.get('cross_category_patterns', {}),
            'generation_category_selector': analysis.get('generation_category_selector', {}),
            'available_categories': [c.get('category_id', 'unknown') for c in analysis.get('categories', [])]
        }
        main_file = handle_dir / 'main.json'
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(main_data, f, indent=2, ensure_ascii=False)
        
        # Save per-category JSON files
        categories_saved = []
        for category in analysis.get('categories', []):
            category_id = category.get('category_id', 'unknown')
            category_file = handle_dir / f'{category_id}.json'
            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump(category, f, indent=2, ensure_ascii=False)
            categories_saved.append(category_id)
        
        return jsonify({
            'success': True,
            'handle': username,
            'main_file': 'main.json',
            'category_files': categories_saved
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Generation Page Routes
# =============================================================================

@app.route('/generate/<handle>')
def generate_page(handle):
    """Generation page for a specific handle."""
    handle_dir = config.DATA_DIR / handle
    
    if not handle_dir.exists():
        return redirect(url_for('index'))
    
    analysis_files = get_analysis_files(handle)
    
    return render_template('generate.html', 
                         handle=handle, 
                         analysis_files=analysis_files)


@app.route('/analysis-files/<handle>', methods=['GET'])
def get_handle_analysis_files(handle):
    """API: Get analysis files for a handle."""
    analysis_files = get_analysis_files(handle)
    return jsonify({'files': analysis_files})


@app.route('/analysis-content/<handle>/<filename>', methods=['GET'])
def get_analysis_content(handle, filename):
    """API: Get content of a specific analysis file."""
    file_path = config.DATA_DIR / handle / filename
    
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        return jsonify(content)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/universal-elements/<handle>', methods=['GET'])
def get_universal_elements(handle):
    """API: Get universal design elements (main.json) for a handle."""
    main_file = config.DATA_DIR / handle / 'main.json'
    
    if not main_file.exists():
        return jsonify({'error': 'main.json not found. Please run analysis first.'}), 404
    
    try:
        with open(main_file, 'r', encoding='utf-8') as f:
            main_data = json.load(f)
        
        return jsonify(main_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Image Processing Routes
# =============================================================================

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded images."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/upload', methods=['POST'])
def upload():
    """Upload an image to the canvas."""
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400

    allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Only JPG, PNG, and WEBP images are allowed'}), 400

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Reset session state
        session.clear()
        session['history'] = [{
            'type': 'upload',
            'message': f'Uploaded {file.filename}'
        }]
        session['current_image_path'] = filepath
        session['current_image_url'] = f'/uploads/{filename}'
        session.modified = True

        return jsonify({
            'success': True,
            'image_url': f'/uploads/{filename}',
            'history': session['history']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/process', methods=['POST'])
def process():
    """Process image generation or editing."""
    data = request.json
    prompt = data.get('prompt')
    model = data.get('model', 'prunaai/p-image-edit')
    main_json = data.get('main_json')          # Universal elements (always sent)
    analysis_json = data.get('analysis_json')  # Selected category JSON

    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    current_image_path = session.get('current_image_path')
    current_remote_url = session.get('current_remote_url')

    if 'history' not in session:
        session['history'] = []

    if 'total_cost' not in session:
        session['total_cost'] = 0.0

    try:
        # Validate input image - prefer local file, reject stale remote URLs
        input_image = None
        
        # Check local path first (preferred)
        if current_image_path and os.path.exists(current_image_path):
            input_image = current_image_path
        # Remote URLs from Replicate expire quickly - don't use them
        # (Previous session data may have stale URLs)
        
        if input_image:
            # Edit existing image - NO JSONs passed, just the user prompt
            image_url, cost = editor.edit_image(prompt, input_image, model=model)
        else:
            # Generate new image - Include design context from JSONs
            generation_prompt = prompt
            
            # Build enhanced prompt with JSON context for initial generation
            if main_json or analysis_json:
                context_parts = []
                
                if main_json:
                    context_parts.append(f"Universal Design Elements:\n{json.dumps(main_json, indent=2)}")
                
                if analysis_json:
                    context_parts.append(f"Category Design System:\n{json.dumps(analysis_json, indent=2)}")
                
                if context_parts:
                    generation_prompt = f"{prompt}\n\n---\nDesign Context:\n" + "\n\n".join(context_parts)
            
            cost = generator.calculate_cost(has_input_image=False)
            image_url = generator.generate_image(generation_prompt)

        # Always persist images locally to avoid expired Replicate URLs
        display_url = image_url
        local_path = None
        
        if is_data_url(image_url):
            # Data URL - decode and save
            local_path, display_url = persist_data_url_image(image_url, app.config['UPLOAD_FOLDER'])
        elif image_url.startswith(('http://', 'https://')):
            # Remote URL - download and save locally to prevent expiration
            try:
                response = requests.get(image_url, timeout=30)
                response.raise_for_status()
                
                # Determine extension from content type
                content_type = response.headers.get('content-type', 'image/png')
                ext = '.png' if 'png' in content_type else '.jpg' if 'jpeg' in content_type or 'jpg' in content_type else '.webp'
                
                filename = f'generated_{uuid.uuid4().hex}{ext}'
                local_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                
                display_url = f'/uploads/{filename}'
            except Exception as e:
                print(f"Warning: Failed to download image: {e}")
                # Fall back to remote URL (may fail on subsequent edits)
                local_path = None
                display_url = image_url

        # Track cost
        session['total_cost'] += cost

        # Always use local path for subsequent edits (no more remote URLs)
        session['current_remote_url'] = None
        session['current_image_path'] = local_path
        session['current_image_url'] = display_url

        # Extract clean user prompt for history
        clean_user_prompt = extract_user_prompt(prompt)

        session['history'].append({
            'type': 'user',
            'message': clean_user_prompt
        })
        session.modified = True

        return jsonify({
            'success': True,
            'image_url': display_url,
            'history': session['history'],
            'total_cost': round(session['total_cost'], 4)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/state', methods=['GET'])
def get_state():
    """Get current session state."""
    return jsonify({
        'has_session': 'history' in session and len(session.get('history', [])) > 0,
        'image_url': session.get('current_image_url'),
        'history': session.get('history', []),
        'total_cost': session.get('total_cost', 0.0)
    })


@app.route('/reset', methods=['POST'])
def reset():
    """Reset the current session."""
    session.clear()
    return jsonify({'success': True})


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5000))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
