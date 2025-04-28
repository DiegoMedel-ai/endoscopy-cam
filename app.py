import os
import time
import subprocess
from datetime import datetime
from threading import Lock

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO

from routes.gallery import gallery
from routes.audio import create_audio_blueprint
from routes.video import create_video_blueprint
from services.media_handler import MediaHandler
from app_context import app

# ✅ Habilita CORS completo
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*")

# ✅ Configuraciones
PROCEDURE_FOLDER = os.path.join(os.getcwd(), 'PROCEDURES')
TMP_FOLDER = os.path.join(os.getcwd(), "tmp")
os.makedirs(TMP_FOLDER, exist_ok=True)

media_handler = MediaHandler(PROCEDURE_FOLDER)
audio_processing_lock = Lock()
transcription_log = []

# ✅ Blueprints
audio_bp = create_audio_blueprint(media_handler)
video_bp = create_video_blueprint(media_handler)

app.register_blueprint(video_bp, url_prefix='/video')
app.register_blueprint(gallery, url_prefix='/gallery')
app.register_blueprint(audio_bp, url_prefix='/audio')


# ----------------------------------------------------------
# FUNCIONES Y ENDPOINTS
# ----------------------------------------------------------

@app.route('/upload_images', methods=['POST', 'OPTIONS'])
def upload_images():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.get_json()
    folder = data.get('folder')
    image_names = data.get('image_names', [])

    if not folder or not image_names:
        return jsonify({"message": "Faltan datos."}), 400

    folder_path = os.path.join(PROCEDURE_FOLDER, folder)
    if not os.path.exists(folder_path):
        return jsonify({"message": "La carpeta no existe."}), 404

    decrypted_images = []
    for image_name in image_names:
        path = os.path.join(folder_path, image_name)
        if not os.path.exists(path):
            return jsonify({"message": f"No existe {image_name}"}), 404
        try:
            data = media_handler.decrypt_file(path)
            clean_name = image_name.replace(".enc", "") if image_name.endswith(".enc") else image_name
            decrypted_images.append((clean_name, data))
        except Exception as e:
            return jsonify({"message": f"Error con {image_name}: {e}"}), 500

    if not decrypted_images:
        return jsonify({"message": "No se pudo descifrar ninguna imagen."}), 400

    try:
        files = [('files', (name, data, 'image/jpeg')) for name, data in decrypted_images]
        url = 'https://69c7-187-189-148-91.ngrok-free.app/api/public-upload'
        headers = {'Authorization': 'Bearer token-secreto-torre-medica'}
        response = requests.post(url, files=files, headers=headers)
        response.raise_for_status()
        return jsonify({"message": "Imágenes enviadas", "response": response.json()}), 200
    except requests.RequestException as e:
        return jsonify({"message": "Error al enviar", "error": str(e)}), 500


@app.route('/upload_audio', methods=['POST', 'OPTIONS'])
def upload_audio():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    file = request.files.get('audio_file')
    if not file:
        return 'No audio file received', 400

    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    base = f"audio_{timestamp}"
    webm_path = os.path.join('AUDIO_OUTPUT', base + '.webm')
    mp3_path = os.path.join('AUDIO_OUTPUT', base + '.mp3')

    os.makedirs('AUDIO_OUTPUT', exist_ok=True)
    file.save(webm_path)

    try:
        subprocess.run([
            'ffmpeg', '-i', webm_path, '-vn',
            '-acodec', 'libmp3lame', '-q:a', '2', mp3_path
        ], check=True)
        return 'Audio convertido a MP3', 200
    except subprocess.CalledProcessError as e:
        return f'Error al convertir audio: {e}', 500


# ----------------------------------------------------------
# MAIN APP
# ----------------------------------------------------------
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
