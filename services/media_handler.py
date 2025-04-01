import os
import time
import cv2
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import queue
import eventlet

load_dotenv()

def find_capture_device():
    for i in range(4):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            print(f"Dispositivo de video encontrado en /dev/video{i}")
            return cap
    raise RuntimeError("No se encontró una capturadora de video disponible.")

class MediaHandler:
    def __init__(self, base_folder):
        self.base_folder = base_folder
        self.session_folder = None
        self.latest_frame = None

        # Cola para streaming (limitada) y para grabación (sin límite)
        self.stream_queue = queue.Queue(maxsize=10)
        self.record_queue = queue.Queue()  # Cola sin límite

        # Obtener la clave de cifrado desde las variables de entorno
        self.secret_key = os.getenv("SECRET_KEY")
        self.cipher = Fernet(self.secret_key.encode())

    def start_session(self):
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        self.session_folder = os.path.join(self.base_folder, timestamp)
        os.makedirs(self.session_folder, exist_ok=True)
        print("✅ Carpeta de sesión creada:", self.session_folder, flush=True)

    def capture_frames(self):
        """
        Abre la cámara y lee frames continuamente.
        Cada frame se duplica en dos colas:
          - self.stream_queue para streaming (limitada).
          - self.record_queue para grabación (sin límite).
        """
        print("🎥 Iniciando captura de frames...", flush=True)
        cap = find_capture_device()
        if not cap.isOpened():
            print("❌ No se pudo abrir la cámara en capture_frames", flush=True)
            return

        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            # Para streaming: si la cola está llena, descarta el frame más antiguo
            if self.stream_queue.full():
                _ = self.stream_queue.get()
                # print("🗑️ Se descartó un frame en stream_queue", flush=True)
            self.stream_queue.put(frame)
            # print("Frame agregado a stream_queue, tamaño:", self.stream_queue.qsize(), flush=True)

            # Para grabación: usa una cola sin límite para conservar todos los frames
            self.record_queue.put(frame)
            self.latest_frame = frame.copy()  # Mantener una copia del último frame

            eventlet.sleep(0.01)
        # cap.release()  # No se alcanza porque el bucle es infinito

    def generate(self):
        """
        Endpoint de streaming: extrae frames de la cola de streaming y los entrega en formato JPEG.
        """
        while True:
            if not self.stream_queue.empty():
                frame = self.stream_queue.get()
                ret, buffer = cv2.imencode('.jpg', frame)
                if not ret:
                    continue
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            else:
                eventlet.sleep(0.01)

    def record_video(self, recording_flag):
        """
        Consume frames de la cola de grabación mientras recording_flag esté activo,
        graba el video, lo cifra y lo guarda.
        """
        print("📹 Entrando a record_video()", flush=True)
        try:
            if self.session_folder is None:
                raise ValueError("La sesión no ha sido iniciada. Llama a start_session() antes de grabar video.")
            
            print("📁 Carpeta de sesión:", self.session_folder, flush=True)
            
            video_filename = f"video_{time.strftime('%Y%m%d-%H%M%S')}.avi"
            video_path = os.path.join(self.session_folder, video_filename)
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            video_writer = cv2.VideoWriter(video_path, fourcc, 20.0, (640, 480))
            
            frame_count = 0
            print("⏺️ Iniciando grabación desde record_queue...", flush=True)

            while recording_flag.is_set():
                if not self.record_queue.empty():
                    frame = self.record_queue.get()
                    video_writer.write(frame)
                    frame_count += 1
                    if frame_count % 30 == 0:
                        print(f"🎞️ Grabando... frame {frame_count}", flush=True)
                else:
                    eventlet.sleep(0.01)  # Evita bloquear el CPU

            print(f"🛑 Deteniendo grabación... Frames grabados: {frame_count}", flush=True)
            video_writer.release()

            print("🔒 Cifrando video...", flush=True)
            with open(video_path, "rb") as video_file:
                encrypted_data = self.cipher.encrypt(video_file.read())
            encrypted_video_path = f"{video_path}.enc"
            with open(encrypted_video_path, "wb") as encrypted_file:
                encrypted_file.write(encrypted_data)
            os.remove(video_path)

            print(f"✅ Video cifrado y guardado en: {encrypted_video_path}", flush=True)
            return encrypted_video_path

        except Exception as e:
            print("❌ Error en record_video():", e, flush=True)

    def save_snapshot(self, frame):
        """
        Guarda una imagen del frame proporcionado, la cifra y la guarda en la carpeta de sesión.
        Retorna el nombre y la ruta del archivo encriptado.
        """
        if self.session_folder is None:
            raise ValueError("La sesión no ha sido iniciada. Llama a start_session() primero.")

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"snapshot_{timestamp}.jpg"
        path = os.path.join(self.session_folder, filename)

        # Guardar imagen temporal
        cv2.imwrite(path, frame)

        # Leer y cifrar la imagen
        with open(path, "rb") as f:
            encrypted_data = self.cipher.encrypt(f.read())

        encrypted_path = f"{path}.enc"
        with open(encrypted_path, "wb") as f:
            f.write(encrypted_data)

        os.remove(path)  # Eliminar imagen original no cifrada

        return filename + ".enc", encrypted_path

def save_audio(self, audio_path):
    """
    Cifra un archivo de audio y lo guarda en la carpeta de sesión.
    Elimina el archivo original después de cifrarlo.
    """
    if self.session_folder is None:
        raise ValueError("La sesión no ha sido iniciada. Llama a start_session() primero.")

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"audio_{timestamp}.mp3"
    output_path = os.path.join(self.session_folder, filename)

    # Renombrar el archivo temporal al definitivo
    os.rename(audio_path, output_path)

    # Leer y cifrar el archivo de audio
    with open(output_path, "rb") as f:
        encrypted_data = self.cipher.encrypt(f.read())

    encrypted_path = f"{output_path}.enc"
    with open(encrypted_path, "wb") as f:
        f.write(encrypted_data)

    os.remove(output_path)  # Eliminar archivo original no cifrado

    return filename + ".enc", encrypted_path
