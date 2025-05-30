import os
import time
import threading
import subprocess
import wave
import json
import queue
import pyaudio
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"
import cv2
from cryptography.fernet import Fernet
from vosk import Model, KaldiRecognizer
from dotenv import load_dotenv
import tempfile

load_dotenv()

_capture_device = False  # Variable global para almacenar el dispositivo de captura

def find_capture_device():
    global _capture_device
    if _capture_device is not False:
        print("⚠️ Dispositivo de captura ya inicializado. Reutilizando...", flush=True)
        return _capture_device

    for i in range(4):
        cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
        if cap.isOpened():
            print(f"Dispositivo de video encontrado en /dev/video{i}", flush=True)
            _capture_device = True  # Almacena el dispositivo para reutilizarlo
            return cap
    raise RuntimeError("No se encontró una capturadora de video disponible.")


def warmup_camera(cap, warmup_frames=60):  # prueba con 60
    print("⏳ Esperando a que la cámara se estabilice...")
    for i in range(warmup_frames):
        ret, frame = cap.read()
        if not ret:
            print(f"Frame {i} no válido")
        else:
            print(f"Frame {i} OK")
        time.sleep(0.1)  # más delay, le das más chance al driver
    print("✅ Cámara estabilizada.")


class MediaHandler:
    def __init__(self, base_folder, is_for_image=False):
        self.base_folder = base_folder
        self.session_folder = None
        self.video_process = None
        self.audio_green_thread = None
        self.audio_stop_event = None
        self.audio_path = None
        self.record_queue = queue.Queue()
        self.stream_queue = queue.Queue(maxsize=10)
        self.latest_frame = None

        self.secret_key = os.getenv("SECRET_KEY")
        if not self.secret_key:
            raise ValueError("SECRET_KEY no está definida en el entorno.")
        self.cipher = Fernet(self.secret_key.encode())

        model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vosk-model-small-es-0.42"))
        self.model = Model(model_path)

        if not is_for_image:
            self.cap = find_capture_device()
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            warmup_camera(self.cap)
            print("✅ Dispositivo de captura de video inicializado correctamente", flush=True)

    def start_session(self,usuario=None):
        if usuario == None:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            self.session_folder = os.path.join(self.base_folder, timestamp)
        else:
            self.session_folder = os.path.join(self.base_folder, usuario+"_"+time.strftime("%Y%m%d-%H%M%S"))
        os.makedirs(self.session_folder, exist_ok=True)
        print(f"Carpeta de sesión creada: {self.session_folder}", flush=True)

    def start_audio_recording(self):
        print("🎙️ Iniciando start_audio_recording()", flush=True)

        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        CHUNK = 1024

        # Preparamos ruta de salida
        audio_filename = f"audio_{time.strftime('%Y%m%d-%H%M%S')}.wav"
        self.audio_path = os.path.join(self.session_folder, audio_filename)
        print(f"🎙️ Archivo de audio: {self.audio_path}", flush=True)

        audio_interface = pyaudio.PyAudio()

        try:
            # Abrimos el stream (bloqueante) pero NO en el event loop
            audio_stream = audio_interface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            print("✅ Stream de audio abierto", flush=True)

            # Esta función SÍ correrá en un hilo OS real
            def record_audio():
                print("🎙️ Empezando a grabar audio...", flush=True)
                with wave.open(self.audio_path, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(audio_interface.get_sample_size(FORMAT))
                    wf.setframerate(RATE)

                    # Este loop puede bloquear en .read(), pero SOLO dentro de este hilo
                    while not self.audio_stop_event.is_set():
                        try:
                            data = audio_stream.read(CHUNK, exception_on_overflow=False)
                            wf.writeframes(data)
                        except Exception as e:
                            print(f"⚠️ Error leyendo audio: {e}", flush=True)
                            break

                print("🛑 Cerrando stream de audio...", flush=True)
                audio_stream.stop_stream()
                audio_stream.close()
                audio_interface.terminate()
                print(f"✅ Audio guardado en: {self.audio_path}", flush=True)

            # Creamos el Event para poder parar este hilo
            self.audio_stop_event = threading.Event()

            self.audio_thread = threading.Thread(target=record_audio, daemon=True)
            self.audio_thread.start()
            print("✅ Hilo real de grabación de audio lanzado", flush=True)

        except Exception as e:
            print(f"❌ Error en start_audio_recording: {e}", flush=True)
            audio_interface.terminate()


    def stop_audio_recording(self):
        print("🛑 Entrando a stop_audio_recording()", flush=True)
        if hasattr(self, 'audio_thread') and self.audio_thread.is_alive():
            self.audio_stop_event.set()
            self.audio_thread.join()  # Espera a que el hilo termine
            print("✅ Audio detenido correctamente", flush=True)
        else:
            print("⚠️ No hay hilo de audio activo o ya terminó", flush=True)


    def record_video(self, recording_flag):
        print("🎥 Iniciando record_video()", flush=True)
        width = 640
        height = 480
        resolution = f"{width}x{height}"

        video_filename = f"video_{time.strftime('%Y%m%d-%H%M%S')}.mp4"
        video_path = os.path.join(self.session_folder, video_filename)
        print(f"🎥 Archivo de video: {video_path}", flush=True)

        command = [
            'ffmpeg',
            '-y',
            '-f', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', resolution,
            '-r', '24',
            '-i', '-',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-pix_fmt', 'yuv420p',
            '-profile:v', 'baseline',
            '-movflags', '+faststart',
            '-loglevel', 'error',
            video_path
        ]

        self.video_process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("✅ FFmpeg lanzado", flush=True)

        frame_count = 0
        try:
            while recording_flag.is_set() or not self.record_queue.empty():
                if not self.record_queue.empty():
                    frame = self.record_queue.get()
                    try:
                        self.video_process.stdin.write(frame.tobytes())
                        frame_count += 1
                        if frame_count % 30 == 0:
                            print(f"🎞️ Frames grabados: {frame_count}", flush=True)
                    except Exception as e:
                        print(f"❌ Error escribiendo frame: {e}", flush=True)
                        break
                else:
                    time.sleep(0.01)

            print(f"🛑 Finalizando grabación de video ({frame_count} frames)...", flush=True)
            try:
                self.video_process.stdin.close()
            except Exception:
                pass

            self.video_process.wait(timeout=10)
            print(f"✅ FFmpeg finalizado con código {self.video_process.returncode}", flush=True)
            
            # Encriptar el video después de grabarlo
            encrypted_path = self.encrypt_file(video_path)
            print(f"✅ Video encriptado guardado en: {encrypted_path}", flush=True)
            
        except Exception as e:
            print(f"❌ Error en grabación de video: {e}", flush=True)
            if self.video_process:
                self.video_process.kill()

        finally:
            self.video_process = None

    def capture_frames(self):
        print("🎥 Iniciando captura de frames...", flush=True)
        if not self.cap.isOpened():
            print("❌ No se pudo abrir la cámara.", flush=True)
            return

        # Define la resolución máxima permitida
        max_width = 640
        max_height = 480

        while True:
            ret, frame = self.cap.read()
            if not ret:
                continue

            # Redimensionar si es necesario
            height, width = frame.shape[:2]
            if width > max_width or height > max_height:
                frame = cv2.resize(frame, (max_width, max_height), interpolation=cv2.INTER_AREA)

            if self.stream_queue.full():
                self.stream_queue.get()
            self.stream_queue.put(frame)
            self.record_queue.put(frame)
            self.latest_frame = frame.copy()

            time.sleep(0.01)

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
                time.sleep(0.01)

    def transcribe_audio(self):
        print("🧠 Iniciando transcripción de audio...", flush=True)
        if not self.audio_path or not os.path.exists(self.audio_path):
            raise FileNotFoundError("❌ No se encontró el archivo de audio para transcribir.")

        wf = wave.open(self.audio_path, "rb")
        rec = KaldiRecognizer(self.model, wf.getframerate())
        text = ""

        # Leemos chunks y vamos imprimiendo cada fragmento reconocido
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                chunk = result.get("text", "").strip()
                if chunk:
                    print(f"🗣️ Fragmento reconocido: \"{chunk}\"", flush=True)
                    text += chunk + " "

        # Procesamos resultado final
        final = json.loads(rec.FinalResult())
        final_chunk = final.get("text", "").strip()
        if final_chunk:
            print(f"🗣️ Fragmento final: \"{final_chunk}\"", flush=True)
            text += final_chunk

        transcript = text.strip()
        print(f"✅ Transcripción terminada: \"{transcript}\"", flush=True)
        return transcript

    
    def save_transcription(self, text: str) -> str:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        path_txt = os.path.join(self.session_folder,
                                f"transcripcion_{timestamp}.txt")
        with open(path_txt, "w", encoding="utf-8") as f:
            f.write(text)

        print(f"✅ Transcripción guardada en claro en: {path_txt}", flush=True)
        return path_txt
    
    def encrypt_file(self, input_path, output_path=None):
        """Encripta un archivo y devuelve la ruta del archivo encriptado"""
        if output_path is None:
            output_path = input_path + '.enc'
            
        with open(input_path, 'rb') as f:
            data = f.read()
        
        encrypted_data = self.cipher.encrypt(data)
        
        with open(output_path, 'wb') as f:
            f.write(encrypted_data)
            
        # Eliminar el archivo original
        os.remove(input_path)
        
        return output_path

    def decrypt_file(self, input_path, output_path=None):
        """Desencripta un archivo y devuelve los datos desencriptados"""
        if output_path is None:
            # Modo temporal: crea un archivo temporal
            output_path = tempfile.NamedTemporaryFile(delete=False).name
            
        with open(input_path, 'rb') as f:
            encrypted_data = f.read()
        
        try:
            decrypted_data = self.cipher.decrypt(encrypted_data)
        except Exception as e:
            print(f"Error al desencriptar {input_path}: {e}")
            raise
            
        with open(output_path, 'wb') as f:
            f.write(decrypted_data)
            
        return output_path
    
    def save_snapshot(self, frame):
        """Guarda una imagen encriptada"""
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"foto_{timestamp}.jpg"
        temp_path = os.path.join(self.session_folder, filename)
        
        # Guardar temporalmente sin encriptar
        cv2.imwrite(temp_path, frame)
        
        # Encriptar y eliminar original
        encrypted_path = self.encrypt_file(temp_path)
        encrypted_filename = os.path.basename(encrypted_path)
        
        print(f"✅ Imagen encriptada guardada como: {encrypted_filename}", flush=True)
        return encrypted_filename, encrypted_path


