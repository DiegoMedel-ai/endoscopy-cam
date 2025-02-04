from flask import Blueprint, jsonify, Response, request
import threading
import cv2
import os
import time
from services.media_handler import MediaHandler
from dotenv import load_dotenv

load_dotenv()

# Configuración inicial
video = Blueprint('video', __name__)
PROCEDURE_FOLDER = os.path.join(os.getcwd(), 'PROCEDURES')
os.makedirs(PROCEDURE_FOLDER, exist_ok=True)

media_handler = MediaHandler(PROCEDURE_FOLDER)
cap = cv2.VideoCapture(0)
recording_flag = threading.Event()

environment = os.getenv("environment", "dev")

# Configuración del GPIO para el botón
if environment == "prod":
    import gpiod
    BUTTON_PIN = 70
    chip = gpiod.Chip('gpiochip0')
    button_line = chip.get_line(BUTTON_PIN)
    button_line.request(consumer="button", type=gpiod.LINE_REQ_DIR_IN)

button_pressed = False

# Función para leer el botón
def read_button():
    global button_pressed
    while True:
        if environment == "prod":
            button_state = button_line.get_value()
            if button_state == 0 and not button_pressed:
                button_pressed = True
                capture() 
            elif button_state == 1: 
                button_pressed = False
        time.sleep(0.1)

if environment == "prod":
    button_thread = threading.Thread(target=read_button)
    button_thread.daemon = True
    button_thread.start()

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
    if environment == "prod":
        button_line.release()
    return jsonify({"message": "Cámara liberada y aplicación cerrada."})