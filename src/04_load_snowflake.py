"""
Paso 3 - Carga del modelo gold en Snowflake.

Lee los CSV de data/gold/ (generados por src/03_build_gold.py), crea el
esquema en Snowflake si no existe (sql/ddl_gold.sql) y carga las 4
dimensiones + la tabla de hechos.

Se puede ejecutar varias veces sin duplicar filas: cada tabla se vacia
(TRUNCATE) justo antes de volver a cargarla.

Credenciales: se leen de variables de entorno (ver .env.example).
"""

import os
import sys
from pathlib import Path

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas

ROOT_DIR = Path(__file__).resolve().parent.parent
GOLD_DIR = ROOT_DIR / "data" / "gold"
DDL_FILE = ROOT_DIR / "sql" / "ddl_gold.sql"


TABLAS = [
    ("dim_fecha", "dim_fecha.csv"),
    ("dim_empresa", "dim_empresa.csv"),
    ("dim_area", "dim_area.csv"),
    ("dim_tipo_contrato", "dim_tipo_contrato.csv"),
    ("fact_contratos", "fact_contratos.csv"),
]

VARS_REQUERIDAS = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
]


def _conectar():
    load_dotenv(ROOT_DIR / ".env")
    faltan = [v for v in VARS_REQUERIDAS if not os.environ.get(v)]
    if faltan:
        print(f"Faltan variables de entorno en .env: {', '.join(faltan)}")
        sys.exit(1)

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
    )


def _crear_esquema(conn):
    ddl = DDL_FILE.read_text(encoding="utf-8")
    for cur in conn.execute_string(ddl):
        cur.fetchall()
    print("Esquema creado/verificado (CREATE TABLE IF NOT EXISTS).")


def _cargar_tabla(conn, nombre_tabla: str, fichero_csv: str):
    df = pd.read_csv(GOLD_DIR / fichero_csv)

    cur = conn.cursor()
    try:
        cur.execute(f"TRUNCATE TABLE IF EXISTS {nombre_tabla}")
    finally:
        cur.close()

    exito, n_chunks, n_filas, _ = write_pandas(conn, df, nombre_tabla.upper(), quote_identifiers=False)
    if not exito:
        raise RuntimeError(f"Fallo al cargar {nombre_tabla}")
    print(f"  {nombre_tabla}: {n_filas} filas cargadas ({n_chunks} chunk(s))")


def _controles_post_carga(conn):
    print()
    print("=== Controles post-carga (ejecutados en Snowflake) ===")
    cur = conn.cursor()
    try:
        for nombre_tabla, _ in TABLAS:
            cur.execute(f"SELECT COUNT(*) FROM {nombre_tabla}")
            total = cur.fetchone()[0]
            print(f"  {nombre_tabla}: {total} filas")

        print()
        print("  Nulos en claves foraneas de fact_contratos (deben ser 0):")
        cur.execute(
            """
            SELECT
                SUM(IFF(fecha_key IS NULL, 1, 0))         AS fecha_null,
                SUM(IFF(empresa_key IS NULL, 1, 0))       AS empresa_null,
                SUM(IFF(area_key IS NULL, 1, 0))          AS area_null,
                SUM(IFF(tipo_contrato_key IS NULL, 1, 0)) AS tipo_null
            FROM fact_contratos
            """
        )
        fecha_n, empresa_n, area_n, tipo_n = cur.fetchone()
        print(f"    fecha_key={fecha_n}  empresa_key={empresa_n}  area_key={area_n}  tipo_contrato_key={tipo_n}")

        print()
        print("  Integridad referencial (filas de fact_contratos sin dimension correspondiente, deben ser 0):")
        for columna, tabla_dim, clave_dim in [
            ("fecha_key", "dim_fecha", "fecha_key"),
            ("empresa_key", "dim_empresa", "empresa_key"),
            ("area_key", "dim_area", "area_key"),
            ("tipo_contrato_key", "dim_tipo_contrato", "tipo_contrato_key"),
        ]:
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM fact_contratos f
                LEFT JOIN {tabla_dim} d ON f.{columna} = d.{clave_dim}
                WHERE d.{clave_dim} IS NULL
                """
            )
            huerfanas = cur.fetchone()[0]
            print(f"    {columna} -> {tabla_dim}: {huerfanas} filas huerfanas")

        print()
        print("  Duplicados exactos en fact_contratos (deben ser 0):")
        cur.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT expediente, empresa_key, importe_con_iva, fecha_key, objeto, COUNT(*) AS n
                FROM fact_contratos
                GROUP BY expediente, empresa_key, importe_con_iva, fecha_key, objeto
                HAVING COUNT(*) > 1
            )
            """
        )
        print(f"    grupos duplicados: {cur.fetchone()[0]}")
    finally:
        cur.close()


def main():
    conn = _conectar()
    try:
        _crear_esquema(conn)
        print()
        print("Cargando tablas...")
        for nombre_tabla, fichero_csv in TABLAS:
            _cargar_tabla(conn, nombre_tabla, fichero_csv)
        _controles_post_carga(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
