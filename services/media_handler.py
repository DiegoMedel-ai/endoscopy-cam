import os
import time
import cv2
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import queue
import eventlet
import subprocess

load_dotenv()

def find_capture_device():
    for i in range(4):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            print(f"✅ Dispositivo de video encontrado en /dev/video{i}")
            return cap
    raise RuntimeError("❌ No se encontró una capturadora de video disponible.")

class MediaHandler:
    def __init__(self, base_folder):
        self.base_folder = base_folder
        self.session_folder = None
        self.latest_frame = None

        # Inicializar cámara
        self.cap = find_capture_device()

        # Cola para streaming (limitada) y para grabación (sin límite)
        self.stream_queue = queue.Queue(maxsize=10)
        self.record_queue = queue.Queue()

        # Clave secreta desde .env
        self.secret_key = os.getenv("SECRET_KEY")
        if not self.secret_key:
            raise ValueError("❌ SECRET_KEY no está definida en el entorno.")
        self.cipher = Fernet(self.secret_key.encode())

    def start_session(self):
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        self.session_folder = os.path.join(self.base_folder, timestamp)
        os.makedirs(self.session_folder, exist_ok=True)
        print("📁 Carpeta de sesión creada:", self.session_folder, flush=True)

    def capture_frames(self):
        print("🎥 Iniciando captura de frames...", flush=True)
        if not self.cap.isOpened():
            print("❌ No se pudo abrir la cámara en capture_frames", flush=True)
            return

        while True:
            ret, frame = self.cap.read()
            if not ret:
                continue

            if self.stream_queue.full():
                self.stream_queue.get()
            self.stream_queue.put(frame)

            self.record_queue.put(frame)
            self.latest_frame = frame.copy()

            eventlet.sleep(0.01)

    def generate(self):
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
        print("📹 Iniciando grabación con FFmpeg...", flush=True)
        process = None
        try:
            if self.session_folder is None:
                raise ValueError("Sesión no iniciada")

            video_filename = f"video_{time.strftime('%Y%m%d-%H%M%S')}.mp4"
            video_path = os.path.join(self.session_folder, video_filename)
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            resolution = f"{width}x{height}"
            print(f"🎯 Resolución detectada: {width}x{height}", flush=True)
            command = [
                'ffmpeg',
                '-y',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-s', resolution,
                '-pix_fmt', 'bgr24',
                '-r', '24',
                '-i', '-',
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-pix_fmt', 'yuv420p',
                '-profile:v', 'baseline',
                '-movflags', '+faststart',
                '-f', 'mp4',
                video_path
            ]

            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )

            frame_count = 0
            last_update = time.time()

            while recording_flag.is_set():
                if not self.record_queue.empty():
                    frame = self.record_queue.get()
                    try:
                        process.stdin.write(frame.tobytes())
                        frame_count += 1

                        if time.time() - last_update > 1.0:
                            print(f"🎞️ Frames grabados: {frame_count}", flush=True)
                            last_update = time.time()

                    except BrokenPipeError:
                        ffmpeg_error = process.stderr.read().decode('utf-8')
                        print(f"❌ FFmpeg falló: {ffmpeg_error}", flush=True)
                        raise RuntimeError(f"FFmpeg error: {ffmpeg_error}")
                else:
                    eventlet.sleep(0.01)

            print(f"🛑 Finalizando grabación ({frame_count} frames)...", flush=True)
            process.stdin.close()
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8')
                raise RuntimeError(f"❌ FFmpeg falló: {error_msg}")

            if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
                raise RuntimeError("❌ El archivo de video no se creó correctamente")

            print(f"✅ Video guardado: {video_path} ({os.path.getsize(video_path)/1024:.2f} KB)", flush=True)
            return video_path

        except Exception as e:
            print(f"❌ Error en grabación: {str(e)}", flush=True)
            if process and process.poll() is None:
                process.kill()
            raise
        finally:
            pass

    def save_snapshot(self, frame):
        if self.session_folder is None:
            raise ValueError("La sesión no ha sido iniciada. Llama a start_session() primero.")

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"snapshot_{timestamp}.jpg"
        path = os.path.join(self.session_folder, filename)
        cv2.imwrite(path, frame)

        return filename, path

    def save_audio(self, audio_path):
        if self.session_folder is None:
            raise ValueError("La sesión no ha sido iniciada. Llama a start_session() primero.")

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"audio_{timestamp}.mp3"
        output_path = os.path.join(self.session_folder, filename)
        os.rename(audio_path, output_path)

        with open(output_path, "rb") as f:
            encrypted_data = self.cipher.encrypt(f.read())

        encrypted_path = f"{output_path}.enc"
        with open(encrypted_path, "wb") as f:
            f.write(encrypted_data)

        os.remove(output_path)
        return filename + ".enc", encrypted_path
