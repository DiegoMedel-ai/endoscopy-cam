from flask import Flask, render_template, Response, request, jsonify
import cv2
import os
import time
import threading

app = Flask(__name__)
cap = cv2.VideoCapture(0)

IMAGE_FOLDER = os.path.join(os.getcwd(), 'images')
VIDEO_FOLDER = os.path.join(os.getcwd(), 'videos') 
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)

recording = False
video_writer = None
video_thread = None


def generate():
    while True:
        ret, frame = cap.read()
        if ret:
            (flag, encodedImage) = cv2.imencode(".jpg", frame)
            if not flag:
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' +
                   bytearray(encodedImage) + b'\r\n')

def record_video():
    global recording, video_writer
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    video_path = os.path.join(VIDEO_FOLDER, f"video_{timestamp}.avi")
    
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    video_writer = cv2.VideoWriter(video_path, fourcc, 20.0, (640, 480))

    while recording:
        ret, frame = cap.read()
        if ret:
            video_writer.write(frame)

    video_writer.release()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/capture', methods=['POST'])
def capture():
    ret, frame = cap.read()
    
    if not ret:
        return jsonify({"message": "Error al capturar la imagen."}), 500
    
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f'snapshot_{timestamp}.jpg'
    filepath = os.path.join(IMAGE_FOLDER, filename)
    cv2.imwrite(filepath, frame)
    
    return jsonify({"message": f"Imagen guardada como {filename}", "path": filepath})

@app.route('/start_recording', methods=['POST'])
def start_recording():
    global recording, video_thread
    if not recording:
        recording = True
        video_thread = threading.Thread(target=record_video)
        video_thread.start()
        return jsonify({"message": "Grabación iniciada."})
    return jsonify({"message": "La grabación ya está en curso."})

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    global recording
    if recording:
        recording = False
        video_thread.join()
        return jsonify({"message": "Grabación detenida."})
    return jsonify({"message": "No hay grabación en curso."})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    cap.release()
    return jsonify({"message": "Cámara liberada y aplicación cerrada."})

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        cap.release()
