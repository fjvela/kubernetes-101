# docker — las cuatro imágenes propias

```bash
./build.sh                                   # construye tienda/web:1.4.2, etc.
./build.sh --kind                            # y las mete en el clúster de kind
REGISTRO=ghcr.io/TU-USUARIO ./build.sh --push
docker compose up --build                    # la tienda entera, sin Kubernetes
```

## docker o podman, da igual

El script llama a `docker` si lo encuentra y a `podman` si no. `MOTOR=podman
./build.sh` fuerza el motor cuando tienes los dos.

La diferencia que importa está en `--kind`. `kind load docker-image` va a buscar
la imagen al demonio de Docker, así que con podman no encuentra nada: el build
va bien, el `load` dice que sí, y los Pods se quedan en `ErrImageNeverPull` sin
que nada apunte a la causa. El camino portable es sacar la imagen a un tar y
cargar el tar, que es lo que hace el script:

```bash
podman save --format docker-archive -o web.tar tienda/web:1.4.2
kind load image-archive web.tar --name tienda
```

Y el clúster tiene que crearlo el mismo motor:
`KIND_EXPERIMENTAL_PROVIDER=podman kind create cluster`. Si construyes con
podman sobre un kind creado con docker, las imágenes acaban en el nodo
equivocado, que es decir en ninguno.

Fuera de Linux, antes de nada: `podman machine start`.

## Qué hay dentro

**`web`** parte de `nginx-unprivileged` y no del `nginx` oficial. La diferencia
importa: escucha en el 8080 y corre como usuario sin privilegios, que es lo que
pide el `securityContext` del libro. Con la imagen oficial, que quiere el puerto
80 y arranca como root, ese Deployment no levanta.

**`api`** es Python con la librería estándar y `psycopg`. Habla con Redis
implementando el protocolo a mano (son treinta líneas) para no arrastrar otra
dependencia. Expone:

| Ruta | Para qué |
|---|---|
| `/healthz` | ¿el proceso está vivo? No mira las dependencias. → `livenessProbe` |
| `/readyz` | ¿puede atender? Sí las mira. → `readinessProbe` |
| `/metrics` | contadores en formato Prometheus |
| `/api/productos` | lee de `db`, cachea 30 s en `cache` |
| `/api/visitas` | incrementa un contador en `cache` |
| `/api/quemar` | consume CPU 5 s, para ver escalar al HPA |

La separación entre `/healthz` y `/readyz` es deliberada y es la lección
entera del capítulo de probes: si la base de datos se cae, `api` deja de estar
*lista* pero sigue *viva*. Con una liveness que mirase la base de datos,
Kubernetes reiniciaría en bucle unos Pods que no tienen nada roto.

También arranca lento a propósito (`ARRANQUE_LENTO_SEGUNDOS`, 5 por defecto).
Por eso hay una `startupProbe`: sin ella, la liveness mataría el contenedor
antes de que llegue a levantar.

**`reports`** genera el CSV del informe nocturno. **`holgazan`** duerme.
