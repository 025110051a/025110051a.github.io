# PASOS (hazlos en este orden)

## 1. En tu PC (carpeta del proyecto con main.py y app.py)
    pip install pygame-ce pygbag
    python main.py              # prueba local (captura: IDE + juego)
    pygbag --build .            # crea build/web  (captura: terminal)
    pip install flask
    python app.py               # abre http://127.0.0.1:5000 y verifica que el juego carga

## 2. GitHub (captura: terminal + repositorio)
    git init
    git add .
    git commit -m "CRASH.EXE 3D"
    git branch -M main
    git remote add origin https://github.com/TU_USUARIO/crash-exe-3d.git
    git push -u origin main
IMPORTANTE: NO ignores build/web; debe subirse al repositorio (ya viene compilado).

## 3A. Render (recomendado: automatico desde GitHub)
 - render.com -> New + -> Web Service -> conecta el repo
 - Runtime: Python 3 | Build Command: pip install -r requirements.txt
 - Start Command: gunicorn app:app | Plan: Free
 - Captura: panel, logs con "Running"/"Your service is live", y la URL https://xxxx.onrender.com

## 3B. PythonAnywhere (alternativa sin Git)
 - Cuenta Beginner (gratis) -> Files: sube main.py/app.py y la carpeta build/web
 - Web -> Add a new web app -> Flask -> Python 3.x
 - En el archivo WSGI:  from app import app as application   (ajusta la ruta a tu carpeta)
 - Reload. URL: https://TU_USUARIO.pythonanywhere.com
 - Captura: pestana Web, error/server log, y el juego en el navegador

## 4. Nota para jugar
El navegador pide un clic en la pagina antes de arrancar (es normal en pygbag).
En Render gratis, la primera carga puede tardar ~50 s si el servicio estaba dormido.
