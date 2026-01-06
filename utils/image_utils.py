import base64
import mimetypes
import os
import uuid


def image_file_to_data_url(image_path):
    # Convert a local image file into a base64 data URL for API uploads.
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = 'application/octet-stream'

    with open(image_path, 'rb') as image_file:
        encoded = base64.b64encode(image_file.read()).decode('utf-8')

    return f'data:{mime_type};base64,{encoded}'


def persist_data_url_image(data_url, upload_folder):
    # Persist large data URLs to disk to avoid oversized session cookies.
    header, encoded = data_url.split(',', 1)
    mime_type = header.split(';')[0].replace('data:', '') if 'data:' in header else 'image/png'
    extension = mimetypes.guess_extension(mime_type) or '.png'
    filename = f'replicate_edit_{uuid.uuid4().hex}{extension}'
    filepath = os.path.join(upload_folder, filename)

    with open(filepath, 'wb') as image_file:
        image_file.write(base64.b64decode(encoded))

    return filepath, f'/uploads/{filename}'


def is_data_url(value):
    return isinstance(value, str) and value.startswith('data:image/')
