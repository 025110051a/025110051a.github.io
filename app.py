"""
Servidor Flask que publica el juego compilado con pygbag (carpeta build/web).
Local:        python app.py   ->  http://127.0.0.1:5000
Produccion:   gunicorn app:app   (Render)  /  WSGI (PythonAnywhere)
"""
import os
from flask import Flask, send_from_directory, jsonify

BASE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(BASE, "build", "web")

app = Flask(__name__)


@app.route("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.route("/salud")
def salud():
    """Ruta de comprobacion: sirve de evidencia de que el servidor esta 'Running'."""
    return jsonify(estado="running", juego="CRASH.EXE 3D")


@app.route("/<path:archivo>")
def estaticos(archivo):
    return send_from_directory(WEB, archivo)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
