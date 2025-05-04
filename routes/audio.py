import os
from flask import Blueprint, jsonify
from dotenv import load_dotenv

load_dotenv()

def create_audio_blueprint(handler):
    audio = Blueprint('audio', __name__)

    @audio.route('/audio/start', methods=['POST'])
    def start_audio():
        print("📡 Entrando a /audio/start", flush=True)
        try:
            if handler.session_folder is None:
                print("📂 No hay sesión activa, creando nueva sesión...", flush=True)
                handler.start_session()
                print("📂 Carpeta de sesión creada", flush=True)

            print("🎙️ Iniciando grabación de audio...", flush=True)
            handler.start_audio_recording()
            print("✅ Grabación de audio iniciada correctamente", flush=True)

            return jsonify({"message": "Grabación de audio iniciada", "status": "success"})

        except Exception as e:
            print(f"❌ Error al iniciar grabación de audio: {e}", flush=True)
            return jsonify({"error": str(e), "status": "error"}), 500


    @audio.route('/audio/stop', methods=['POST'])
    def stop_audio():
        print("📡 Entrando a /audio/stop", flush=True)
        try:
            print("🛑 Deteniendo grabación de audio...", flush=True)
            handler.stop_audio_recording()
            print("✅ Grabación de audio detenida correctamente", flush=True)

            return jsonify({"message": "Grabación de audio detenida", "status": "success"})

        except Exception as e:
            print(f"❌ Error al detener grabación de audio: {e}", flush=True)
            return jsonify({"error": str(e), "status": "error"}), 500


    @audio.route('/audio/transcribe', methods=['GET'])
    def transcribe_audio():
        print("📡 Entrando a /audio/transcribe", flush=True)
        try:
            print("🧠 Transcribiendo audio...", flush=True)
            text = handler.transcribe_audio()
            print("✅ Transcripción completa obtenida", flush=True)

            return jsonify({"transcription": text, "status": "success"})

        except Exception as e:
            print(f"❌ Error al transcribir audio: {e}", flush=True)
            return jsonify({"error": str(e), "status": "error"}), 500


    return audio
