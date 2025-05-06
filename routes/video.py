import os
import threading
import time
from flask import Blueprint, jsonify, Response, request
from dotenv import load_dotenv

load_dotenv()
recording_flag = threading.Event()

import threading, time
from flask import Blueprint, jsonify, Response

def create_video_blueprint(handler):
    video = Blueprint('video', __name__)

    # 1) Captura de frames en hilo real
    threading.Thread(target=handler.capture_frames, daemon=True).start()

    @video.route('/video_feed')
    def video_feed():
        return Response(handler.generate(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
        return Response(handler.generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    @video.route('/capture', methods=['POST'])
    def capture():
        try:
            frame = handler.latest_frame
            if frame is None:
                return jsonify({"message": "Aún no hay frames disponibles para capturar"}), 500

            filename, filepath = handler.save_snapshot(frame)

            # Obtener la carpeta de la foto
            folder = os.path.basename(os.path.dirname(filepath))

            print(f"📸 Imagen guardada como {filename} en la carpeta {folder}")

            # Devolver nombre de la carpeta y el archivo
            return jsonify({
                "message": f"Imagen guardada como {filename}",
                "path": filepath,
                "folder": folder,
                "filename": filename
            })

        except Exception as e:
            print("❌ Error al capturar imagen:", e)
            return jsonify({"message": "Error interno al capturar imagen"}), 500
        

    @video.route('/start_recording', methods=['POST'])
    def start_recording():
        print("📡 Entrando a /start_recording", flush=True)
        if recording_flag.is_set():
            return jsonify({"message":"Grabación ya en curso","status":"warning"}), 409

        data = request.get_json()
        usuario = data.get('usuario', 'desconocido')
        print(f"👤 Usuario recibido: {usuario}", flush=True)
        handler.start_session(usuario)
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
