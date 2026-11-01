# holgazan — pide muchos recursos y no hace nada.
# Existe para que el VerticalPodAutoscaler tenga algo que corregir.
FROM python:3.15-alpine

RUN addgroup -g 30001 -S tienda && adduser -u 30001 -S -G tienda tienda
USER 30001

CMD ["python", "-c", "import time,sys;print('holgazan en pie: pido 2 CPU y 4 GiB, y no los uso',flush=True);[time.sleep(3600) for _ in iter(int,1)]"]
