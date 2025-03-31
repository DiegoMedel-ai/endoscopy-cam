from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from routes.video import video
from routes.gallery import gallery
from app_context import app

import os
import requests
from services.media_handler import MediaHandler

PROCEDURE_FOLDER = os.path.join(os.getcwd(), 'PROCEDURES')

media_handler = MediaHandler(PROCEDURE_FOLDER)

# Registrar los blueprints
app.register_blueprint(video, url_prefix='/video')
app.register_blueprint(gallery, url_prefix='/gallery')

CORS(app)
CORS(app, resources={r"/gallery/*": {"origins": "*"}})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_images', methods=['POST'])
def upload_images():
    data = request.get_json()
    folder = data.get('folder') # nombre del procedimiento  
    image_names = data.get('image_names', []) #nombres de las imgenes

    if not folder or not image_names:
        return jsonify({"message": "El nombre del procedimiento y las imágenes son requeridas."}), 400
    
    folder_path = os.path.join(PROCEDURE_FOLDER, folder) 

    if not os.path.exists(folder_path):
        return jsonify({"message": "El procedimiento no existe."}), 404

    decrypted_images = []
    
    for image_name in image_names:
        encrypted_filepath = os.path.join(folder_path, image_name)
        if not os.path.exists(encrypted_filepath):
            return jsonify({"message": f"La imagen {image_name} no existe."}), 404
        
        try:
            decrypted_data = media_handler.decrypt_file(encrypted_filepath)
            clean_name = image_name.replace(".enc", "") if image_name.endswith(".enc") else image_name
            decrypted_images.append((clean_name, decrypted_data))
        except Exception as e:
            print(f"Error al descifrar {image_name}: {e}")
            return jsonify({"message": f"Error al procesar {image_name}"}), 500
    
    if not decrypted_images:
        return jsonify({"message": "No se pudieron descifrar las imágenes."}), 404

    try:
        # Preparamos los archivos para enviar
        files = []
        for image_name, image_data in decrypted_images:
            files.append(('files', (image_name, image_data, 'image/jpeg')))

        # Configuramos la URL y headers
        url = 'https://69c7-187-189-148-91.ngrok-free.app/api/public-upload'
        headers = {
            'Authorization': 'Bearer token-secreto-torre-medica',  # Reemplaza con tu token real
        }

        # Enviamos la solicitud
        response = requests.post(url, files=files, headers=headers)
        response.raise_for_status()
        
        return jsonify({
            "message": "Las imágenes han sido enviadas exitosamente.",
            "response": response.json()
        }), 200

    except requests.exceptions.RequestException as e:
        print(f"Error al enviar las imágenes: {e}")
        return jsonify({
            "message": "Error al enviar las imágenes al servidor remoto.",
            "error": str(e)
        }), 500
        
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
