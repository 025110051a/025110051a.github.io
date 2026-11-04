"""
CRASH.EXE 3D  -  Esquiva las amenazas del sistema.
Version para NAVEGADOR (pygbag / WebAssembly).

Ejecutar local:   python main.py
Compilar a web:   pygbag --build .      (genera build/web)
Controles:        flechas o A/D | clic/toque izquierda-derecha | ESPACIO/ENTER empezar

ESTRUCTURAS DE DATOS (hechas con clases):
  - Nodo + ColaObstaculos : cola enlazada (FIFO) que guarda los obstaculos activos.
  - Obstaculo, Particula, Pilon : entidades del juego.
"""
import asyncio
import math
import random
import sys

import pygame

pygame.init()
W, H = 960, 640
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("CRASH.EXE 3D")
clock = pygame.time.Clock()

# ---------- Paleta: acero, negro y rojo brillante ----------
RED, ORG, STEEL = (255, 42, 31), (255, 122, 26), (154, 163, 173)
BG, DARK, WHITE = (8, 3, 5), (20, 20, 28), (232, 236, 240)

# ---------- Camara 3D (proyeccion en perspectiva) ----------
CAMY, CAMZ, FOC, HOR = 3.4, 8.0, 520.0, H * 0.36
cam_x = 0.0
ROAD, SX = 4.4, 3.1


def proj(x, y, z):
    """Convierte un punto 3D (x,y,z) a pantalla 2D. k = factor de escala por profundidad."""
    d = CAMZ - z
    k = FOC / max(d, 0.3)
    return (W / 2 + (x - cam_x) * k, HOR + (CAMY - y) * k, k)


def fog(c, z):
    """Niebla: mezcla el color con el fondo segun la distancia (da sensacion de profundidad)."""
    t = min(1, max(0, (CAMZ - z - 20) / 95))
    return tuple(int(c[i] + (BG[i] - c[i]) * t) for i in range(3))


_fonts = {}


def font(sz):
    sz = max(8, int(sz))
    if sz not in _fonts:
        f = pygame.font.Font(None, int(sz * 1.15))  # fuente por defecto (compatible con web)
        f.set_bold(True)
        _fonts[sz] = f
    return _fonts[sz]


def text(s, size, col, cx, cy, glow=True, left=False):
    if glow:
        g = font(size).render(s, True, (90, 10, 8))
        screen.blit(g, g.get_rect(center=(cx + 2, cy + 2)) if not left else (cx + 2, cy + 2))
    im = font(size).render(s, True, col)
    screen.blit(im, im.get_rect(center=(cx, cy)) if not left else (cx, cy))


def box(x, y0, z, w, h, d, col, glow=False):
    """Dibuja una caja 3D (cara frontal, superior y lateral). Devuelve el rectangulo frontal."""
    zf, zb = z + d / 2, z - d / 2
    if CAMZ - zf < 0.6:
        return None
    x1, x2, y1 = x - w / 2, x + w / 2, y0 + h
    f1, f2 = proj(x1, y1, zf), proj(x2, y0, zf)
    b1, b2 = proj(x1, y1, zb), proj(x2, y1, zb)
    c = col if glow else fog(col, z)
    # iluminacion: la cara superior es mas clara y la lateral mas oscura
    top = c if glow else tuple(min(255, int(v * 1.35) + 15) for v in c)
    side = c if glow else tuple(int(v * 0.6) for v in c)
    if y1 < CAMY:
        pygame.draw.polygon(screen, top, [(f1[0], f1[1]), (f2[0], f1[1]), (b2[0], b2[1]), (b1[0], b1[1])])
    if cam_x < x1:
        pygame.draw.polygon(screen, side, [(f1[0], f1[1]), (f1[0], f2[1]), (proj(x1, y0, zb)[0], proj(x1, y0, zb)[1]), (b1[0], b1[1])])
    elif cam_x > x2:
        pygame.draw.polygon(screen, side, [(f2[0], f1[1]), (f2[0], f2[1]), (proj(x2, y0, zb)[0], proj(x2, y0, zb)[1]), (b2[0], b2[1])])
    r = pygame.Rect(int(f1[0]), int(f1[1]), max(1, int(f2[0] - f1[0])), max(1, int(f2[1] - f1[1])))
    pygame.draw.rect(screen, c, r)
    return r


