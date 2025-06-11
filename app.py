import os
import time
import subprocess
from datetime import datetime
from threading import Lock

from flask import Flask, render_template, request, jsonify, render_template_string, redirect, url_for
from flask_cors import CORS

from routes.gallery import gallery
# from routes.audio import create_audio_blueprint
from routes.video import create_video_blueprint
from services.media_handler import MediaHandler
from app_context import app

# ✅ Habilita CORS completo
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# ✅ Configuraciones
PROCEDURE_FOLDER = os.path.join(os.getcwd(), 'PROCEDURES')
TMP_FOLDER = os.path.join(os.getcwd(), "tmp")
os.makedirs(TMP_FOLDER, exist_ok=True)

media_handler = MediaHandler(PROCEDURE_FOLDER)
audio_processing_lock = Lock()
transcription_log = []

# ✅ Blueprints
# audio_bp = create_audio_blueprint(media_handler)
video_bp = create_video_blueprint(media_handler)

app.register_blueprint(video_bp, url_prefix='/video')
app.register_blueprint(gallery, url_prefix='/gallery')
# app.register_blueprint(audio_bp, url_prefix='/audio')

INTERFACE = 'wlxa047d75c7b0a'  # Cambia a tu interfaz si es necesario

print("MAX_CONTENT_LENGTH:", app.config['MAX_CONTENT_LENGTH'])


# ----------------------------------------------------------
# FUNCIONES Y ENDPOINTS
# ----------------------------------------------------------

@app.route('/upload_images', methods=['POST', 'OPTIONS'])
def upload_images():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.get_json()
    folder = data.get('folder')
    image_names = data.get('image_names', [])

    if not folder or not image_names:
        return jsonify({"message": "Faltan datos."}), 400

    folder_path = os.path.join(PROCEDURE_FOLDER, folder)
    if not os.path.exists(folder_path):
        return jsonify({"message": "La carpeta no existe."}), 404

    decrypted_images = []
    for image_name in image_names:
        path = os.path.join(folder_path, image_name)
        if not os.path.exists(path):
            return jsonify({"message": f"No existe {image_name}"}), 404
        try:
            data = media_handler.decrypt_file(path)
            clean_name = image_name.replace(".enc", "") if image_name.endswith(".enc") else image_name
            decrypted_images.append((clean_name, data))
        except Exception as e:
            return jsonify({"message": f"Error con {image_name}: {e}"}), 500

    if not decrypted_images:
        return jsonify({"message": "No se pudo descifrar ninguna imagen."}), 400

    try:
        files = [('files', (name, data, 'image/jpeg')) for name, data in decrypted_images]
        url = 'https://69c7-187-189-148-91.ngrok-free.app/api/public-upload'
        headers = {'Authorization': 'Bearer token-secreto-torre-medica'}
        response = requests.post(url, files=files, headers=headers)
        response.raise_for_status()
        return jsonify({"message": "Imágenes enviadas", "response": response.json()}), 200
    except requests.RequestException as e:
        return jsonify({"message": "Error al enviar", "error": str(e)}), 500


@app.route('/upload_audio', methods=['POST', 'OPTIONS'])
def upload_audio():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    file = request.files.get('audio_file')
    if not file:
        return 'No audio file received', 400

    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    base = f"audio_{timestamp}"
    webm_path = os.path.join('AUDIO_OUTPUT', base + '.webm')
    mp3_path = os.path.join('AUDIO_OUTPUT', base + '.mp3')

    os.makedirs('AUDIO_OUTPUT', exist_ok=True)
    file.save(webm_path)

    try:
        subprocess.run([
            'ffmpeg', '-i', webm_path, '-vn',
            '-acodec', 'libmp3lame', '-q:a', '2', mp3_path
        ], check=True)
        return 'Audio convertido a MP3', 200
    except subprocess.CalledProcessError as e:
        return f'Error al convertir audio: {e}', 500

@app.route('/network')
def index():
    error_message = request.args.get('error')
    success_message = request.args.get('success')

    # Forzar escaneo de redes antes de listarlas
    subprocess.run(['nmcli', 'device', 'wifi', 'rescan', 'ifname', INTERFACE])

    try:
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'SSID', 'device', 'wifi', 'list', 'ifname', INTERFACE],
            capture_output=True, text=True, check=True
        )
        ssids = set(line.strip() for line in result.stdout.splitlines() if line.strip())
    except subprocess.CalledProcessError as e:
        ssids = []
        error_message = f"Error al escanear redes: {e.stderr}"

    return render_template_string('''
        <html>
        <head>
        <style>
        
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f0f0f0;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                }

                .form-container {
                    background-color: #ffffff;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                    width: 300px;
                }

                h2 {
                    text-align: center;
                    color: #333;
                }

                label {
                    display: block;
                    margin-bottom: 8px;
                    color: #555;
                }

                input[type="text"], input[type="password"] {
                    width: 100%;
                    padding: 10px;
                    margin-bottom: 15px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    font-size: 14px;
                }

                input[type="submit"] {
                    width: 100%;
                    background-color: #4CAF50;
                    color: white;
                    padding: 10px;
                    border: none;
                    border-radius: 4px;
                    font-size: 16px;
                    cursor: pointer;
                }

                input[type="submit"]:hover {
                    background-color: #45a049;
                }

                .footer {
                    text-align: center;
                    margin-top: 20px;
                    font-size: 12px;
                    color: #999;
                }

                .error {
                    color: red;
                    font-size: 14px;
                    margin-bottom: 15px;
                }

                .success {
                    color: green;
                    font-size: 14px;
                    margin-bottom: 15px;
                }
        </style>
        </head>
        <body>
            <div class="form-container">
                <h2>Conectar a la red</h2>
                {% if error_message %}
                    <div class="error">{{ error_message }}</div>
                {% elif success_message %}
                    <div class="success">{{ success_message }}</div>
                {% endif %}
                <form method="POST" action="/connect">
                    <label for="ssid">SSID (Nombre de la red):</label>
                    <select id="ssid" name="ssid" required>
                        <option value="">Seleccione una red</option>
                        {% for ssid in ssids %}
                            <option value="{{ ssid }}">{{ ssid }}</option>
                        {% endfor %}
                    </select>
                    <label for="password">Contraseña:</label>
                    <input type="password" id="password" name="password" required>
                    <input type="submit" value="Conectar">
                </form>
            </div>
        </body>
        </html>
    ''', error_message=error_message, success_message=success_message, ssids=ssids)

@app.route('/connect', methods=['POST'])
def connect():
    ssid = request.form['ssid']
    password = request.form['password']

    try:
        command = f'nmcli dev wifi connect "{ssid}" password "{password}" ifname "{INTERFACE}"'
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            # Reiniciar dispositivo tras conexión exitosa
            subprocess.run(['reboot'])
            return redirect(url_for('index', success=f'Conectado exitosamente a la red {ssid}'))
        else:
            return redirect(url_for('index', error=result.stderr))
    except Exception as e:
        return redirect(url_for('index', error=str(e)))


# ----------------------------------------------------------
# MAIN APP
# ----------------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
