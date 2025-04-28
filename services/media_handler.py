import os
import time
import threading
import subprocess
import wave
import json
import queue
import pyaudio
import cv2
from cryptography.fernet import Fernet
from vosk import Model, KaldiRecognizer
from dotenv import load_dotenv

load_dotenv()

def find_capture_device():
    for i in range(4):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            print(f"Dispositivo de video encontrado en /dev/video{i}", flush=True)
            return cap
    raise RuntimeError("No se encontró una capturadora de video disponible.")

class MediaHandler:
    def __init__(self, base_folder):
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

        self.cap = find_capture_device()

    def start_session(self):
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        self.session_folder = os.path.join(self.base_folder, timestamp)
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

            # ⚙️ Aquí lanzamos el hilo REAL de Python (no eventlet)
            self.audio_thread = threading.Thread(target=record_audio, daemon=True)
            self.audio_thread.start()
            print("✅ Hilo real de grabación de audio lanzado", flush=True)

        except Exception as e:
            print(f"❌ Error en start_audio_recording: {e}", flush=True)
            audio_interface.terminate()


    def stop_audio_recording(self):
        print("🛑 Entrando a stop_audio_recording()", flush=True)
        if self.audio_green_thread:
            self.audio_stop_event.set()
            self.audio_green_thread.wait()
            print("✅ Audio detenido correctamente", flush=True)

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

        while True:
            ret, frame = self.cap.read()
            if not ret:
                continue

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


