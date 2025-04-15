import eventlet
eventlet.monkey_patch()

import os
import threading
import time
import requests
from flask import Blueprint, jsonify, Response, request
from dotenv import load_dotenv

recording_flag = threading.Event()
load_dotenv()
environment = os.getenv("environment", "dev")

def create_video_blueprint(handler, socketio):
    video = Blueprint('video', __name__)

    # Inicia la captura de frames en segundo plano
    eventlet.spawn(handler.capture_frames)

    @video.route('/video_feed')
    def video_feed():
        return Response(handler.generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    @video.route('/capture', methods=['POST'])
    def capture():
        try:
            frame = handler.latest_frame
            if frame is None:
                return jsonify({"message": "Aún no hay frames disponibles para capturar"}), 500

            filename, filepath = handler.save_snapshot(frame)
            print("📸 Imagen guardada como", filename)
            return jsonify({"message": f"Imagen guardada como {filename}", "path": filepath})
        except Exception as e:
            print("❌ Error al capturar imagen:", e)
            return jsonify({"message": "Error interno al capturar imagen"}), 500

    @video.route('/start_recording', methods=['POST', 'OPTIONS'])
    def start_recording():
        print("✅ Entrando a start_recording", flush=True)

        if recording_flag.is_set():
            print("⚠️ Ya hay una grabación en curso", flush=True)
            return jsonify({
                "message": "La grabación ya está en curso.",
                "status": "warning"
            }), 409

        try:
            print("🟢 Iniciando nueva sesión de grabación...", flush=True)
            handler.record_queue.queue.clear()
            handler.start_session()

            if not handler.cap or not handler.cap.isOpened():
                raise RuntimeError("La cámara no está disponible")

            recording_flag.set()

            def safe_record():
                try:
                    handler.record_video(recording_flag)
                except Exception as e:
                    print(f"💥 Error en hilo de grabación: {str(e)}", flush=True)
                    recording_flag.clear()

            eventlet.spawn(safe_record)

            eventlet.sleep(0.1)
            if not recording_flag.is_set():
                raise RuntimeError("No se pudo iniciar la grabación")

            try:
                print("🎙️ Iniciando grabación de audio automáticamente...")
                audio_url = request.host_url.rstrip('/') + "/audio/record"
                response = requests.post(audio_url)
                print("🎤 Grabación de audio lanzada:", response.status_code)
            except Exception as e:
                print(f"❌ Error al iniciar audio automáticamente: {e}")

            return jsonify({
                "message": "Grabación iniciada correctamente",
                "status": "success"
            })

        except Exception as e:
            recording_flag.clear()
            print(f"❌ Error al iniciar grabación: {str(e)}", flush=True)
            return jsonify({
                "error": str(e),
                "message": "No se pudo iniciar la grabación",
                "status": "error"
            }), 500

    @video.route('/stop_recording', methods=['POST', 'OPTIONS'])
    def stop_recording():
        if recording_flag.is_set():
            recording_flag.clear()
            time.sleep(1)
            try:
                print("🛑 Deteniendo grabación de audio automáticamente...")
                audio_stop_url = request.host_url.rstrip('/') + "/audio/stop_recording"
                response = requests.post(audio_stop_url)
                print("🔇 Audio detenido:", response.status_code)
            except Exception as e:
                print(f"❌ Error al detener el audio:", e)

            return jsonify({
                "message": "Grabación detenida",
                "status": "success"
            })

        return jsonify({
            "message": "No hay grabación en curso",
            "status": "info"
        })

    @video.route('/shutdown', methods=['POST'])
    def shutdown():
        return jsonify({"message": "Cámara liberada y aplicación cerrada."})

    return video
