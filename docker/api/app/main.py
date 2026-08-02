#!/usr/bin/env python3
"""
api — el backend de la tienda del libro «Kubernetes 101».

Habla con `db` (PostgreSQL) y con `cache` (Redis). Expone lo justo para que
las probes, el HPA y las NetworkPolicy del libro tengan algo real que medir.

Rutas:
  GET /healthz        vivo (no comprueba dependencias)  -> livenessProbe
  GET /readyz         listo (sí las comprueba)          -> readinessProbe
  GET /metrics        métricas en formato Prometheus
  GET /api/productos  lee de la base de datos, cachea en Redis
  GET /api/visitas    incrementa un contador en Redis
  GET /api/quemar     consume CPU a propósito, para ver escalar al HPA
"""
import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PUERTO = int(os.environ.get("APP_PORT", "8080"))
DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "tienda")
DB_USER = os.environ.get("POSTGRES_USER", os.environ.get("DB_USER", "tienda"))
DB_PASS = os.environ.get("PGPASSWORD", os.environ.get("DB_PASSWORD", ""))
CACHE_HOST = os.environ.get("CACHE_HOST", "cache")
CACHE_PORT = int(os.environ.get("CACHE_PORT", "6379"))
ARRANQUE_LENTO = int(os.environ.get("ARRANQUE_LENTO_SEGUNDOS", "5"))

INICIO = time.time()
LISTO = threading.Event()
METRICAS = {"peticiones": 0, "errores": 0, "cache_hits": 0, "cache_misses": 0}
CANDADO = threading.Lock()


# ─────────────────────────────────────────────────────────── Redis (RESP mínimo)
class Cache:
    """Cliente Redis diminuto. Suficiente para GET, SET e INCR."""

    def __init__(self, host, port, timeout=2.0):
        self.host, self.port, self.timeout = host, port, timeout

    def _mandar(self, *partes):
        cmd = f"*{len(partes)}\r\n".encode()
        for p in partes:
            b = str(p).encode()
            cmd += b"$" + str(len(b)).encode() + b"\r\n" + b + b"\r\n"
        with socket.create_connection((self.host, self.port), self.timeout) as s:
            s.sendall(cmd)
            return self._leer(s.makefile("rb"))

    @staticmethod
    def _leer(f):
        linea = f.readline().strip()
        if not linea:
            raise ConnectionError("respuesta vacía de Redis")
        marca, resto = linea[:1], linea[1:]
        if marca in (b"+", b":"):
            return resto.decode()
        if marca == b"-":
            raise RuntimeError(resto.decode())
        if marca == b"$":
            n = int(resto)
            if n == -1:
                return None
            dato = f.read(n)
            f.read(2)
            return dato.decode()
        raise RuntimeError(f"respuesta inesperada: {linea!r}")

    def get(self, k):
        return self._mandar("GET", k)

    def set(self, k, v, ttl=30):
        return self._mandar("SET", k, v, "EX", ttl)

    def incr(self, k):
        return self._mandar("INCR", k)

    def ping(self):
        return self._mandar("PING") == "PONG"


cache = Cache(CACHE_HOST, CACHE_PORT)


# ──────────────────────────────────────────────────────────────────── PostgreSQL
def conexion_db():
    import psycopg  # se importa aquí para que el proceso arranque sin la base

    return psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS, connect_timeout=3,
    )


def preparar_db():
    """Crea la tabla y siembra datos. Idempotente: se puede llamar mil veces."""
    with conexion_db() as cn, cn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS productos ("
            "  id SERIAL PRIMARY KEY,"
            "  nombre TEXT NOT NULL,"
            "  precio NUMERIC(8,2) NOT NULL)"
        )
        cur.execute("SELECT COUNT(*) FROM productos")
        if cur.fetchone()[0] == 0:
            cur.executemany(
                "INSERT INTO productos (nombre, precio) VALUES (%s, %s)",
                [("Camiseta", 19.90), ("Zapatillas", 64.50),
                 ("Gorra", 12.00), ("Sudadera", 39.95)],
            )
        cn.commit()


def leer_productos():
    with conexion_db() as cn, cn.cursor() as cur:
        cur.execute("SELECT id, nombre, precio FROM productos ORDER BY id")
        return [{"id": i, "nombre": n, "precio": float(p)} for i, n, p in cur.fetchall()]


def db_viva():
    try:
        with conexion_db() as cn, cn.cursor() as cur:
            cur.execute("SELECT 1")
            return True
    except Exception:
        return False


