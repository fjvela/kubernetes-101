# reports — el informe de ventas nocturno (CronJob)
FROM python:3.14-alpine

RUN addgroup -g 30001 -S tienda && adduser -u 30001 -S -G tienda tienda

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generar-informe.py /usr/local/bin/generar-informe

USER 30001
ENTRYPOINT ["python", "/usr/local/bin/generar-informe"]