def quad(col, pts):
    pygame.draw.polygon(screen, col, [(proj(*p)[0], proj(*p)[1]) for p in pts])


# =====================================================================
#  ESTRUCTURA DE DATOS PROPIA: COLA ENLAZADA (FIFO)
# =====================================================================
class Nodo:
    """Nodo de la lista enlazada: guarda un dato y la referencia al siguiente."""

    def __init__(self, dato):
        self.dato = dato
        self.siguiente = None


class ColaObstaculos:
    """Cola enlazada. Los obstaculos nacen lejos (encolar al final) y el mas
    viejo, el que esta mas cerca de la camara, esta al frente (desencolar)."""

    def __init__(self):
        self.frente = None
        self.final = None
        self.tamano = 0

    def encolar(self, dato):                      # O(1)
        nodo = Nodo(dato)
        if self.final is None:
            self.frente = self.final = nodo
        else:
            self.final.siguiente = nodo
            self.final = nodo
        self.tamano += 1

    def desencolar(self):                         # O(1)
        if self.frente is None:
            return None
        dato = self.frente.dato
        self.frente = self.frente.siguiente
        if self.frente is None:
            self.final = None
        self.tamano -= 1
        return dato

    def ver_frente(self):
        return self.frente.dato if self.frente else None

    def esta_vacia(self):
        return self.tamano == 0

    def vaciar(self):
        self.frente = self.final = None
        self.tamano = 0

    def eliminar_si(self, condicion):             # O(n): quita nodos que cumplan la condicion
        previo, actual = None, self.frente
        while actual:
            if condicion(actual.dato):
                if previo is None:
                    self.frente = actual.siguiente
                else:
                    previo.siguiente = actual.siguiente
                if actual is self.final:
                    self.final = previo
                self.tamano -= 1
            else:
                previo = actual
            actual = actual.siguiente

    def __iter__(self):
        actual = self.frente
        while actual:
            yield actual.dato
            actual = actual.siguiente

    def __len__(self):
        return self.tamano