# ───────────────────────────────────────────────────────────────── arranque lento
def arrancar():
    """Simula una aplicación que tarda en estar lista: eso justifica la startupProbe."""
    time.sleep(ARRANQUE_LENTO)
    for intento in range(30):
        try:
            preparar_db()
            break
        except Exception as e:
            print(f"esperando a la base de datos ({intento + 1}/30): {e}", flush=True)
            time.sleep(2)
    LISTO.set()
    print("api lista", flush=True)


# ────────────────────────────────────────────────────────────────────── servidor
class Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, formato, *args):
        print(f"{self.address_string()} {formato % args}", flush=True)

    def responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
        datos = cuerpo if isinstance(cuerpo, bytes) else cuerpo.encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def json(self, codigo, obj):
        self.responder(codigo, json.dumps(obj, ensure_ascii=False, indent=2))

    def do_GET(self):
        with CANDADO:
            METRICAS["peticiones"] += 1
        ruta = self.path.split("?")[0]
        try:
            if ruta == "/healthz":
                self.json(200, {"estado": "vivo", "uptime": round(time.time() - INICIO, 1)})
            elif ruta == "/readyz":
                self.readyz()
            elif ruta == "/metrics":
                self.metricas()
            # Con y sin barra final: `location /api/` de nginx solo captura la
            # ruta con barra, así que desde `web` esta es la única forma de
            # llegar aquí. Sin `/api/` en la lista, el botón «Quién responde»
            # de la página contesta 404.
            elif ruta in ("/", "/api", "/api/"):
                self.json(200, {
                    "servicio": "api", "version": os.environ.get("APP_VERSION", "2.1.0"),
                    "pod": os.environ.get("POD_NAME", socket.gethostname()),
                    "nodo": os.environ.get("NODE_NAME", "desconocido"),
                    "rutas": ["/healthz", "/readyz", "/metrics",
                              "/api/productos", "/api/visitas", "/api/quemar"],
                })
            elif ruta == "/api/productos":
                self.productos()
            elif ruta == "/api/visitas":
                self.json(200, {"visitas": int(cache.incr("tienda:visitas"))})
            elif ruta == "/api/quemar":
                fin = time.time() + 5
                while time.time() < fin:
                    pass
                self.json(200, {"quemado": "5s de CPU"})
            else:
                self.json(404, {"error": "no encontrado", "ruta": ruta})
        except Exception as e:
            with CANDADO:
                METRICAS["errores"] += 1
            self.json(500, {"error": str(e)})

    def readyz(self):
        if not LISTO.is_set():
            self.json(503, {"estado": "arrancando"})
            return
        estado = {"db": db_viva(), "cache": False}
        try:
            estado["cache"] = cache.ping()
        except Exception:
            pass
        listo = all(estado.values())
        self.json(200 if listo else 503, {"estado": "listo" if listo else "degradado", **estado})

    def productos(self):
        clave = "tienda:productos"
        try:
            guardado = cache.get(clave)
        except Exception:
            guardado = None
        if guardado:
            with CANDADO:
                METRICAS["cache_hits"] += 1
            self.responder(200, guardado)
            return
        with CANDADO:
            METRICAS["cache_misses"] += 1
        datos = json.dumps({"origen": "db", "productos": leer_productos()},
                           ensure_ascii=False, indent=2)
        try:
            cache.set(clave, datos, ttl=30)
        except Exception:
            pass
        self.responder(200, datos)

    def metricas(self):
        with CANDADO:
            m = dict(METRICAS)
        texto = (
            "# HELP api_peticiones_total Peticiones HTTP atendidas.\n"
            "# TYPE api_peticiones_total counter\n"
            f"api_peticiones_total {m['peticiones']}\n"
            "# HELP api_errores_total Peticiones que terminaron en error.\n"
            "# TYPE api_errores_total counter\n"
            f"api_errores_total {m['errores']}\n"
            "# HELP api_cache_hits_total Respuestas servidas desde la cache.\n"
            "# TYPE api_cache_hits_total counter\n"
            f"api_cache_hits_total {m['cache_hits']}\n"
            "# HELP api_cache_misses_total Respuestas que tuvieron que ir a la base.\n"
            "# TYPE api_cache_misses_total counter\n"
            f"api_cache_misses_total {m['cache_misses']}\n"
            "# HELP api_uptime_segundos Segundos desde el arranque del proceso.\n"
            "# TYPE api_uptime_segundos gauge\n"
            f"api_uptime_segundos {round(time.time() - INICIO, 1)}\n"
        )
        self.responder(200, texto, "text/plain; version=0.0.4; charset=utf-8")


if __name__ == "__main__":
    threading.Thread(target=arrancar, daemon=True).start()
    print(f"api escuchando en :{PUERTO}", flush=True)
    ThreadingHTTPServer(("", PUERTO), Manejador).serve_forever()
