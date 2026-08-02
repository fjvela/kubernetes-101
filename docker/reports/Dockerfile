# reports — el informe de ventas nocturno (CronJob)
FROM python:3.12-alpine

RUN addgroup -g 30001 -S tienda && adduser -u 30001 -S -G tienda tienda

WORKDIR /app
RUN pip install --no-cache-dir "psycopg[binary]==3.2.3"
COPY generar-informe.py /usr/local/bin/generar-informe

USER 30001
ENTRYPOINT ["python", "/usr/local/bin/generar-informe"]
