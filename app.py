from flask import Flask, render_template
from routes.video import video
from routes.gallery import gallery

app = Flask(__name__)

# Registrar los blueprints
app.register_blueprint(video, url_prefix='/video')
app.register_blueprint(gallery, url_prefix='/gallery')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
