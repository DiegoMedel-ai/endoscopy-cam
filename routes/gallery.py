from flask import Blueprint, render_template, send_from_directory
import os,locale
from datetime import datetime

gallery = Blueprint('gallery', __name__)

# Ruta base de las imágenes
IMAGE_BASE_FOLDER = os.path.join(os.getcwd(), 'PROCEDURES')

def traducir_fecha(fecha_numerica):
    try:
        # Establecer el idioma español
        locale.setlocale(locale.LC_TIME, 'es_ES' if 'es_ES' in locale.locale_alias else 'es_MX.utf8')

        # Imprimir diagnóstico
        print(f"Procesando: {fecha_numerica}")

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
    valor = traducir_fecha(folders[0])
    print(valor)
    # Convertir los nombres de carpeta a fechas legibles
    translated_folders = [(folder, traducir_fecha(folder)) for folder in sorted(folders, reverse=True)]
    
    return render_template('gallery_menu.html', folders=translated_folders)


@gallery.route('/gallery/<folder>')
def gallery_view(folder):
    # Asegurarse de que la carpeta existe
    folder_path = os.path.join(IMAGE_BASE_FOLDER, folder)
    if not os.path.exists(folder_path):
        return f"La carpeta {folder} no existe.", 404

    # Listar imágenes dentro de la carpeta seleccionada y construir rutas dinámicas
    image_files = [f"{folder}/{img}" for img in os.listdir(folder_path) if img.endswith(('.jpg', '.png', '.jpeg'))]
    return render_template('gallery.html', images=image_files, folder=folder)



@gallery.route('/procedures/<path:filename>')
def serve_procedure_image(filename):
    return send_from_directory(IMAGE_BASE_FOLDER, filename)

