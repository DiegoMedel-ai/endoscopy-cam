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
    
    folder_path = os.path.join(BASE_FOLDER, folder) 

    if not os.path.exists(folder_path):
        return jsonify({"message": "El procedimiento no existe."}), 404

    decrypted_images = [] # las voy a desencriptar pero las podemos enviar encriptadas
    #encrypted_images = [] # por si las queremos enviar encriptadas

    for image_name in image_names:
        encrypted_filepath = os.path.join(folder_path, image_name)
        if not os.path.exists(encrypted_filepath):
            return jsonify({"message": "La imagen no existe."}), 404
            continue
        
        try:
            decrypted_data = media_handler.decrypt_file(encrypted_filepath)
            decrypted_images.append(decrypted_data)

            #encriptadas
            #with open(encrypted_filepath, "rb") as encrypted_file:
            #    encrypted_data = encrypted_file.read()
            #encrypted_images.append((image_name, encrypted_data))

        except Exception as e:
            print(f"Error al descifrar {image_name}: {e}")
            continue
    
    if not decrypted_images:
        return jsonify({"message": "No se pudieron descifrar las imágenes."}), 404

    #if not encrypted_images:
    #    return jsonify({"message": "No se pudieron encriptar las imágenes."}), 404


    # con request ennviamos las imaganes al cielo

    try:
        files = []

        #for image_name, encrypted_data in encrypted_images:
        #    files.append(('images', (image_name, encrypted_data, 'application/octet-stream'))) #el application/octet-stream es para enviar los archicos .enc

        for image_name, decrypted_data in decrypted_images:
            files.append(('images', (image_name, decrypted_data, 'image/jpg')))

        response = requests.post('https://cielo.andresvalesverga', files=files)
        response.raise_for_status()
        return jsonify({"message": "Las imágenes han sido enviadas exitosamente."}), 200

    except requests.exceptions.RequestException as e:
        print(f"Error al enviar las mamalonas al cielo: {e}")
        return jsonify({"message": "Error al enviar las imagenes al cielo."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
