"""
CRASH.EXE 3D - VIDEOJUEGO 3D + ESTRUCTURA DE DATOS + SERVIDOR WEB (un solo archivo)
Asignatura: Estructura de Datos
Docente: Giomar

Como funciona:
  - Python (Flask) guarda en una COLA ENLAZADA (FIFO) los obstaculos activos de cada partida.
  - El navegador dibuja el mundo 3D (Three.js). Le pide a Python cada obstaculo nuevo
    (/api/generar) y le avisa cuando uno choca o sale de la pista (/api/quitar).

Ejecucion local:
  1. pip install flask
  2. python app.py
  3. Abrir http://127.0.0.1:5000

Hosting (Render):  Build: pip install -r requirements.txt  |  Start: gunicorn app:app
"""

import os
import random
from flask import Flask, jsonify, render_template_string, request

# =====================================================================
# 1. ESTRUCTURA DE DATOS EN PYTHON: COLA ENLAZADA (FIFO) CREADA CON CLASES
# =====================================================================
class NodoObstaculo:
    """Nodo de la lista enlazada: guarda un obstaculo y la referencia al siguiente."""
    def __init__(self, id_obs, tipo, x, z):
        self.id = id_obs
        self.tipo = tipo  # 'error', 'virus', 'firewall'
        self.x = x
        self.z = z
        self.siguiente = None


class ColaObstaculos:
    """
    Cola FIFO enlazada. Los obstaculos nacen lejos (se encolan al final) y el mas
    antiguo, el que esta mas cerca del jugador, esta al frente (se desencola primero).
    """
    def __init__(self):
        self.frente = None
        self.final = None
        self.longitud = 0
        self.contador_ids = 0

    def encolar(self, tipo, x, z):          # O(1)
        self.contador_ids += 1
        nuevo = NodoObstaculo(self.contador_ids, tipo, x, z)
        if self.final is None:
            self.frente = self.final = nuevo
        else:
            self.final.siguiente = nuevo
            self.final = nuevo
        self.longitud += 1
        return nuevo

    def desencolar(self):                   # O(1)
        if self.frente is None:
            return None
        nodo = self.frente
        self.frente = nodo.siguiente
        if self.frente is None:
            self.final = None
        self.longitud -= 1
        return nodo

    def eliminar_id(self, id_obs):          # O(1) si es el frente, O(n) en otro caso
        if self.frente is not None and self.frente.id == id_obs:
            return self.desencolar()
        previo, actual = self.frente, self.frente.siguiente if self.frente else None
        while actual:
            if actual.id == id_obs:
                previo.siguiente = actual.siguiente
                if actual is self.final:
                    self.final = previo
                self.longitud -= 1
                return actual
            previo, actual = actual, actual.siguiente
        return None

    def vaciar(self):
        self.frente = self.final = None
        self.longitud = 0

    def a_lista_dict(self):
        """Convierte la cola a una lista de diccionarios (para mostrarla como JSON)."""
        actual, lista = self.frente, []
        while actual:
            lista.append({"id": actual.id, "tipo": actual.tipo, "x": actual.x, "z": actual.z})
            actual = actual.siguiente
        return lista

    def __len__(self):
        return self.longitud


# Una cola por cada partida (el navegador envia un identificador 'sid')
partidas = {}
MAX_PARTIDAS = 200
TIPOS = ["error", "virus", "firewall"]


def cola_de(sid):
    """Devuelve la cola de la partida; la crea si no existe."""
    sid = str(sid)[:64]
    if sid not in partidas:
        if len(partidas) >= MAX_PARTIDAS:           # evita crecer sin limite
            partidas.pop(next(iter(partidas)))
        partidas[sid] = ColaObstaculos()
    return partidas[sid]


# =====================================================================
# 2. SERVIDOR FLASK CON MOTOR 3D INTEGRADO (WEBGL / THREE.JS)
# =====================================================================

app = Flask(__name__)

