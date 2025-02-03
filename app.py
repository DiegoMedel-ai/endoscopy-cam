from flask import Flask, render_template
from routes.video import video

app = Flask(__name__)

# Registrar el Blueprint
app.register_blueprint(video, url_prefix='/video')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
