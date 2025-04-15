import os
import time
import threading
import wave
import pyaudio
import whisper
from flask import Blueprint, jsonify, request, make_response
from flask_socketio import emit  # Para emitir eventos
from dotenv import load_dotenv

load_dotenv()

# Flag global para controlar la grabación de audio
recording_audio_flag = threading.Event()

def create_audio_blueprint(handler, socketio):
    audioRoute = Blueprint('audio', __name__)

    # Parámetros para grabación con PyAudio
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK = 1024
    RECORD_SECONDS = 2

    def record_chunk():
        pa = pyaudio.PyAudio()
        stream = pa.open(format=FORMAT,
                         channels=CHANNELS,
                         rate=RATE,
                         input=True,
                         frames_per_buffer=CHUNK)
        frames = []
        print("🎤 Micrófono abierto correctamente")
        for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK)
            frames.append(data)
        stream.stop_stream()
        stream.close()
        pa.terminate()
        return frames

    def save_wav(frames, filename):
        pa = pyaudio.PyAudio()
        wf = wave.open(filename, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pa.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        pa.terminate()

    @audioRoute.route('/record', methods=['POST', 'OPTIONS'])
    def start_recording():
        print("📡 POST recibido en /audio/record")

        if request.method == 'OPTIONS':
            print("🔁 OPTIONS recibido en /audio/record")
            response = jsonify({})
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response

        if handler.session_folder is None:
            print("❌ No hay sesión activa en handler")
            return jsonify({"error": "No hay sesión activa"}), 400

        recording_audio_flag.set()

        def record_loop():
            print("🎙️ Intentando abrir micrófono con PyAudio...")
            model = whisper.load_model("tiny")
            print("🟢 Iniciando hilo de grabación y transcripción de audio...")
            while recording_audio_flag.is_set():
                try:
                    frames = record_chunk()
                    print(f"✅ Audio capturado: {len(frames)} frames")
                    timestamp = time.strftime("%Y%m%d-%H%M%S")
                    temp_wav = os.path.join(handler.session_folder, f"temp_audio_{timestamp}.wav")
                    save_wav(frames, temp_wav)
                    print(f"💾 Audio guardado: {temp_wav}")

                    result = model.transcribe(temp_wav, language="es")
                    transcription = result.get("text", "").strip()
                    print("📝 Transcripción:", transcription)

                    socketio.emit('transcription', {'text': transcription})
                    os.remove(temp_wav)
                except Exception as e:
                    print("❌ Error en record_loop:", e)
                    break
            print("🛑 Hilo de grabación finalizado")

        threading.Thread(target=record_loop, daemon=True).start()
        return jsonify({"message": "Grabación de audio iniciada y transcripción activada."})


    @audioRoute.route('/stop_recording', methods=['POST', 'OPTIONS'])
    def stop_audio_recording():
        recording_audio_flag.clear()
        print("🔇 Grabación de audio detenida")
        return jsonify({"message": "Grabación de audio detenida"})

    return audioRoute

