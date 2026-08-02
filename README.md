# La tienda — código del libro *Kubernetes 101*

Este repositorio **es el Apéndice B** del libro
[**Kubernetes 101**](https://www.javivela.dev/libros/kubernetes-101). El libro no
imprime el manifiesto completo, sino que apunta aquí: son más de seiscientas
líneas de YAML que nadie va a teclear desde una hoja de papel, y que aquí se
pueden clonar, aplicar, romper y arreglar, que es lo único que se puede hacer de
verdad con un manifiesto.

Es el sistema que se construye a lo largo del libro, listo para desplegar y
toquetear. No son fragmentos sueltos: es la tienda entera, funcionando.

Si has leído el libro, reconocerás todos los nombres. Si no lo has leído, esto
te sirve igual como ejemplo de una aplicación pequeña pero completa en
Kubernetes: frontend, backend, base de datos con estado, caché repartida,
agente de logs por nodo, tareas programadas, políticas de red y escalado.

---

## Las piezas

| Pieza | Qué es | Objeto | Namespace |
|---|---|---|---|
| `web` | El frontend. Sirve la página y hace de proxy hacia la API. | Deployment ×3 | `tienda` |
| `api` | El backend. Habla con la base de datos y con la caché. | Deployment ×2 | `tienda` |
| `db` | PostgreSQL. La única pieza con disco propio. | StatefulSet ×1 | `tienda` |
| `cache` | Redis. Una réplica por nodo. | Deployment ×3 | `tienda` |
| `agent` | Recoge los logs del nodo. | DaemonSet | `plataforma` |
| `backups` | Copia la base de datos y termina. | Job | `tienda` |
| `reports` | El informe de ventas, cada noche a las 03:00. | CronJob | `tienda` |
| `holgazan` | Pide 2 CPU y 4 GiB, y no usa nada. | Deployment ×1 | `tienda` |
| `gateway` | La puerta de entrada del tráfico. | Ingress (o Gateway) | `tienda` / `plataforma` |

Son nueve de las diez piezas del libro (por eso la `ResourceQuota` de aquí suma 4,2 CPU y la del libro 4,7: son los 500m del `recomendador`). Falta el `recomendador`, que pide una
GPU con Dynamic Resource Allocation: necesita hardware y un driver DRA
instalado, así que no tiene sentido dejarlo en un repositorio pensado para
arrancar en un portátil. Está en el Apéndice B del libro.

El `agent` vive en `plataforma` y no en `tienda` por un motivo concreto: monta
`/var/log` del nodo con un `hostPath`, y eso lo prohíbe el nivel `baseline` de
Pod Security Admission que protege al Namespace de la aplicación. Es el tipo de
detalle que solo aparece cuando intentas desplegar de verdad lo que has escrito.

---

## Qué hay en cada directorio

```
docker/       Cómo se construyen las cuatro imágenes propias
k8s/          Los manifiestos del libro, adaptados para arrancar en kind
kustomize/    Los mismos manifiestos, con overlays de dev y prod
helm/         Los mismos manifiestos, empaquetados como chart
```

Los tres formatos despliegan el mismo sistema. Están los tres a propósito: es
la forma más honesta de ver qué aporta cada herramienta y qué cuesta cada una.
Hay diferencias puntuales entre ellos y con el libro, y están todas listadas
más abajo en «[En qué se aparta del libro](#en-qué-se-aparta-del-libro)».

- **`k8s/`** es el suelo. YAML plano, cero magia, un fichero por pieza. Es lo
  que quieres cuando estás aprendiendo o cuando algo falla y necesitas leer
  exactamente lo que se va a aplicar.
- **`kustomize/`** no duplica nada: los overlays *referencian* los ficheros de
  `k8s/`. Cambias el original y los tres entornos se enteran. Es la respuesta a
  «quiero lo mismo pero con dos réplicas menos» sin copiar y pegar.
- **`helm/`** es lo que quieres cuando el sistema tiene que ser instalable por
  terceros, con valores, condicionales y versionado.

---

## Ponerlo en marcha

### Opción rápida: sin Kubernetes

Para comprobar que las imágenes funcionan antes de meterlas en un clúster:

```bash
cd docker
docker compose up --build
curl http://localhost:8080/api/productos
```

### En un clúster local con kind

```bash
# 1. Un clúster de tres nodos, como el mapa del libro
kind create cluster --name tienda --config kind.yaml

# 2. Construir las imágenes y meterlas dentro del clúster: kind no ve el motor
#    de contenedores de tu máquina, hay que pasarle las imágenes a mano.
./docker/build.sh --kind

# 3. Desplegar
kubectl apply -f k8s/

# 4. Mirar
kubectl get pods -n tienda -o wide
kubectl port-forward -n tienda svc/web 8080:80
# y abre http://localhost:8080
```

### Con podman en vez de docker

`docker/build.sh` funciona con los dos: si no encuentra docker usa podman, y
`MOTOR=podman ./docker/build.sh` lo fuerza. Solo hay tres cosas que cambian, y
las tres muerden en silencio si no las sabes:

```bash
# 1. Fuera de Linux, podman corre dentro de una máquina virtual. Sin esto, el
#    primer build falla con un error de conexión que no menciona la VM.
podman machine start

# 2. El clúster tiene que crearlo el mismo motor que construye las imágenes.
KIND_EXPERIMENTAL_PROVIDER=podman kind create cluster --name tienda --config -

# 3. Y ya: el script sabe que con podman `kind load docker-image` no sirve
#    —va a buscar la imagen a un demonio de Docker que no existe— y usa
#    `podman save` + `kind load image-archive`, que es el camino portable.
MOTOR=podman ./docker/build.sh --kind
```

Para la opción sin Kubernetes, `compose.yaml` vale tal cual, pero `podman
compose` necesita que tengas instalado `podman-compose` o `docker-compose`:
es un envoltorio, no una implementación propia.

### Con kustomize

```bash
kustomize build kustomize/overlays/dev  | kubectl apply -f -
kustomize build kustomize/overlays/prod | kubectl apply -f -
```

Antes de usar `prod`, cambia `TU-USUARIO` en
`kustomize/overlays/prod/kustomization.yaml` por tu usuario de GitHub.

### Con Helm

```bash
helm install tienda ./helm/tienda \
  --namespace tienda --create-namespace \
  --set global.registro=ghcr.io/TU-USUARIO \
  --set global.prefijo=tienda-
```

El chart crea `plataforma`, con su `enforce: privileged`, porque el `agent` lo
necesita. El de la tienda no: ese lo crea Helm con `--create-namespace`.

> **Un chart no puede crear el Namespace de su propio release.** Helm guarda el
> Secret del release *dentro* de ese Namespace, y lo hace antes de aplicar
> ninguna plantilla: si no existe, la instalación falla sin llegar a renderizar
> nada. Y si lo creas tú a mano por adelantado, el chart intenta crear el suyo
> encima y falla con *«invalid ownership metadata»*. Para eso existe el flag.

El precio es que el `tienda` que crea Helm nace **sin** etiquetas de Pod
Security Admission, que en el libro son media lección. Si las quieres, crea los
Namespaces tú con el manifiesto que ya está aquí y quítale al chart ese trabajo:

```bash
kubectl apply -f k8s/00-namespaces.yaml
helm install tienda ./helm/tienda \
  --namespace tienda \
  --set crearNamespacePlataforma=false
```

Para ver qué se va a aplicar sin aplicarlo:

```bash
helm template tienda ./helm/tienda | less
```

---

## Comprobar que todo está en pie

```bash
kubectl get all -n tienda
kubectl get pods -n tienda -o wide          # una réplica de cache por nodo
kubectl get pvc -n tienda                   # datos-db-0
kubectl get jobs,cronjobs -n tienda         # backups y reports
```

Lo que deberías ver: `web` con 3/3, `api` con 2/2, `cache` con una réplica por
nodo, `db` con 1/1 y su PVC en `Bound`, y `backups` como `Completed`. El CronJob
`reports` no habrá corrido todavía salvo que sean las 3 de la mañana.

Si la `db` se queda en `Pending`, es que tu clúster no aprovisiona volúmenes de
forma dinámica y hay que darle uno a mano. Es el comportamiento esperado, y
saber leer ese `Pending` es lo que enseña el capítulo de Almacenamiento.

## En qué se aparta del libro

El libro explica el sistema; este repositorio tiene que arrancarlo en un
portátil. Eso obliga a unas cuantas concesiones. Ninguna cambia lo que se
aprende, pero conviene tenerlas escritas para que no parezcan erratas.

| Punto | En el libro | Aquí | Por qué |
|---|---|---|---|
| Puerta de entrada | Gateway API | Ingress en `k8s/`, Gateway en `k8s/opcional/` | Gateway API necesita instalar los CRD y un controlador. El Ingress funciona con `kind` recién creado. |
| Service `api` | `port: 80` → `targetPort: 8080` | `port: 8080` | La aplicación real escucha en 8080 y `nginx.conf` la busca ahí. Evita una indirección que en el libro sirve para explicar, y aquí solo confunde. |
| Reparto de `cache` | `whenUnsatisfiable: DoNotSchedule` | `ScheduleAnyway` (el overlay `prod` sí usa `DoNotSchedule`) | Con menos nodos que réplicas, `DoNotSchedule` deja Pods en `Pending` para siempre. |
| Disco de `db` | 20 GiB, `storageClassName: fast-ssd` | 5 GiB, sin clase (usa la de por defecto) | `fast-ssd` no existe en un clúster local. |
| `LimitRange` | `min` 50m / 64Mi | `min` 10m / 32Mi | Para que quepa el sistema entero en un portátil. |
| Job `backups` | Sí | Solo en `k8s/` y `kustomize/`; el chart no lo incluye | Un Job de un solo uso no encaja en el ciclo de vida de un release de Helm. |
| `NetworkPolicy` de la `db` | `namespaceSelector` + `podSelector` (el ejemplo de AND), y regla de egress al puerto 53 | Solo `podSelector`, sin egress | En un clúster de un solo Namespace el `namespaceSelector` no aporta nada, y sin regla de egress declarada no se corta el DNS. El matiz del AND se explica en el libro, que es donde toca. |
| `NetworkPolicy` de la `cache` | No existe | `cache-solo-desde-api` | El libro cierra solo la `db` para no repetir el mismo ejemplo dos veces; aquí sale gratis y deja el sistema mejor cerrado. |
| Service `web` | `type: LoadBalancer` | `type: ClusterIP` | En `kind` no hay balanceador que asignar: el Service se quedaría con la IP externa en `<pending>` para siempre. Se llega desde fuera por el Ingress o con `port-forward`. |
| `LimitRange` de PVC | Segunda entrada `type: PersistentVolumeClaim` (entre 1Gi y 100Gi) | No existe | El disco de la `db` aquí son 5 GiB de la clase por defecto, y una sola entrada de tipo `Container` basta para lo que enseña el capítulo. |
| Cuota de `ResourceClaim` | `count/resourceclaims.resource.k8s.io: "2"` | Sin esa entrada | Va con el `recomendador`, que no está aquí. Sin DRA no hay ResourceClaims que contar. |
| `PriorityClass` | Tres clases (`tienda-critica`, `tienda-normal`, `tienda-relleno`) y el `globalDefault` | No existen | Son objetos de ámbito de clúster, no de Namespace: crearlos desde este repositorio contaminaría el clúster del lector fuera de `tienda`. El capítulo de Scheduling los explica y se aplican a mano. |
| Nombre del PDB | Dos alternativas, `web-pdb-min` y `web-pdb-max`, para comparar `minAvailable` con `maxUnavailable` | Uno solo, `web-pdb`, con `minAvailable: 2` | Los dos objetos del libro son excluyentes: sirven para comparar, no para aplicar a la vez. |
| Ingress en el chart | — | `ingress.enabled: false` por defecto | En `k8s/` el Ingress se crea siempre; en Helm hay que pedirlo con `--set ingress.enabled=true`, porque un chart que crea un Ingress sin controlador instalado deja un objeto que no sirve para nada. |
| Namespaces en el chart | `k8s/` crea los tres (`tienda`, `plataforma`, `observabilidad`) con sus etiquetas de PSA | El chart solo crea `plataforma`; `tienda` lo crea Helm con `--create-namespace`, sin etiquetas, y `observabilidad` no lo crea nadie | Un chart no puede crear el Namespace de su propio release (ver «[Con Helm](#con-helm)»), y `observabilidad` está reservado para lo que este repositorio no despliega: en un chart sería un Namespace vacío que aparece de la nada. |
| `ResourceQuota` de objetos | Incluye `deployments.apps` y `services.loadbalancers` | Sin esas dos entradas | En `kind` no hay LoadBalancer que contar. |
| Volumen de `backups` y `reports` | PVC dedicados (`backups-pvc`, `informes-pvc`) | `emptyDir` | Un PVC por tarea obliga a aprovisionar dos volúmenes más para ver correr un Job de treinta segundos. |
| HPA de `api` | `maxReplicas: 20` y tres métricas (CPU, memoria y una custom) | `maxReplicas: 10`, solo CPU | Las métricas custom necesitan un adaptador instalado. Con CPU basta para ver el bucle de escalado. |
| TLS de entrada | El Ingress lleva `spec.tls` con el Secret `tienda-tls` | Sin TLS, y el host es `tienda.local` | Un certificado exige o cert-manager o generarlo a mano, y no aporta nada al ejemplo. |
| `web-config` | Incluye además `app.properties` y un `nginx.conf` completo | Solo las cuatro variables | El fichero de nginx va en la imagen, que es donde tiene sentido. Las variables sí se consumen: `API_URL` sustituye el destino del proxy vía `envsubst`. |
| `db-credentials` | Incluye `db-host` y `connection-string` | Incluye `database` | Las dos primeras existen en el libro para explicar que las claves con guion no se pueden inyectar con `envFrom`. Aquí sobran, y `database` sí hace falta. |
| `updateMode` del VPA | `InPlaceOrRecreate` | `Off` | El libro enseña el modo más nuevo, que redimensiona sin reiniciar. Aquí empieza solo recomendando: mira antes de tocar, que es como se despliega un VPA la primera vez sobre algo que no conoces. |
| `minAllowed` del VPA | `100m` / `128Mi` | `50m` / `64Mi` | Va con el `min` del `LimitRange` de la fila de más arriba: si el VPA pudiera recomendar por debajo del mínimo del Namespace, la recomendación se rechazaría en la admisión. |
| `controlledValues` del VPA | `RequestsAndLimits` | Sin declarar (por defecto, `RequestsAndLimits`) | El libro lo escribe para poder explicarlo. Aquí se deja al valor por defecto, que es el mismo. |
| Volumen de escritura de `web` | `cache-estatico` montado en `/var/cache/web` | `cache-nginx` montado en `/tmp` | Va con `nginx-unprivileged` (ver «Las imágenes»): esa imagen escribe sus temporales en `/tmp`, no en `/var/cache`. El nombre cambia por lo mismo, para que se lea qué es. |

Si encuentras alguna diferencia que **no** esté en esta tabla, es un error del
repositorio: abre una issue.

---

## Comprobar que está vivo

```bash
# Las piezas en pie, y en qué nodo ha caído cada una
kubectl get pods -n tienda -o wide

# Cómo ha quedado repartida cache (con ScheduleAnyway es una preferencia,
# no una garantía; el overlay prod la convierte en obligatoria)
kubectl get pods -n tienda -l app=cache -o wide

# El disco de la base de datos
kubectl get pvc -n tienda

# Quién responde detrás del Service
kubectl run curl --rm -it --image=curlimages/curl:8.10.1 --restart=Never \
  -n tienda -- curl -s http://api:8080/api/

# La caché funcionando: la primera vez dice "db", la segunda no
kubectl run curl --rm -it --image=curlimages/curl:8.10.1 --restart=Never \
  -n tienda -- curl -s http://api:8080/api/productos
```

### Ver escalar el HPA

`api` tiene un endpoint que quema CPU a propósito:

```bash
kubectl run carga --rm -it --image=curlimages/curl:8.10.1 --restart=Never -n tienda -- \
  sh -c 'while true; do curl -s http://api:8080/api/quemar > /dev/null; done'

# en otra terminal
kubectl get hpa -n tienda -w
```

### Ver funcionar la NetworkPolicy

`web` no puede hablar con la base de datos: tiene que pasar por `api`.

```bash
kubectl exec -n tienda deploy/web -- \
  timeout 3 sh -c 'nc -z db 5432 && echo LLEGA || echo BLOQUEADO'
```

Con un CNI que implemente NetworkPolicy (Calico, Cilium), dirá `BLOQUEADO`. Con
el CNI por defecto de kind, que no las implementa, dirá `LLEGA`: la política se
crea pero nadie la aplica. Es un detalle que sorprende a mucha gente la primera
vez.

---

## Las imágenes

Cuatro son propias y se construyen aquí:

| Imagen | Base | Qué hace |
|---|---|---|
| `web` | `nginx-unprivileged:alpine` | Sirve la página y hace proxy a `/api/` |
| `api` | `python:3.12-alpine` | HTTP en Python, habla con PostgreSQL y Redis |
| `reports` | `python:3.12-alpine` | Genera el CSV del informe |
| `holgazan` | `python:3.12-alpine` | Duerme. Ese es todo su trabajo. |

Tres son públicas y se usan tal cual: `postgres:16-alpine`, `redis:7-alpine` y
`fluent/fluent-bit:3.0`.

`web` parte de **nginx-unprivileged** y no del `nginx` normal por una razón
práctica: escucha en el 8080 y corre como usuario sin privilegios, que es
justo lo que exige el `securityContext` del capítulo de Seguridad. Con la
imagen oficial de nginx, que quiere el puerto 80 y arranca como root, ese
manifiesto no llega a levantar.

El workflow de `.github/workflows/imagenes.yaml` las publica en
`ghcr.io/TU-USUARIO/tienda-*` en cada push a `main`. No necesita secretos:
le basta con el `GITHUB_TOKEN` que GitHub inyecta solo.

**Un solo criterio de nombres, en los cuatro sitios.** Sin registro, valen los
nombres del libro (`tienda/web:1.4.2`). Con un registro real, las imágenes
llevan el prefijo `tienda-`, porque en ghcr.io el paquete cuelga de tu usuario
y `ghcr.io/tuusuario/web` sería un nombre demasiado genérico:

| Camino | Cómo se le dice | Qué produce |
|---|---|---|
| `docker/build.sh` | `REGISTRO=ghcr.io/TU-USUARIO ./build.sh --push` | `ghcr.io/TU-USUARIO/tienda-web:1.4.2` |
| GitHub Actions | automático en cada push a `main` | `ghcr.io/TU-USUARIO/tienda-web:1.4.2` |
| `kustomize/overlays/prod` | `newName` en el `kustomization.yaml` | `ghcr.io/TU-USUARIO/tienda-web:1.4.2` |
| Helm | `--set global.registro=... --set global.prefijo=tienda-` | `ghcr.io/TU-USUARIO/tienda-web:1.4.2` |

---

## Lo que este repositorio no es

No es una aplicación de producción. La contraseña de la base de datos está en
un fichero, no hay TLS entre piezas, no hay copias reales de nada y el `api`
mete cuatro productos en una tabla para tener algo que enseñar. Está escrito
para que se entienda leyéndolo, no para que aguante tráfico.

Si quieres llevarte algo de aquí a un clúster de verdad, empieza por sacar el
Secret a un gestor externo (Vault, External Secrets, SOPS) y por revisar las
NetworkPolicies, que aquí solo cubren las dos rutas evidentes.

---

## Licencia

Código bajo licencia MIT. El texto del libro no: eso es otra cosa y se compra.
