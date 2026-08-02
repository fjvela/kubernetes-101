# kustomize — el mismo sistema, con capas

Aquí no hay ni un manifiesto nuevo. `base/` apunta a `../../k8s`, y los overlays
solo declaran las diferencias. Si añades una pieza en `k8s/`, aparece sola en
los dos entornos.

```
base/                  referencia a k8s/, más labels comunes
overlays/dev/          1 réplica de todo, holgazán a dieta, arranque instantáneo
overlays/prod/         3+2+3 réplicas, imágenes en ghcr.io, reparto estricto
```

## Ver qué sale antes de aplicarlo

```bash
kustomize build overlays/dev
kustomize build overlays/prod | grep -E "image:|replicas:"
```

## Aplicar

```bash
kubectl apply -k overlays/dev
kubectl apply -k overlays/prod
```

## Las tres diferencias entre dev y prod

**Réplicas.** En dev todo va a 1. No tiene sentido gastar tres Pods de `cache`
en un portátil.

**Imágenes.** `dev` se queda con los nombres del libro (`tienda/web:1.4.2`),
que son los que construye `./docker/build.sh` en tu máquina y no salen de ahí;
`prod` reescribe el nombre entero para apuntar a `ghcr.io`. Cambiar de registro
es una línea, y está en un solo sitio: el bloque `images:` del overlay.

**El reparto de la caché.** En dev, `whenUnsatisfiable: ScheduleAnyway`: si no
caben repartidas, que arranquen igual. En prod, `DoNotSchedule`: prefiero un Pod
en `Pending` y un aviso, a tres réplicas en el mismo nodo fingiendo que hay alta
disponibilidad.

Esa última es la diferencia que más se parece a la vida real: la misma
configuración, con la tolerancia al riesgo cambiada.
