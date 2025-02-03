from flask import Blueprint, jsonify, Response, request
import threading
import cv2
import os
from services.media_handler import MediaHandler

video = Blueprint('video', __name__)

# Configuración inicial
PROCEDURE_FOLDER = os.path.join(os.getcwd(), 'PROCEDURES')
os.makedirs(PROCEDURE_FOLDER, exist_ok=True)

media_handler = MediaHandler(PROCEDURE_FOLDER)
cap = cv2.VideoCapture(0)
recording_flag = threading.Event()

@video.route('/video_feed')
def video_feed():
    return Response(media_handler.generate(cap), mimetype='multipart/x-mixed-replace; boundary=frame')

@video.route('/capture', methods=['POST'])
def capture():
    if not recording_flag.is_set():
        return jsonify({"message": "No se está grabando. Inicie una grabación antes de capturar imágenes."}), 400

    ret, frame = cap.read()
    if not ret:
        return jsonify({"message": "Inicia una grabacion para capturar un video"}), 500

    filename, filepath = media_handler.save_snapshot(frame)
    return jsonify({"message": f"Imagen guardada como {filename}", "path": filepath})

@video.route('/start_recording', methods=['POST'])
def start_recording():
    if not recording_flag.is_set():
        media_handler.start_session()  # Inicia la sesión
        recording_flag.set()
        video_thread = threading.Thread(target=media_handler.record_video, args=(cap, recording_flag))
        video_thread.start()
        return jsonify({"message": "Grabación iniciada."})
    return jsonify({"message": "La grabación ya está en curso."})

@video.route('/stop_recording', methods=['POST'])
def stop_recording():
    if recording_flag.is_set():
        recording_flag.clear()
        return jsonify({"message": "Grabación detenida."})
    return jsonify({"message": "No hay grabación en curso."})

@video.route('/shutdown', methods=['POST'])
def shutdown():
    cap.release()
    return jsonify({"message": "Cámara liberada y aplicación cerrada."})
