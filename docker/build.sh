#!/usr/bin/env bash
# Construye, publica y carga en kind las cuatro imágenes propias de la tienda.
#
#   ./build.sh                                    los nombres del libro (tienda/*)
#   ./build.sh --kind                             y las mete en el clúster de kind
#   REGISTRO=ghcr.io/tuusuario ./build.sh --push
#   MOTOR=podman ./build.sh --kind                forzando el motor
#
# Funciona igual con docker y con podman. Si no dices cuál, usa el que
# encuentre: docker primero por ser el del libro, podman si no hay docker.
set -euo pipefail

cd "$(dirname "$0")"

uso() {
  sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
}

# ────────────────────────────────────────────────────────────────── argumentos
PUSH=no
KIND=no
while [ $# -gt 0 ]; do
  case "$1" in
    --push) PUSH=si ;;
    --kind) KIND=si ;;
    -h|--help) uso; exit 0 ;;
    *) echo "Opción desconocida: $1" >&2; echo >&2; uso >&2; exit 1 ;;
  esac
  shift
done

# ─────────────────────────────────────────────────────────────────── el motor
# docker y podman aceptan las mismas órdenes para build y para push, así que
# basta con decidir a cuál se llama. Donde sí se separan los caminos es en kind.
if [ -z "${MOTOR:-}" ]; then
  if command -v docker >/dev/null 2>&1; then
    MOTOR=docker
  elif command -v podman >/dev/null 2>&1; then
    MOTOR=podman
  else
    echo "No encuentro ni docker ni podman en el PATH." >&2
    exit 1
  fi
fi

if ! command -v "$MOTOR" >/dev/null 2>&1; then
  echo "MOTOR=$MOTOR, pero '$MOTOR' no está instalado." >&2
  exit 1
fi

if ! "$MOTOR" info >/dev/null 2>&1; then
  echo "'$MOTOR info' falla: el motor no está respondiendo." >&2
  if [ "$MOTOR" = podman ]; then
    # Fuera de Linux, podman no corre nativo: hay una máquina virtual detrás.
    # Si no está arrancada, el primer build falla con un error de conexión que
    # no menciona la VM por ninguna parte.
    echo "Con podman fuera de Linux hace falta arrancar la VM:" >&2
    echo "  podman machine start" >&2
  fi
  exit 1
fi

# kind habla con el motor de contenedores para crear los nodos y para meterles
# imágenes dentro, y por defecto asume docker. Si construyes con podman, el
# clúster tiene que haberse creado también con podman:
#   KIND_EXPERIMENTAL_PROVIDER=podman kind create cluster --name tienda ...
if [ "$MOTOR" = podman ]; then
  export KIND_EXPERIMENTAL_PROVIDER="${KIND_EXPERIMENTAL_PROVIDER:-podman}"
fi

# ──────────────────────────────────────────────────────── registro y versiones
REGISTRO="${REGISTRO:-tienda}"
CLUSTER="${CLUSTER:-tienda}"

# Con el registro por defecto valen los nombres del libro: `tienda/web:1.4.2`.
# Con un registro propio hace falta el prefijo `tienda-`, porque en un registro
# como ghcr.io el paquete cuelga de tu usuario y `ghcr.io/tuusuario/web` sería
# un nombre demasiado genérico. Es exactamente lo que publica el workflow de
# .github/workflows/imagenes.yaml y lo que espera kustomize/overlays/prod.
if [ "$REGISTRO" = "tienda" ]; then
  PREFIJO=""
else
  PREFIJO="tienda-"
fi

# `pieza:version`, el mismo formato que el bucle de kind del README. No es un
# array asociativo a propósito: `declare -A` es de bash 4, y el bash que trae
# macOS de serie sigue siendo el 3.2, que es donde esto tiene que arrancar.
PIEZAS="web:1.4.2 api:2.1.0 reports:1.0.3 holgazan:0.9.0"

# El tar intermedio solo hace falta en el camino de podman (ver más abajo).
TMP=""
if [ "$KIND" = si ] && [ "$MOTOR" != docker ]; then
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
fi

echo "motor: $MOTOR | registro: $REGISTRO"
echo

for entrada in $PIEZAS; do
  pieza="${entrada%%:*}"
  version="${entrada##*:}"
  tag="${REGISTRO}/${PREFIJO}${pieza}:${version}"

  echo "==> $tag"
  "$MOTOR" build -t "$tag" "./${pieza}"

  # Con `set -e`, un `[ ... ] && cmd` como última orden del bucle es un pie de
  # plomo conocido: si el test falla, la lista devuelve 1. Un if es explícito.
  if [ "$PUSH" = si ]; then
    # Con podman, autentícate antes:  podman login ghcr.io
    "$MOTOR" push "$tag"
  fi

  if [ "$KIND" = si ]; then
    if [ "$MOTOR" = docker ]; then
      kind load docker-image "$tag" --name "$CLUSTER"
    else
      # `kind load docker-image` va a buscar la imagen al demonio de Docker,
      # que con podman sencillamente no existe. El camino portable es sacarla a
      # un tar y cargar el tar: eso kind lo sabe leer venga de donde venga.
      # El `--format docker-archive` no es adorno: kind no acepta el archivo en
      # formato OCI.
      "$MOTOR" save --format docker-archive -o "$TMP/${pieza}.tar" "$tag"
      kind load image-archive "$TMP/${pieza}.tar" --name "$CLUSTER"
    fi
  fi
done

echo
if [ "$KIND" = si ]; then
  echo "Listo. Las cuatro imágenes están dentro del clúster '$CLUSTER'."
  echo "Ahora:  kubectl apply -f ../k8s/"
else
  echo "Listo. Para meterlas en el clúster de kind:  ./build.sh --kind"
fi
