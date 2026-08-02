# web — el frontend de la tienda
#
# Se parte de nginx-unprivileged porque escucha en el 8080 y corre como usuario
# sin privilegios: es lo que exige el securityContext del capítulo de Seguridad.
FROM nginxinc/nginx-unprivileged:1.27-alpine

# En templates/, no en conf.d/: el entrypoint de la imagen pasa envsubst a todo
# lo que hay aquí y escribe el resultado en conf.d/. Es lo que hace que el
# ConfigMap `web-config` tenga efecto de verdad sobre la configuración.
#
# Y no, no se lleva por delante las variables propias de nginx: el entrypoint
# construye la lista de nombres a sustituir a partir de las variables de ENTORNO
# definidas, y `$host` o `$remote_addr` no lo son, así que envsubst ni las mira.
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY html/ /usr/share/nginx/html/

# Valor por defecto, para que la imagen funcione suelta (docker run) sin
# ConfigMap. En Kubernetes lo pisa `web-config`.
ENV API_URL=http://api:8080

USER 101
EXPOSE 8080
