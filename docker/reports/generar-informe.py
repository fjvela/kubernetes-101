#!/usr/bin/env python3
"""Genera el informe de ventas de la tienda. Lo ejecuta el CronJob `reports`."""
import argparse
import csv
import datetime
import os
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=os.environ.get("DB_HOST", "db"))
    p.add_argument("--salida", default="/informes/ventas.csv")
    args = p.parse_args()

    import psycopg
    with psycopg.connect(
        host=args.host,
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "tienda"),
        user=os.environ.get("POSTGRES_USER", "tienda"),
        password=os.environ.get("PGPASSWORD", ""),
        connect_timeout=5,
    ) as cn, cn.cursor() as cur:
        cur.execute("SELECT id, nombre, precio FROM productos ORDER BY id")
        filas = cur.fetchall()

    os.makedirs(os.path.dirname(args.salida), exist_ok=True)
    with open(args.salida, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "nombre", "precio", "generado"])
        ahora = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        for fila in filas:
            w.writerow([*fila, ahora])

    print(f"Informe generado con éxito: {args.salida} ({len(filas)} filas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