# =====================================================================
#  ENTIDADES
# =====================================================================
class Obstaculo:
    TIPOS_HW = {"err": 1.2, "bug": .8, "virus": .85, "404": 1.0, "fire": 2.5, "chip": .7}
    TIPOS_HD = {"bug": .9, "virus": .85, "chip": .7}

    def __init__(self, tipo, x):
        self.tipo = tipo
        self.x = x
        self.z = -105.0
        self.hw = self.TIPOS_HW[tipo]                 # mitad del ancho (colision)
        self.hd = self.TIPOS_HD.get(tipo, .4)         # mitad de la profundidad (colision)
        self.fase = random.random() * 6
        self.muerto = False

    def actualizar(self, dt, velocidad):
        self.z += velocidad * dt
        self.fase += dt * 6

    def choca_con(self, x_jugador):
        return abs(self.x - x_jugador) < self.hw + .85 and abs(self.z) < self.hd + 1.9

    def dibujar(self):
        t, x, z = self.tipo, self.x, self.z
        if t == "err":
            r = box(x, .1, z, 2.4, 1.7, .3, (27, 27, 34))
            if r:
                pygame.draw.rect(screen, fog(RED, z), (r.x, r.y, r.w, r.h * .22))
                text("ERROR", r.h * .26, fog((255, 90, 77), z), r.centerx, r.centery + r.h * .12, False)
        elif t == "404":
            r = box(x, .1, z, 2, 1.4, .3, (13, 13, 18))
            if r:
                pygame.draw.rect(screen, fog(STEEL, z), r, max(1, r.h // 14))
                text("404", r.h * .5, fog(RED, z), r.centerx, r.centery, False)
        elif t == "fire":
            r = box(x, .1, z, 5, 1.3, .4, (255, 80, 22))
            if r:
                text("FIREWALL", r.h * .55, (255, 255, 255), r.centerx, r.centery, False)
        elif t == "bug":
            px, py, k = proj(x, .6, z)
            for i in (-1, 0, 1):
                s = math.sin(self.fase + i * 2) * .15 * k
                pygame.draw.line(screen, fog(ORG, z), (px - .75 * k, py + i * .3 * k + s), (px + .75 * k, py + i * .3 * k - s), max(1, int(k * .06)))
            pygame.draw.ellipse(screen, fog((214, 42, 16), z), (px - .5 * k, py - .45 * k, k, .9 * k))
            pygame.draw.circle(screen, fog((42, 10, 6), z), (int(px), int(py + .4 * k)), max(2, int(.3 * k)))
            for e in (-.12, .12):
                pygame.draw.circle(screen, fog((255, 208, 160), z), (int(px + e * k), int(py + .35 * k)), max(1, int(.06 * k)))
        elif t == "virus":
            px, py, k = proj(x, .95, z)
            for i in range(14):
                a = i * 0.449 + self.fase * .3
                pygame.draw.line(screen, fog(RED, z), (px + math.cos(a) * .55 * k, py + math.sin(a) * .55 * k), (px + math.cos(a) * 1.0 * k, py + math.sin(a) * 1.0 * k), max(2, int(.1 * k)))
            pygame.draw.circle(screen, fog((22, 6, 10), z), (int(px), int(py)), max(3, int(.65 * k)))
            pygame.draw.circle(screen, fog(RED, z), (int(px), int(py)), max(3, int(.65 * k)), max(1, int(.05 * k)))
            pygame.draw.rect(screen, fog((255, 58, 42), z), (px - .4 * k, py - .08 * k, .8 * k, .16 * k))
        else:  # chip (escudo)
            y = 1 + math.sin(self.fase) * .15
            box(x, y, z, 1.2, .25, 1.2, (201, 209, 218))
            box(x, y + .25, z, .7, .1, .7, ORG, True)


class Particula:
    def __init__(self, x, y, z, color):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = random.uniform(-5, 5), random.uniform(0, 7), random.uniform(-5, 5)
        self.vida = 0.8
        self.color = color

    def actualizar(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.vy -= 18 * dt          # gravedad
        self.vida -= dt

    def dibujar(self):
        px, py, k = proj(self.x, self.y, self.z)
        s = max(2, int(.14 * k))
        pygame.draw.rect(screen, self.color, (px, py, s, s))


class Pilon:
    """Torre tipo servidor al borde de la carretera (decoracion)."""

    def __init__(self, lado, indice):
        self.x = lado * (6.6 + random.random() * 1.5)
        self.z = 5 - indice * 9
        self.alto = 3 + random.random() * 7

    def actualizar(self, avance):
        self.z += avance
        if self.z > 8:
            self.z -= 126

    def dibujar(self):
        r = box(self.x, 0, self.z, 1.4, self.alto, 1.4, (26, 29, 36))
        if r:
            ix = r.left if self.x > 0 else r.right
            pygame.draw.line(screen, fog(RED, self.z), (ix, r.y + r.h * .1), (ix, r.bottom), max(1, r.w // 14))


# =====================================================================
#  JUEGO
# =====================================================================
class Game:
    def __init__(self):
        self.state = "menu"
        self.best = 0                       # el record vive en memoria (en web no hay disco)
        self.dist = 0.0
        self.pilones = [Pilon(s, i) for s in (-1, 1) for i in range(14)]
        self.velo = pygame.Surface((W, H), pygame.SRCALPHA)
        self.velo.fill((5, 5, 8, 215))
        self.obs = ColaObstaculos()
        self.reset()

    def reset(self):
        self.obs.vaciar()
        self.parts = []
        self.score, self.lives, self.speed, self.t = 0.0, 3, 24.0, 0.0
        self.spawn, self.inv, self.shield, self.shake = 0.5, 0.0, 0.0, 0.0
        self.x, self.lean = 0.0, 0.0

    def start(self):
        self.reset()
        self.state = "play"

    def boom(self, x, y, z, n, cols=(RED, ORG)):
        for _ in range(n):
            self.parts.append(Particula(x, y, z, random.choice(cols)))

    def add_obstacle(self):
        r = random.random()
        ty = "err" if r < .2 else "bug" if r < .4 else "virus" if r < .6 else "404" if r < .78 else "fire" if r < .92 else "chip"
        if ty == "fire" and self.speed < 32:
            ty = "bug"
        hw = Obstaculo.TIPOS_HW[ty]
        x = random.choice((-1.5, 1.5)) if ty == "fire" else random.uniform(-1, 1) * (4 - hw - .2)
        self.obs.encolar(Obstaculo(ty, x))

    def update(self, dt, direccion):
        mult = 1 if self.state == "play" else .3
        self.dist += self.speed * dt * mult
        for p in self.pilones:
            p.actualizar(self.speed * dt * mult)
        for p in self.parts:
            p.actualizar(dt)
        self.parts = [p for p in self.parts if p.vida > 0]
        if self.state != "play":
            return
        self.t += dt
        self.speed = min(70, 24 + self.t * .8)
        self.score += dt * self.speed * .35
        d = direccion
        self.x = max(-SX, min(SX, self.x + d * 14 * dt))
        self.lean += (d - self.lean) * min(1, dt * 8)
        self.spawn -= dt
        if self.spawn <= 0:
            self.add_obstacle()
            self.spawn = max(.3, .9 - self.t * .011) * (.7 + random.random() * .6)
        self.inv, self.shield, self.shake = max(0, self.inv - dt), max(0, self.shield - dt), max(0, self.shake - dt * 3)
        for o in self.obs:
            o.actualizar(dt, self.speed)
            if o.choca_con(self.x):                     # colision
                o.muerto = True
                if o.tipo == "chip":
                    self.shield = 5
                    self.boom(o.x, 1, o.z, 20, ((207, 216, 227),))
                elif self.shield > 0:
                    self.boom(o.x, 1, o.z, 24)
                elif self.inv <= 0:
                    self.lives -= 1
                    self.inv, self.shake = 1.6, 1.0
                    self.boom(self.x, 1, 0, 45)
                    if self.lives <= 0:
                        self.state = "over"
                        self.best = max(self.best, int(self.score))
        # quitar de la cola los obstaculos muertos o que ya pasaron la camara
        self.obs.eliminar_si(lambda o: o.muerto or o.z >= 7)

    # ---------- Dibujo ----------
    def draw_car(self):
        if self.inv > 0 and int(self.t * 14) % 2:
            return
        x = self.x
        for sx in (-.95, .95):
            for sz in (-1.3, 1.3):
                box(x + sx, 0, sz, .36, .8, .8, (8, 8, 10), True)
        box(x, .25, 0, 1.8, .6, 4, (36, 40, 52), True)
        box(x, .85, .3, 1.4, .5, 1.8, (10, 10, 14), True)
        box(x, .86, -1.2, .3, .03, 1.6, RED, True)
        box(x, 1.2, 1.9, 1.9, .08, .5, (28, 30, 38), True)
        for lx in (-.65, .65):
            box(x + lx, .55, 2.0, .45, .18, .08, (255, 40, 30), True)
        if self.shield > 0:
            px, py, k = proj(x, .8, 0)
            pygame.draw.circle(screen, (207, 216, 227), (int(px), int(py)), int(2.2 * k), 3)

    def draw(self):
        global cam_x
        cam_x += (self.x * .6 - cam_x) * .15
        screen.fill(BG)
        for i in range(6):  # resplandor del horizonte
            pygame.draw.rect(screen, (40 - i * 6, 8, 8), (0, HOR - 30 + i * 6, W, 6))
        # cuadricula del suelo
        off = self.dist % 4
        for k in range(30):
            z = 7 - k * 4 + off
            a, b = proj(-40, 0, z), proj(40, 0, z)
            pygame.draw.line(screen, fog((90, 20, 16), z), (a[0], a[1]), (b[0], b[1]), 1)
        # carretera (franjas alternadas)
        n = int(self.dist // 4)
        for k in range(30):
            zn = min(7.5, 6 - k * 4 + off)
            col = (18, 18, 24) if (k + n) % 2 else (13, 13, 18)
            quad(fog(col, zn), [(-ROAD, 0, zn), (ROAD, 0, zn), (ROAD, 0, zn - 4), (-ROAD, 0, zn - 4)])
        for sx in (-ROAD, ROAD):  # bordes de neon
            quad(RED, [(sx - .13, 0.02, 7.5), (sx + .13, .02, 7.5), (sx + .13, .02, -115), (sx - .13, .02, -115)])
        for lx in (-1.4, 1.4):  # rayas de carril
            for k in range(20):
                zn = 5 - k * 6 + (self.dist % 6)
                if zn < 7.5:
                    quad(fog((120, 25, 22), zn), [(lx - .06, .02, zn), (lx + .06, .02, zn), (lx + .06, .02, zn - 2.5), (lx - .06, .02, zn - 2.5)])
        # painter's algorithm: dibujar de lejos a cerca
        items = [(p.z, p) for p in self.pilones] + [(o.z, o) for o in self.obs]
        items.sort(key=lambda a: a[0])
        for _, ent in items:
            ent.dibujar()
        self.draw_car()
        for p in self.parts:
            p.dibujar()
        if self.shake > 0:  # temblor de pantalla
            screen.blit(screen.copy(), (int(random.randint(-6, 6) * self.shake), int(random.randint(-6, 6) * self.shake)))
        # HUD
        if self.state == "play":
            text(f"PUNTOS {int(self.score)}", 22, WHITE, 16, 14, True, True)
            text(f"RECORD {self.best}", 16, STEEL, 16, 42, False, True)
            for i in range(self.lives):
                cx = W - 30 - i * 30
                pygame.draw.polygon(screen, RED, [(cx, 14), (cx + 11, 28), (cx, 42), (cx - 11, 28)])
            if self.shield > 0:
                text(f"ESCUDO {self.shield:.1f}s", 16, ORG, W - 100, 62, False)
        else:
            screen.blit(self.velo, (0, 0))
            if self.state == "menu":
                text("CRASH.EXE", 80, RED, W // 2, 150)
                lines = ["Esquiva las amenazas del sistema",
                         "ERROR  -  BUG  -  VIRUS  -  404  -  FIREWALL",
                         "Recoge el CPU plateado: escudo de 5 s",
                         "Flechas / A-D, o toca izquierda-derecha"]
            else:
                text("SISTEMA", 64, RED, W // 2, 130)
                text("COMPROMETIDO", 64, RED, W // 2, 195)
                lines = [f"Puntos: {int(self.score)}", f"Record: {self.best}"]
            for i, s in enumerate(lines):
                text(s, 20, STEEL if i else WHITE, W // 2, 290 + i * 34, False)
            if pygame.time.get_ticks() // 500 % 2:
                text("ESPACIO, ENTER O CLIC PARA " + ("JUGAR" if self.state == "menu" else "REINICIAR"), 22, (255, 122, 106), W // 2, 500, False)


def leer_direccion():
    """Teclado (flechas / A-D) o mouse/touch (mitad izquierda o derecha de la pantalla)."""
    keys = pygame.key.get_pressed()
    d = int(bool(keys[pygame.K_RIGHT] or keys[pygame.K_d])) - int(bool(keys[pygame.K_LEFT] or keys[pygame.K_a]))
    if d == 0 and pygame.mouse.get_pressed()[0]:
        d = 1 if pygame.mouse.get_pos()[0] > W / 2 else -1
    return d


async def main():
    game = Game()
    test = "--test" in sys.argv
    frames = 0
    while True:
        dt = 1 / 60 if test else min(.05, clock.tick(60) / 1000)
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                return
            if game.state != "play" and (
                (e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_RETURN))
                or e.type == pygame.MOUSEBUTTONDOWN
            ):
                game.start()
        d = leer_direccion()
        if test:  # piloto automatico para pruebas
            if game.state == "menu" and frames == 5:
                game.start()
            game.x = 2.5 * math.sin(frames / 40)
            d = 0
        game.update(dt, d)
        game.draw()
        pygame.display.flip()
        frames += 1
        if test and frames in (4, 300):
            pygame.image.save(screen, f"/tmp/crash_{frames}.png")
        if test and frames >= 600:
            print("OK frames:", frames, "estado:", game.state, "puntos:", int(game.score),
                  "vidas:", game.lives, "obstaculos en cola:", len(game.obs))
            return
        await asyncio.sleep(0)   # OBLIGATORIO para pygbag: cede el control al navegador


asyncio.run(main())
