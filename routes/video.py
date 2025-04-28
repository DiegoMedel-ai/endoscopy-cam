import os
import threading
import time
from flask import Blueprint, jsonify, Response, request
from dotenv import load_dotenv

load_dotenv()
recording_flag = threading.Event()

import threading, time
from flask import Blueprint, jsonify, Response
# ya no necesitas eventlet aquí

def create_video_blueprint(handler):
    video = Blueprint('video', __name__)

    # 1) Captura de frames en hilo real
    threading.Thread(target=handler.capture_frames, daemon=True).start()

    @video.route('/video_feed')
    def video_feed():
        return Response(handler.generate(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    @video.route('/start_recording', methods=['POST'])
    def start_recording():
        print("📡 Entrando a /start_recording", flush=True)
        if recording_flag.is_set():
            return jsonify({"message":"Grabación ya en curso","status":"warning"}), 409

        handler.start_session()
        recording_flag.set()
        print("✅ recording_flag activado", flush=True)

        # 2) Record video en hilo real
        threading.Thread(target=handler.record_video,
                         args=(recording_flag,),
                         daemon=True).start()
        print("🎥 Hilo de grabación de video lanzado", flush=True)

        # 3) Record audio invoca su propio hilo
        handler.start_audio_recording()
        print("🎙️ Hilo de grabación de audio lanzado", flush=True)

        return jsonify({"message":"Grabación iniciada","status":"success"}), 200

    @video.route('/stop_recording', methods=['POST'])
    def stop_recording():
        print("🔵 Entró a /stop_recording", flush=True)
        if not recording_flag.is_set():
            return jsonify({"message":"No hay grabación activa","status":"info"}), 200

        recording_flag.clear()
        print("🛑 recording_flag desactivado", flush=True)

        # Detener audio
        handler.stop_audio_recording()
        print("✅ Audio detenido", flush=True)

        # Aquí podrías también unirte al hilo de video si quisieras
        # pero record_video deja de iterar cuando recording_flag.clear()

        # Transcripción y guardado
        transcription = handler.transcribe_audio()
        encrypted = handler.save_transcription(transcription)
        print("✅ Transcripción guardada", flush=True)

        return jsonify({
            "message":"Grabación detenida",
            "transcription": transcription,
            "transcription_file": os.path.basename(encrypted),
            "status":"success"}), 200

    return video

    @video.route('/shutdown', methods=['POST'])
    def shutdown():
        return jsonify({"message": "Cámara liberada y aplicación cerrada."})

    return video