PLANTILLA_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CRASH.EXE 3D - Estructura de Datos</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background-color: #05050a; color: #fff; overflow: hidden; }
        #canvas-container { width: 100vw; height: 100vh; display: block; }
        
        /* UI Overlay */
        #hud {
            position: absolute;
            top: 20px;
            left: 20px;
            z-index: 10;
            background: rgba(10, 10, 20, 0.75);
            padding: 15px 25px;
            border-radius: 10px;
            border: 1px solid rgba(0, 240, 255, 0.3);
            backdrop-filter: blur(5px);
            box-shadow: 0 0 20px rgba(0, 240, 255, 0.15);
        }
        .stat-label { font-size: 11px; text-transform: uppercase; color: #8a8b9e; letter-spacing: 1px; }
        .stat-value { font-size: 24px; font-weight: bold; color: #00f0ff; text-shadow: 0 0 8px rgba(0,240,255,0.5); margin-bottom: 8px; }
        .lives { color: #ff2a5f; text-shadow: 0 0 8px rgba(255,42,95,0.5); }
        
        #overlay {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(5, 5, 10, 0.85);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 20;
            backdrop-filter: blur(8px);
        }
        h1 { font-size: 54px; font-weight: 900; color: #ff2a5f; text-shadow: 0 0 20px rgba(255,42,95,0.6); margin-bottom: 10px; letter-spacing: 2px; }
        p.subtitle { font-size: 16px; color: #a0a5c0; margin-bottom: 30px; text-align: center; max-width: 500px; }
        .btn {
            background: linear-gradient(45deg, #ff2a5f, #ff7e40);
            border: none;
            padding: 14px 40px;
            color: white;
            font-size: 18px;
            font-weight: bold;
            border-radius: 30px;
            cursor: pointer;
            box-shadow: 0 0 25px rgba(255,42,95,0.5);
            transition: all 0.2s ease;
        }
        .btn:hover { transform: scale(1.05); box-shadow: 0 0 35px rgba(255,42,95,0.8); }
        
        .badge {
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: rgba(15, 15, 25, 0.8);
            border: 1px solid rgba(255,255,255,0.1);
            padding: 10px 15px;
            border-radius: 6px;
            font-size: 12px;
            color: #8a8b9e;
        }
    </style>
    <!-- Three.js Motor 3D Gráfico de Alta Calidad -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>

    <div id="hud">
        <div class="stat-label">Puntaje</div>
        <div id="score-val" class="stat-value">0</div>
        <div class="stat-label">Vidas del Navegador</div>
        <div id="lives-val" class="stat-value lives">❤❤❤</div>
        <div class="stat-label">Estructura FIFO (Cola)</div>
        <div id="queue-val" style="font-size: 14px; color: #a0a5c0;">Nodos activos: 0</div>
    </div>

    <div id="overlay">
        <h1 id="title-text">CRASH.EXE 3D</h1>
        <p class="subtitle">Esquiva las amenazas del sistema en este entorno 3D impulsado por Python y Estructura de Datos (Cola Enlazada FIFO).</p>
        <button class="btn" onclick="startGame()">INICIAR JUEGO</button>
    </div>

    <div class="badge">
        Docente: Giomar | Estructura de Datos
    </div>

    <div id="canvas-container"></div>

    <script>
        // CONFIGURACIÓN ESCENA 3D (THREE.JS)
        let scene, camera, renderer;
        let player, playerSpeed = 0.25;
        let obstacles = [];
        let score = 0, lives = 3;
        let isPlaying = false;
        let keys = {};
        let spawnTimer = 0;
        let queueLen = 0;
        let pendingSpawn = false;
        const SID = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Math.random()).slice(2);

        // Llama a la API de Python (la cola enlazada vive en el servidor)
        function api(ruta, datos) {
            return fetch(ruta, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(Object.assign({ sid: SID }, datos || {}))
            }).then(r => r.json()).catch(() => null);
        }

        // Pide a Python un obstaculo nuevo (Python lo ENCOLA y responde sus datos)
        function pedirObstaculo() {
            if (pendingSpawn) return;
            pendingSpawn = true;
            api('/api/generar').then(d => {
                if (d && isPlaying) { createObstacle(d); queueLen = d.longitud; }
            }).then(() => { pendingSpawn = false; });
        }

        // Avisa a Python que un obstaculo salio o choco (Python lo DESENCOLA)
        function quitarObstaculo(id) {
            api('/api/quitar', { id: id }).then(d => { if (d) queueLen = d.longitud; });
        }

        function init3D() {
            const container = document.getElementById('canvas-container');
            
            scene = new THREE.Scene();
            scene.fog = new THREE.FogExp2(0x05050a, 0.015);

            camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set(0, 3.5, 7);
            camera.lookAt(0, 1, -5);

            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setPixelRatio(window.devicePixelRatio);
            renderer.shadowMap.enabled = true;
            container.appendChild(renderer.domElement);

            // Luces del escenario 3D
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
            scene.add(ambientLight);

            const dirLight = new THREE.DirectionalLight(0xff2a5f, 0.8);
            dirLight.position.set(5, 12, 5);
            dirLight.castShadow = true;
            scene.add(dirLight);

            const gridLight = new THREE.PointLight(0x00f0ff, 1.5, 30);
            gridLight.position.set(0, 2, -10);
            scene.add(gridLight);

            // Carretera 3D (Pista)
            const roadGeo = new THREE.PlaneGeometry(10, 200);
            const roadMat = new THREE.MeshStandardMaterial({ color: 0x0a0a14, roughness: 0.2, metalness: 0.8 });
            const road = new THREE.Mesh(roadGeo, roadMat);
            road.rotation.x = -Math.PI / 2;
            road.position.z = -90;
            road.receiveShadow = true;
            scene.add(road);

            // Bordes Neón
            for(let side of [-5.1, 5.1]) {
                const borderGeo = new THREE.BoxGeometry(0.2, 0.2, 200);
                const borderMat = new THREE.MeshBasicMaterial({ color: 0x00f0ff });
                const border = new THREE.Mesh(borderGeo, borderMat);
                border.position.set(side, 0.1, -90);
                scene.add(border);
            }

            // Entidad Controlable (Nave / Jugador 3D)
            const playerGroup = new THREE.Group();
            
            const bodyGeo = new THREE.BoxGeometry(1.2, 0.4, 2);
            const bodyMat = new THREE.MeshStandardMaterial({ color: 0x00f0ff, roughness: 0.1, metalness: 0.9 });
            const body = new THREE.Mesh(bodyGeo, bodyMat);
            body.castShadow = true;
            playerGroup.add(body);

            const cabinGeo = new THREE.BoxGeometry(0.8, 0.3, 0.9);
            const cabinMat = new THREE.MeshBasicMaterial({ color: 0xff2a5f });
            const cabin = new THREE.Mesh(cabinGeo, cabinMat);
            cabin.position.set(0, 0.35, -0.1);
            playerGroup.add(cabin);

            playerGroup.position.set(0, 0.3, 2);
            player = playerGroup;
            scene.add(player);

            // Eventos de teclado
            window.addEventListener('keydown', e => keys[e.code] = true);
            window.addEventListener('keyup', e => keys[e.code] = false);
            window.addEventListener('resize', onWindowResize);

            animate();
        }

        function createObstacle(datos) {
            const type = datos.tipo;      // tipo y posicion los decide Python
            const x = datos.x;

            const obsGroup = new THREE.Group();
            let geo, mat;

            if(type === 'error') {
                geo = new THREE.BoxGeometry(1.6, 1.6, 1.6);
                mat = new THREE.MeshStandardMaterial({ color: 0xff2a5f, roughness: 0.3 });
            } else if(type === 'virus') {
                geo = new THREE.IcosahedronGeometry(1, 0);
                mat = new THREE.MeshStandardMaterial({ color: 0xff9900, wireframe: true });
            } else {
                geo = new THREE.BoxGeometry(3.5, 1.2, 0.5);
                mat = new THREE.MeshBasicMaterial({ color: 0x00f0ff, wireframe: true });
            }

            const mesh = new THREE.Mesh(geo, mat);
            mesh.castShadow = true;
            obsGroup.add(mesh);
            obsGroup.position.set(x, 0.8, -80);
            
            scene.add(obsGroup);
            obstacles.push({ id: datos.id, mesh: obsGroup, x: x, z: -80, type: type });
        }

        function startGame() {
            document.getElementById('overlay').style.display = 'none';
            score = 0;
            lives = 3;
            isPlaying = true;
            
            // Limpiar obstáculos antiguos
            obstacles.forEach(o => scene.remove(o.mesh));
            obstacles = [];
            queueLen = 0;
            api('/api/reiniciar');
            player.position.x = 0;
            updateHUD();
        }

        function gameOver() {
            isPlaying = false;
            document.getElementById('title-text').innerText = 'SISTEMA CRASHED';
            document.getElementById('overlay').style.display = 'flex';
        }

        function updateHUD() {
            document.getElementById('score-val').innerText = Math.floor(score);
            document.getElementById('lives-val').innerText = '❤'.repeat(lives);
            document.getElementById('queue-val').innerText = 'Nodos en Cola FIFO (Python): ' + queueLen;
        }

        function animate() {
            requestAnimationFrame(animate);

            if (isPlaying) {
                // Movimiento del jugador
                if ((keys['ArrowLeft'] || keys['KeyA']) && player.position.x > -3.8) {
                    player.position.x -= playerSpeed;
                    player.rotation.z = 0.15;
                } else if ((keys['ArrowRight'] || keys['KeyD']) && player.position.x < 3.8) {
                    player.position.x += playerSpeed;
                    player.rotation.z = -0.15;
                } else {
                    player.rotation.z = 0;
                }

                // Cámara suave
                camera.position.x += (player.position.x * 0.5 - camera.position.x) * 0.1;

                // Generación de obstáculos
                spawnTimer++;
                if (spawnTimer > 40) {
                    pedirObstaculo();
                    spawnTimer = 0;
                }

                // Actualizar obstáculos (Simulación de la cola en 3D)
                score += 0.2;
                const speed = 0.7 + (score * 0.0005);

                for (let i = obstacles.length - 1; i >= 0; i--) {
                    let obs = obstacles[i];
                    obs.mesh.position.z += speed;
                    obs.mesh.rotation.x += 0.02;
                    obs.mesh.rotation.y += 0.02;

                    // Detección de Colisión
                    const dist = player.position.distanceTo(obs.mesh.position);
                    if (dist < 1.8) {
                        scene.remove(obs.mesh);
                        obstacles.splice(i, 1);
                        quitarObstaculo(obs.id);
                        lives--;
                        updateHUD();
                        if (lives <= 0) gameOver();
                        continue;
                    }

                    // Desencolar cuando pasa la cámara (FIFO)
                    if (obs.mesh.position.z > 5) {
                        scene.remove(obs.mesh);
                        obstacles.splice(i, 1);
                        quitarObstaculo(obs.id);
                        updateHUD();
                    }
                }
                updateHUD();
            }

            renderer.render(scene, camera);
        }

        function onWindowResize() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }

        window.onload = init3D;
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    """Ruta principal: Entrega el juego 3D al navegador."""
    return render_template_string(PLANTILLA_HTML)

@app.route("/salud")
def salud():
    """Ruta de verificación para el Hosting / Evaluación."""
    return jsonify(
        estado="running",
        juego="CRASH.EXE 3D",
        estructura_datos="ColaObstaculos (FIFO Enlazada)",
        nodos_activos=sum(len(c) for c in partidas.values()),
        partidas_activas=len(partidas)
    )


def datos_json():
    return request.get_json(silent=True) or {}


@app.route("/api/reiniciar", methods=["POST"])
def api_reiniciar():
    """Vacia la cola al empezar una partida nueva."""
    cola = cola_de(datos_json().get("sid", "anon"))
    cola.vaciar()
    return jsonify(ok=True, longitud=len(cola))


@app.route("/api/generar", methods=["POST"])
def api_generar():
    """Python crea un obstaculo y lo ENCOLA (al final de la cola)."""
    cola = cola_de(datos_json().get("sid", "anon"))
    nodo = cola.encolar(random.choice(TIPOS), round(random.uniform(-3.6, 3.6), 2), -80)
    return jsonify(id=nodo.id, tipo=nodo.tipo, x=nodo.x, z=nodo.z, longitud=len(cola))


@app.route("/api/quitar", methods=["POST"])
def api_quitar():
    """El obstaculo choco o salio de la pista: Python lo saca de la cola."""
    datos = datos_json()
    cola = cola_de(datos.get("sid", "anon"))
    try:
        id_obs = int(datos.get("id", -1))
    except (TypeError, ValueError):
        id_obs = -1
    cola.eliminar_id(id_obs)
    return jsonify(longitud=len(cola), cola=cola.a_lista_dict())

if __name__ == "__main__":
    # Inicia el servidor en el puerto 5000 localmente o en el asignado por el hosting
    port = int(os.environ.get("PORT", 5000))
    print(f"Servidor iniciado en http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("DEBUG") == "1")