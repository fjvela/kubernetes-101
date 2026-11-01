# api — backend de la tienda
FROM python:3.15-alpine

# Usuario sin privilegios: el securityContext del libro exige runAsNonRoot,
# y el kubelet necesita un UID numérico para poder comprobarlo.
RUN addgroup -g 30001 -S tienda && adduser -u 30001 -S -G tienda tienda

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./

USER 30001
EXPOSE 8080

ENV APP_PORT=8080 \
    APP_VERSION=2.1.0 \
    PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
