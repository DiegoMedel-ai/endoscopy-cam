import os
import time
import cv2

class MediaHandler:
    def __init__(self, base_folder):
        self.base_folder = base_folder
        self.session_folder = None

    def start_session(self):
        # Crear una carpeta única para la sesión actual
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
        return filename, filepath

    def generate(self, cap):
        while True:
            ret, frame = cap.read()
            if not ret:
                continue
            # Codificar el frame en formato JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            # Convertir el buffer a bytes y generar el frame para la transmisión
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
            ret, frame = cap.read()
            if ret:
                video_writer.write(frame)

        video_writer.release()
