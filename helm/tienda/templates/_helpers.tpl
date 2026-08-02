{{/*
  Nombre completo de una imagen propia: registro + prefijo + repositorio + tag.
  El prefijo está vacío por defecto (nombres del libro: `tienda/web:1.4.2`) y
  vale `tienda-` cuando publicas en un registro real, que es como las nombra
  .github/workflows/imagenes.yaml: `ghcr.io/tuusuario/tienda-web:1.4.2`.
*/}}
{{- define "tienda.imagen" -}}
{{- printf "%s/%s%s:%s" .registro (.prefijo | default "") .repo .tag -}}
{{- end -}}

{{/* Labels comunes a todo lo que despliega el chart. */}}
{{- define "tienda.labels" -}}
app.kubernetes.io/part-of: tienda
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}
