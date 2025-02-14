from flask import Blueprint, render_template, send_file, abort
import os
import locale
from datetime import datetime
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import io

# Cargar variables de entorno
load_dotenv()

gallery = Blueprint('gallery', __name__)

# Ruta base de las imágenes
IMAGE_BASE_FOLDER = os.path.join(os.getcwd(), 'PROCEDURES')

# Obtener la clave de cifrado desde las variables de entorno
SECRET_KEY = os.getenv("SECRET_KEY")

cipher = Fernet(SECRET_KEY.encode())

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


@gallery.route('/gallery/<folder>')
def gallery_view(folder):
    # Asegurarse de que la carpeta existe
    folder_path = os.path.join(IMAGE_BASE_FOLDER, folder)
    if not os.path.exists(folder_path):
        return f"La carpeta {folder} no existe.", 404

    # Listar imágenes encriptadas dentro de la carpeta
    image_files = [img for img in os.listdir(folder_path) if img.endswith('.jpg.enc')]

    # Crear rutas dinámicas para desencriptar y visualizar
    image_paths = [f"/procedures/{folder}/{img}" for img in image_files]

    return render_template('gallery.html', images=image_paths, folder=folder)


@gallery.route('/procedures/<folder>/<filename>')
def serve_encrypted_image(folder, filename):
    """Desencripta y devuelve la imagen para que pueda visualizarse en la galería."""
    file_path = os.path.join(IMAGE_BASE_FOLDER, folder, filename)

    if not os.path.exists(file_path):
        abort(404, description="Imagen no encontrada")

    try:
        with open(file_path, "rb") as encrypted_file:
            encrypted_data = encrypted_file.read()

        decrypted_data = cipher.decrypt(encrypted_data)

        return send_file(io.BytesIO(decrypted_data), mimetype='image/jpeg')

    except Exception as e:
        print(f"Error al desencriptar {filename}: {e}")
        abort(500, description="Error al procesar la imagen")
