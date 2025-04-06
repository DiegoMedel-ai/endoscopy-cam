from flask import Blueprint, jsonify, Response, request
import os
import eventlet
import threading
import time
from services.media_handler import MediaHandler
from dotenv import load_dotenv
from app_context import app

load_dotenv()
environment = os.getenv("environment", "dev")
recording_flag = threading.Event()
video = Blueprint('video', __name__)
PROCEDURE_FOLDER = os.path.join(os.getcwd(), 'PROCEDURES')
os.makedirs(PROCEDURE_FOLDER, exist_ok=True)

media_handler = MediaHandler(PROCEDURE_FOLDER)
transcription_log = []
# Inicia la captura de frames (esto llenará las colas para streaming y grabación)
eventlet.spawn(media_handler.capture_frames)

# Puedes mantener tu función find_capture_device() para otros usos, si es necesario.
# Si usas el método capture_frames() no es necesario pasar cap a generate().

@video.route('/video_feed')
def video_feed():
    return Response(media_handler.generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@video.route('/capture', methods=['POST'])
def capture():
    # if not recording_flag.is_set():
    #     return jsonify({"message": "No se está grabando. Inicie una grabación antes de capturar imágenes."}), 400

    try:
        frame = media_handler.latest_frame
        if frame is None:
            return jsonify({"message": "Aún no hay frames disponibles para capturar"}), 500

        filename, filepath = media_handler.save_snapshot(frame)
        print("📸 Imagen guardada como", filename)
        return jsonify({"message": f"Imagen guardada como {filename}", "path": filepath})

    except Exception as e:
        print("❌ Error al capturar imagen:", e)
        return jsonify({"message": "Error interno al capturar imagen"}), 500

@video.route('/start_recording', methods=['POST'])
def start_recording():
    print("✅ Entrando a start_recording", flush=True)
    if not recording_flag.is_set():
        try:
            print("🟢 Iniciando nueva sesión de grabación...", flush=True)
            media_handler.start_session()
            recording_flag.set()
            video_thread = eventlet.spawn(media_handler.record_video, recording_flag)
            print("🎥 Hilo de grabación lanzado correctamente", flush=True)
            return jsonify({"message": "Grabación iniciada."})
        except Exception as e:
            print("❌ Error al iniciar grabación:", e, flush=True)
            return jsonify({"error": str(e)}), 500
    print("⚠️ Ya hay una grabación en curso", flush=True)
    return jsonify({"message": "La grabación ya está en curso."})

@video.route('/stop_recording', methods=['POST'])
def stop_recording():
    if recording_flag.is_set():
        recording_flag.clear()
        time.sleep(0.5)  # Pequeña espera para asegurar el cierre

        # Guardar transcripción si existe
        if transcription_log:
            try:
                session_folder = media_handler.session_folder
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                txt_path = os.path.join(session_folder, f"transcripcion_{timestamp}.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write('\n'.join(transcription_log))
                print(f"📝 Transcripción guardada en: {txt_path}")
                transcription_log.clear()
            except Exception as e:
                print("❌ Error al guardar transcripción:", e)

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
    # Liberar la cámara si es necesario
    # cap.release()  # Si usas un objeto global, revisa este punto.
    return jsonify({"message": "Cámara liberada y aplicación cerrada."})
