from flask import Flask, render_template, Response, request, jsonify
import cv2
import os
import time

app = Flask(__name__)
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

IMAGE_FOLDER = os.path.join(os.getcwd(), 'images')
os.makedirs(IMAGE_FOLDER, exist_ok=True)

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

@app.route('/shutdown', methods=['POST'])
def shutdown():
    cap.release()
    return jsonify({"message": "Cámara liberada y aplicación cerrada."})

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        cap.release()
