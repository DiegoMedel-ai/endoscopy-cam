from flask import Flask, render_template, Response, request, jsonify
import cv2
import os
import time

app = Flask(__name__)

IMAGE_FOLDER = os.path.join(os.getcwd(), 'images')
if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER, exist_ok=True)

def gen_frames():
    # Inicializar la capturadora dentro de la función
    camera = cv2.VideoCapture('/dev/video1', cv2.CAP_V4L2)
    
    if not camera.isOpened():
        print("Error: No se pudo abrir la capturadora de video.")
        return

    while True:
        success, frame = camera.read()
        if not success:
            print("Error al leer el frame.")
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    camera.release()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/capture', methods=['POST'])
def capture():
    camera = cv2.VideoCapture('/dev/video1', cv2.CAP_V4L2)
    
    if not camera.isOpened():
        return jsonify({"message": "Error al abrir la capturadora de video."}), 500
    
    success, frame = camera.read()
    if success:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f'snapshot_{timestamp}.jpg'
        filepath = os.path.join(IMAGE_FOLDER, filename)
        cv2.imwrite(filepath, frame)
        camera.release()
        return jsonify({"message": f"Imagen guardada como {filename}"})
    else:
        camera.release()
        return jsonify({"message": "Error al capturar la imagen"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
