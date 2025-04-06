from flask import Blueprint, render_template, send_file, abort, jsonify 
import os
import locale
from datetime import datetime
from dotenv import load_dotenv
import io

# Cargar variables de entorno
load_dotenv()

gallery = Blueprint('gallery', __name__)

# Ruta base de las imágenes
IMAGE_BASE_FOLDER = os.path.join(os.getcwd(), 'PROCEDURES')

def traducir_fecha(fecha_numerica):
    try:
        # Establecer el idioma español
        locale.setlocale(locale.LC_TIME, 'es_ES' if 'es_ES' in locale.locale_alias else 'es_MX.utf8')

        # Dividir en fecha y hora
        partes = fecha_numerica.split('-')
        fecha = datetime.strptime(partes[0], "%Y%m%d")
        
        if len(partes) > 1:
            hora = partes[1]  # HHMMSS
            return f"{fecha.strftime('%d de %B de %Y').lstrip('0').replace(' 0', ' ')} a las {hora[:2]}:{hora[2:4]}"
        else:
            return fecha.strftime("%d de %B de %Y").lstrip('0').replace(' 0', ' ')

    except ValueError as e:
        print(f"Error al convertir la fecha: {e}")
        return fecha_numerica


@gallery.route('/gallery')
def gallery_menu():
    # Listar todas las carpetas dentro de "images/"
    folders = [f for f in os.listdir(IMAGE_BASE_FOLDER) if os.path.isdir(os.path.join(IMAGE_BASE_FOLDER, f))]
    
    if not folders:
        return "No hay imágenes disponibles.", 404

    # Convertir los nombres de carpeta a fechas legibles
    translated_folders = [(folder, traducir_fecha(folder)) for folder in sorted(folders, reverse=True)]
    
    return render_template('gallery_menu.html', folders=translated_folders)


@gallery.route('/galleryMedApp')
def get_gallery():
    try:
        folders = [f for f in os.listdir(IMAGE_BASE_FOLDER) 
                  if os.path.isdir(os.path.join(IMAGE_BASE_FOLDER, f))]
        
        if not folders:
            return jsonify({"error": "No hay imágenes disponibles"}), 404
        
        translated_folders = [{
            "folder": folder,
            "fecha_legible": traducir_fecha(folder)
        } for folder in sorted(folders, reverse=True)]
        
        return jsonify(translated_folders)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@gallery.route('/gallery/<folder>')
def gallery_view(folder):
    # Asegurarse de que la carpeta existe
    folder_path = os.path.join(IMAGE_BASE_FOLDER, folder)
    if not os.path.exists(folder_path):
        return f"La carpeta {folder} no existe.", 404

    # Listar imágenes (ahora sin .enc)
    image_files = [img for img in os.listdir(folder_path) if img.endswith('.jpg')]

    # Crear rutas dinámicas para visualizar
    image_paths = [f"/procedures/{folder}/{img}" for img in image_files]

    return render_template('gallery.html', images=image_paths, folder=folder)


@gallery.route('/procedures/<folder>/<filename>')
def serve_media(folder, filename):
    """Devuelve el archivo multimedia (jpg o mp4) directamente"""
    file_path = os.path.join(IMAGE_BASE_FOLDER, folder, filename)

    if not os.path.exists(file_path):
        abort(404, description="Archivo no encontrado")

    # Determinar el tipo MIME según la extensión
    if filename.lower().endswith('.jpg'):
        mimetype = 'image/jpeg'
    elif filename.lower().endswith('.mp4'):
        mimetype = 'video/mp4'
    else:
        mimetype = 'application/octet-stream'

    return send_file(file_path, mimetype=mimetype)

@gallery.route('/folders', methods=['GET'])
def get_folders():
    try:
        # Listar todas las carpetas dentro de "PROCEDURES/"
        folders = [f for f in os.listdir(IMAGE_BASE_FOLDER) 
                  if os.path.isdir(os.path.join(IMAGE_BASE_FOLDER, f))]
        
        if not folders:
            return jsonify([])
        
        # Convertir los nombres de carpeta a fechas legibles
        translated_folders = [{
            "folder": folder,
            "fecha_legible": traducir_fecha(folder)
        } for folder in sorted(folders, reverse=True)]
        
        return jsonify(translated_folders)
    
    except Exception as e:
        print(f"Error al listar carpetas: {e}")
        return jsonify({"error": str(e)}), 500

@gallery.route('/api/<folder>', methods=['GET'])
def get_images_json(folder):
    folder_path = os.path.join(IMAGE_BASE_FOLDER, folder)

    if not os.path.exists(folder_path):
        return jsonify({"error": f"La carpeta {folder} no existe."}), 404

    # Filtra las imágenes y videos
    image_files = [img for img in os.listdir(folder_path) if img.endswith('.jpg')]
    video_files = [vid for vid in os.listdir(folder_path) if vid.endswith('.mp4')]

    return jsonify({
        "folder": folder,
        "images": image_files,
        "videos": video_files
    })
    
@gallery.route('/take-photo')
def take_last_photo():
    try:
        # Obtener la carpeta más reciente por fecha
        folders = sorted([
            f for f in os.listdir(IMAGE_BASE_FOLDER)
            if os.path.isdir(os.path.join(IMAGE_BASE_FOLDER, f))
        ], reverse=True)

        if not folders:
            return jsonify({"error": "No hay carpetas disponibles"}), 404

        latest_folder = folders[0]
        folder_path = os.path.join(IMAGE_BASE_FOLDER, latest_folder)

        # Obtener la imagen más reciente .jpg
        images = sorted([
            f for f in os.listdir(folder_path)
            if f.endswith('.jpg')
        ], reverse=True)

        if not images:
            return jsonify({"error": "No hay imágenes en la carpeta"}), 404

        latest_image = images[0]
        image_path = os.path.join(folder_path, latest_image)

        return send_file(image_path, mimetype='image/jpeg')

    except Exception as e:
        print(f"Error al obtener la última imagen: {e}")
        return jsonify({"error": str(e)}), 500
    
