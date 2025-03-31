from flask import Blueprint, request, jsonify
import os
import base64
import time
from dotenv import load_dotenv
import subprocess

load_dotenv()

def create_audio_blueprint(procedure_folder, media_handler):
    audio = Blueprint('audio', __name__)

    # Variables globales accesibles en las rutas
    global PROCEDURE_FOLDER
    global handler
    PROCEDURE_FOLDER = procedure_folder
    handler = media_handler

    @audio.route('/upload', methods=['POST'])
    def upload_audio():
        try:
            data = request.json
            base64_audio = data.get("audio")

            if not base64_audio:
                return jsonify({"error": "No se recibió audio"}), 400

            if handler.session_folder is None:
                return jsonify({"error": "No hay sesión activa"}), 400

            # Eliminar encabezado del base64 si lo tiene
            if "," in base64_audio:
                base64_audio = base64_audio.split(",")[1]

            audio_bytes = base64.b64decode(base64_audio)

            timestamp = time.strftime("%Y%m%d-%H%M%S")
            raw_webm_path = os.path.join(handler.session_folder, f"audio_{timestamp}.webm")
            mp3_path = os.path.join(handler.session_folder, f"audio_{timestamp}.mp3")
            encrypted_path = f"{mp3_path}.enc"

            with open(raw_webm_path, "wb") as f:
                f.write(audio_bytes)

            # Convertir a mp3 usando FFmpeg
            result = subprocess.run([
                "ffmpeg", "-y", "-i", raw_webm_path, "-vn", "-acodec", "libmp3lame", mp3_path
            ], capture_output=True, text=True)

            if result.returncode != 0:
                print("❌ Error de FFmpeg:", result.stderr)
                return jsonify({"error": "Error al convertir a MP3"}), 500

            # Cifrar archivo MP3
            with open(mp3_path, "rb") as f:
                encrypted_data = handler.cipher.encrypt(f.read())
            with open(encrypted_path, "wb") as f:
                f.write(encrypted_data)

            # Eliminar temporales
            os.remove(mp3_path)
            os.remove(raw_webm_path)

            print(f"✅ Audio guardado en: {encrypted_path}")
            return jsonify({"message": "Audio recibido y guardado exitosamente", "path": encrypted_path})

        except Exception as e:
            print("❌ Error al procesar audio:", e)
            return jsonify({"error": str(e)}), 500

    return audio
