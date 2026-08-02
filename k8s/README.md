# k8s — los manifiestos tal como salen del libro

Aquí no hay plantillas ni capas: es el YAML que aparece impreso, con los mismos
nombres, los mismos puertos y las mismas etiquetas. Si estás leyendo un capítulo
y quieres el fichero entero, es este directorio.

## Orden

Los ficheros van numerados porque el orden importa:

| Fichero | Qué crea |
|---|---|
| `00-namespaces.yaml` | `tienda`, `plataforma` y `observabilidad` |
| `10-config.yaml` | el ConfigMap `web-config` y el Secret `db-credentials` |
| `20-db.yaml` | el Service headless y el StatefulSet `db` |
| `30-cache.yaml` | el Service y el Deployment `cache` |
| `40-api.yaml` | la ServiceAccount, el Service y el Deployment `api` |
| `50-web.yaml` | el Service, el Deployment y el PDB de `web` |
| `60-agent.yaml` | el DaemonSet `agent` y su RBAC |
| `70-entrada.yaml` | el Ingress de `web` |
| `80-tareas.yaml` | `backups`, `reports` y el `holgazan` |
| `90-politicas.yaml` | ResourceQuota, LimitRange y NetworkPolicies |
| `91-escalado.yaml` | el HPA de `api` |
| `opcional/` | Gateway API y VPA, que necesitan controladores aparte |

## Aplicar

```bash
kubectl apply -f k8s/            # respeta el orden de los números
kubectl apply -k k8s/            # o de una vez, con kustomize
```

## Qué necesita el clúster

- **Nada** para el núcleo: `db`, `cache`, `api`, `web`, `agent` y las tareas.
- Un **Ingress Controller** para `70-entrada.yaml`.
- **metrics-server** para `91-escalado.yaml` (si no, el HPA se queda en `<unknown>`).
- Las **CRD de Gateway API** y un controlador para `opcional/gateway.yaml`.
- El **controlador de VPA** para `opcional/vpa.yaml`.

Todo lo demás funciona en un kind recién creado.

## Un detalle sobre las imágenes

Los manifiestos usan `tienda/web:1.4.2` y compañía, que son los nombres del
libro y no existen en ningún registro público. Tienes dos caminos:

1. Construirlas y cargarlas en kind (ver el README principal). Como llevan
   `imagePullPolicy: IfNotPresent`, el kubelet las encuentra sin salir a Internet.
2. Usar `kustomize/overlays/prod`, que reescribe los nombres para apuntar a
   `ghcr.io`.
