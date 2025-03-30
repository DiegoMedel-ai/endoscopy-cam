import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from routes.video import transcription_log  # Importa el log compartido



from routes.video import video
from routes.gallery import gallery
from app_context import app

import os
import requests
import base64
import time
import subprocess
import whisper
from threading import Lock
from services.media_handler import MediaHandler

socketio = SocketIO(app, cors_allowed_origins="*")
model = whisper.load_model("base")  # O "tiny" si estás en hardware limitado
PROCEDURE_FOLDER = os.path.join(os.getcwd(), 'PROCEDURES')
media_handler = MediaHandler(PROCEDURE_FOLDER)
TMP_FOLDER = os.path.join(os.getcwd(), "tmp")
os.makedirs(TMP_FOLDER, exist_ok=True)
audio_processing_lock = Lock()
transcription_log = []

app.register_blueprint(video, url_prefix='/video')
app.register_blueprint(gallery, url_prefix='/gallery')
CORS(app)

def wait_until_file_stable(path, timeout=1.0, check_interval=0.1):
    last_size = -1
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(path):
            size = os.path.getsize(path)
            if size == last_size:
                return True
            last_size = size
        time.sleep(check_interval)
    return False

# @app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_images', methods=['POST'])
def upload_images():
    data = request.get_json()
    folder = data.get('folder') # nombre del procedimiento  
    image_names = data.get('image_names', []) #nombres de las imgenes

    if not folder or not image_names:
        return jsonify({"message": "El nombre del procedimiento y las imágenes son requeridas."}), 400
    
    folder_path = os.path.join(PROCEDURE_FOLDER, folder) 

    if not os.path.exists(folder_path):
        return jsonify({"message": "El procedimiento no existe."}), 404

    decrypted_images = []
    
    for image_name in image_names:
        encrypted_filepath = os.path.join(folder_path, image_name)
        if not os.path.exists(encrypted_filepath):
            return jsonify({"message": f"La imagen {image_name} no existe."}), 404
        
        try:
            decrypted_data = media_handler.decrypt_file(encrypted_filepath)
            clean_name = image_name.replace(".enc", "") if image_name.endswith(".enc") else image_name
            decrypted_images.append((clean_name, decrypted_data))
        except Exception as e:
            print(f"Error al descifrar {image_name}: {e}")
            return jsonify({"message": f"Error al procesar {image_name}"}), 500
    
    if not decrypted_images:
        return jsonify({"message": "No se pudieron descifrar las imágenes."}), 404

    try:
        # Preparamos los archivos para enviar
        files = []
        for image_name, image_data in decrypted_images:
            files.append(('files', (image_name, image_data, 'image/jpeg')))

        # Configuramos la URL y headers
        url = 'https://69c7-187-189-148-91.ngrok-free.app/api/public-upload'
        headers = {
            'Authorization': 'Bearer token-secreto-torre-medica',  # Reemplaza con tu token real
        }

        # Enviamos la solicitud
        response = requests.post(url, files=files, headers=headers)
        response.raise_for_status()
        
        return jsonify({
            "message": "Las imágenes han sido enviadas exitosamente.",
            "response": response.json()
        }), 200

    except requests.exceptions.RequestException as e:
        print(f"Error al enviar las imágenes: {e}")
        return jsonify({
            "message": "Error al enviar las imágenes al servidor remoto.",
            "error": str(e)
        }), 500
        
@socketio.on('connect')
def handle_connect():
    print("🟢 Cliente conectado vía WebSocket")

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    webm_path = None
    wav_path = None

    try:
        print("🔄 Recibiendo audio...")
        audio_base64 = data['audio'].split(',')[1]
        audio_bytes = base64.b64decode(audio_base64)
        print("Longitud de audio_bytes:", len(audio_bytes))

        timestamp = int(time.time() * 1000)
        webm_path = os.path.join('tmp', f"audio_{timestamp}.webm")
        with open(webm_path, 'wb') as f:
            f.write(audio_bytes)

        time.sleep(0.1)  # ⚠️ Esperar más tiempo ayuda

        if not os.path.exists(webm_path) or os.path.getsize(webm_path) < 10000:
            print(f"⚠️ Archivo {webm_path} inválido o muy pequeño. Se omitirá.")
            return

        print("Archivo temporal creado:", webm_path)

        # Convertir a WAV (usando ffmpeg)
        wav_path = webm_path.replace('.webm', '.wav')
        command = ['ffmpeg', '-loglevel', 'quiet', '-y', '-i', webm_path, '-ac', '1', '-ar', '16000', wav_path]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            print("❌ Error al convertir con ffmpeg:", result.stderr.decode())
            return

        print("✅ Conversión exitosa:", wav_path)

        print("🎧 Transcribiendo...")
        result = model.transcribe(wav_path, language="es")
        text = result['text'].strip()
        print("✅ Transcripción obtenida:", text)

        if text:
            emit('transcription', {'text': text})
            transcription_log.append(text)

    except Exception as e:
        print("❌ Error al procesar audio:", e)

    finally:
        for path in [webm_path, wav_path]:
            if path and os.path.exists(path):
                os.remove(path)
                print(f"🪩 Archivo temporal eliminado: {path}")




if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)

