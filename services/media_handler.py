import os
import time
import cv2
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import queue

load_dotenv()

class MediaHandler:
    def __init__(self, base_folder):
        self.base_folder = base_folder
        self.session_folder = None

        self.frame_queue = queue.Queue(maxsize=10)

        # Obtener la clave de cifrado desde las variables de entorno
        self.secret_key = os.getenv("SECRET_KEY")
        
        self.cipher = Fernet(self.secret_key.encode())

    def start_session(self):

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        self.session_folder = os.path.join(self.base_folder, timestamp)
        os.makedirs(self.session_folder, exist_ok=True)

    def save_snapshot(self, frame):
 
        if self.session_folder is None:
            raise ValueError("La sesión no ha sido iniciada. Llama a start_session() antes de guardar snapshots.")
        
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"Imagen_{timestamp}.jpg"
        filepath = os.path.join(self.session_folder, filename)

        cv2.imwrite(filepath, frame)

        # Leer la imagen y cifrarla
        with open(filepath, "rb") as file:
            encrypted_data = self.cipher.encrypt(file.read())

        # Guardar el archivo cifrado con extension enc
        encrypted_filepath = f"{filepath}.enc"
        with open(encrypted_filepath, "wb") as encrypted_file:
            encrypted_file.write(encrypted_data)

        os.remove(filepath)

        return filename + ".enc", encrypted_filepath

    def decrypt_file(self, encrypted_filepath):
        """Descifra un archivo encriptado"""
        with open(encrypted_filepath, "rb") as encrypted_file:
            encrypted_data = encrypted_file.read()
        
        decrypted_data = self.cipher.decrypt(encrypted_data)
        return decrypted_data

    def generate(self, cap):
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            if not self.frame_queue.full():
                self.frame_queue.put(frame)

            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    def record_video(self, cap, recording_flag):
        if self.session_folder is None:
            raise ValueError("La sesión no ha sido iniciada. Llama a start_session() antes de grabar video.")

        video_filename = f"video_{time.strftime('%Y%m%d-%H%M%S')}.avi"
        video_path = os.path.join(self.session_folder, video_filename)

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        video_writer = cv2.VideoWriter(video_path, fourcc, 20.0, (640, 480))

        while recording_flag.is_set():
            if not self.frame_queue.empty():
                frame = self.frame_queue.get()
                video_writer.write(frame)

        video_writer.release()

        with open(video_path, "rb") as video_file:
            encrypted_data = self.cipher.encrypt(video_file.read())

        encrypted_video_path = f"{video_path}.enc"
        with open(encrypted_video_path, "wb") as encrypted_file:
            encrypted_file.write(encrypted_data)

        os.remove(video_path)

        return encrypted_video_path