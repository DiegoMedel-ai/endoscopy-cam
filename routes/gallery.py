from flask import Blueprint, render_template, send_file, abort, jsonify, request
import os
import locale
from datetime import datetime
from dotenv import load_dotenv
import io
import tempfile
from xhtml2pdf import pisa
from werkzeug.utils import secure_filename
from services.media_handler import MediaHandler

# Cargar variables de entorno
load_dotenv()

gallery = Blueprint('gallery', __name__)

# Ruta base de las imágenes
IMAGE_BASE_FOLDER = os.path.join(os.getcwd(), 'PROCEDURES')

media_handler = MediaHandler(IMAGE_BASE_FOLDER)

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
    encrypted_filename = filename if filename.endswith('.enc') else filename + '.enc'

    file_path = os.path.join(IMAGE_BASE_FOLDER, folder, encrypted_filename)

    if not os.path.exists(file_path):
        abort(404, description="Archivo no encontrado")

    # Determinar el tipo MIME según la extensión
    if filename.lower().endswith('.jpg'):
        mimetype = 'image/jpeg'
    elif filename.lower().endswith('.mp4'):
        mimetype = 'video/mp4'
    else:
        mimetype = 'application/octet-stream'

    if filename.endswith('.enc') or encrypted_filename.endswith('.enc'):
        try:
            # Crear archivo temporal
            temp_file = media_handler.decrypt_file(file_path)
            
            # Configurar respuesta para eliminar el temporal después
            response = send_file(temp_file, mimetype=mimetype)
            
            @response.call_on_close
            def remove_temp_file():
                try:
                    os.remove(temp_file)
                except Exception as e:
                    print(f"Error al eliminar archivo temporal {temp_file}: {e}")
            
            return response
        except Exception as e:
            print(f"Error al desencriptar {file_path}: {e}")
            abort(500, description="Error al procesar el archivo")
    else:
        # Si no está encriptado, servirlo directamente (modo compatibilidad)
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

    # Filtra las imágenes y videos encriptados (mostrar nombres sin .enc)
    image_files = [img.replace('.enc', '') for img in os.listdir(folder_path) if img.endswith('.jpg.enc')]
    video_files = [vid.replace('.enc', '') for vid in os.listdir(folder_path) if vid.endswith('.mp4.enc')]

    return jsonify({
        "folder": folder,
        "images": image_files,
        "videos": video_files
    })
    
@gallery.route('/take-photo', methods=['GET']) 
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
            if f.endswith('.jpg.enc')
        ], reverse=True)

        if not images:
            return jsonify({"error": "No hay imágenes en la carpeta"}), 404

        latest_image = images[0]
        image_path = os.path.join(folder_path, latest_image)

        # Desencriptar la imagen temporalmente
        temp_file = media_handler.decrypt_file(image_path)

        # Devolver tanto la imagen como los metadatos

        print(f"[INFO] Foto capturada: carpeta = {latest_folder}, archivo = {latest_image}")

        response = send_file(temp_file, mimetype='image/jpeg')
        response.headers['X-Folder-Name'] = latest_folder
        response.headers['X-File-Name'] = latest_image.replace('.enc', '')
        response.headers['Access-Control-Expose-Headers'] = 'X-Folder-Name, X-File-Name'
        response.headers['Content-Security-Policy'] = "default-src 'self'"
        response.headers['Access-Control-Allow-Origin'] = '*'
        # Configurar eliminación del archivo temporal después de enviar
        @response.call_on_close
        def remove_temp_file():
            try:
                os.remove(temp_file)
            except Exception as e:
                print(f"Error al eliminar archivo temporal {temp_file}: {e}")
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@gallery.route('/generar_pdf', methods=['POST'])
def generar_pdf():
    html_content = request.form.get('html')
    session_folder = request.form.get('session_folder')
    images = request.files.getlist('images')

    if not html_content or not session_folder:
        return jsonify({'error': 'Faltan parámetros requeridos'}), 400

    image_paths = []
    for img in images:
        filename = secure_filename(img.filename)
        # Buscar tanto la versión encriptada como la no encriptada
        encrypted_path = os.path.join(IMAGE_BASE_FOLDER, session_folder, filename + '.enc')
        normal_path = os.path.join(IMAGE_BASE_FOLDER, session_folder, filename)
        
        if os.path.exists(encrypted_path):
            # Desencriptar temporalmente para el PDF
            temp_file = media_handler.decrypt_file(encrypted_path)
            image_paths.append(temp_file)
        elif os.path.exists(normal_path):
            image_paths.append(normal_path)
        else:
            continue

    # Reemplazar referencias en el HTML
    for img_path in image_paths:
        filename = os.path.basename(img_path)
        html_content = html_content.replace(f"src=\"{filename}\"", f"src=\"file://{img_path}\"")

    pdf_path = os.path.join(IMAGE_BASE_FOLDER, session_folder, 'reporte.pdf')

    with open(pdf_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_file)

    # Limpiar archivos temporales
    for img_path in image_paths:
        if img_path.endswith('.temp'):
            try:
                os.remove(img_path)
            except:
                pass

    if pisa_status.err:
        return jsonify({'error': 'Error al generar el PDF'}), 500

    return jsonify({'pdf_path': pdf_path}), 200

@gallery.route('/delete-image', methods=['DELETE'])
def delete_image():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400

        folder = data.get('folder')
        filename = data.get('filename')
        
        if not folder or not filename:
            return jsonify({"error": "Faltan parámetros folder o filename"}), 400

        # Prevenir directory traversal
        if '../' in folder or '../' in filename:
            return jsonify({"error": "Ruta no permitida"}), 400

        # Buscar tanto el archivo encriptado como el normal
        encrypted_path = os.path.join(IMAGE_BASE_FOLDER, folder, filename + '.enc')
        normal_path = os.path.join(IMAGE_BASE_FOLDER, folder, filename)
        
        deleted_path = None
        if os.path.exists(encrypted_path):
            os.remove(encrypted_path)
            deleted_path = encrypted_path
        elif os.path.exists(normal_path):
            os.remove(normal_path)
            deleted_path = normal_path
        else:
            return jsonify({"error": "Archivo no encontrado"}), 404

        return jsonify({
            "success": True,
            "message": f"Imagen {filename} eliminada",
            "deleted_path": deleted_path
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500