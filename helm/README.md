# helm — el mismo sistema, empaquetado

```bash
helm template tienda ./tienda | less          # ver sin instalar
helm lint ./tienda                            # comprobar el chart
helm install tienda ./tienda -n tienda --create-namespace
helm upgrade tienda ./tienda -n tienda
helm uninstall tienda -n tienda
```

Si quieres el Namespace `tienda` con sus etiquetas de Pod Security Admission
—que el `--create-namespace` de Helm no pone—, créalos antes con el manifiesto
que ya está en `k8s/` y dile al chart que no cree ninguno:

```bash
kubectl apply -f ../k8s/00-namespaces.yaml
helm install tienda ./tienda -n tienda --set crearNamespacePlataforma=false
```

## Lo que se puede tocar sin editar plantillas

```bash
# apuntar a tu registro
--set global.registro=ghcr.io/TU-USUARIO

# apagar piezas que no te interesen ahora
--set holgazan.enabled=false --set agent.enabled=false

# encender el Ingress
--set ingress.enabled=true --set ingress.host=tienda.local

# entorno de desarrollo en una línea
--set web.replicas=1 --set api.replicas=1 --set cache.replicas=1 \
--set api.arranqueLentoSegundos=0
```

## Tres detalles del chart que merecen mirarse

**El chart no crea su propio Namespace, y no es un olvido.** No puede: Helm
guarda el Secret del release *dentro* del Namespace del release, y lo hace
antes de aplicar ninguna plantilla. Si no existe, la instalación falla sin
llegar a renderizar nada; y si lo creas tú a mano, Helm se niega a adoptarlo
con *«invalid ownership metadata»*. Es la pescadilla que se muerde la cola para
la que existe `--create-namespace`. `plataforma` sí lo crea el chart,
precisamente porque no es el del release.


**El `checksum/config` del Deployment de `web`.** Es una anotación calculada a
partir del ConfigMap. Sin ella, cambiar la configuración con `helm upgrade` no
reinicia nada: los Pods siguen con los valores viejos y te pasas media hora
preguntándote por qué no se aplica. Es el truco de Helm que más veces salva el día.

**El `agent` lleva `namespace:` explícito.** Todo lo demás cae en el Namespace
del release, pero el DaemonSet tiene que ir a `plataforma` porque monta el disco
del nodo. Es la excepción, y por eso es el único sitio del chart donde aparece
un Namespace escrito a mano.
