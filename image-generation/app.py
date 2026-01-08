import os
import re

from flask import Flask, render_template, request, jsonify, session, send_from_directory
from werkzeug.utils import secure_filename

import config
from services.replicate_generator import ImageGenerator
from services.replicate_editor import ReplicateImageEditor
from utils.image_utils import persist_data_url_image, is_data_url


def extract_user_prompt(full_prompt):
    """
    Extract the clean user instruction from technical prompt with region specifications.

    Examples:
    Input: 'IMPORTANT: ... Instruction: "Remove hearts". Do not modify...'
    Output: 'Remove hearts'

    Input: 'Generate a cat'
    Output: 'Generate a cat'
    """
    # Try to extract from 'Instruction: "..."' pattern
    match = re.search(r'Instruction:\s*["\']([^"\']+)["\']', full_prompt, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Try to extract from 'Instruction: ...' pattern (without quotes)
    match = re.search(r'Instruction:\s*(.+?)(?:\.|$)', full_prompt, re.IGNORECASE)
    if match:
        instruction = match.group(1).strip()
        # Remove trailing "Do not modify" clause if present
        instruction = re.sub(r'\s*Do not modify.*$', '', instruction, flags=re.IGNORECASE)
        return instruction.strip()

    # If no "Instruction:" pattern found, return the full prompt
    # (for simple prompts without region specifications)
    return full_prompt.strip()

app = Flask(__name__)
# Core Flask config and local upload limits.
app.secret_key = config.APP_SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER

# Replicate auth for the image generation workflow.
os.environ['REPLICATE_API_TOKEN'] = config.REPLICATE_API_TOKEN

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Service clients for generation and editing.
generator = ImageGenerator()
editor = ReplicateImageEditor()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/upload', methods=['POST'])
def upload():
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

        # Reset session state to anchor history on the uploaded image.
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
    data = request.json
    prompt = data.get('prompt')
    model = data.get('model', 'prunaai/p-image-edit')

    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    current_image_path = session.get('current_image_path')
    current_remote_url = session.get('current_remote_url')

    if 'history' not in session:
        session['history'] = []

    if 'total_cost' not in session:
        session['total_cost'] = 0.0

    try:
        input_image = current_remote_url if current_remote_url else current_image_path

        if input_image:
            # Route edits through Replicate using the selected model
            image_url, cost = editor.edit_image(prompt, input_image, model=model)
        else:
            cost = generator.calculate_cost(has_input_image=False)
            image_url = generator.generate_image(prompt)

        # Persist data URLs so we do not store large blobs in the session cookie.
        display_url = image_url
        remote_url = image_url
        local_path = None
        if is_data_url(image_url):
            local_path, display_url = persist_data_url_image(image_url, app.config['UPLOAD_FOLDER'])
            remote_url = None

        # Track per-request cost alongside the running total.
        session['total_cost'] += cost

        session['current_remote_url'] = remote_url
        session['current_image_path'] = local_path
        session['current_image_url'] = display_url

        # Extract clean user prompt for history (hide technical region specifications)
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
    return jsonify({
        'has_session': 'history' in session and len(session.get('history', [])) > 0,
        'image_url': session.get('current_image_url'),
        'history': session.get('history', []),
        'total_cost': session.get('total_cost', 0.0)
    })


@app.route('/reset', methods=['POST'])
def reset():
    session.clear()
    return jsonify({'success': True})


if __name__ == '__main__':
    # Use environment variable to control debug mode (default: False for production)
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5000))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
