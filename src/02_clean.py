"""
Paso 2 - Limpieza y transformación.

Lee la tabla "bronce" (data/processed/bronze_contratos_menores.csv, generada
por src/01_extract.py) y produce una tabla limpia y tipada en
data/processed/contratos_menores_limpio.csv, con una fila por línea de
contrato menor (expediente + adjudicatario + importe).

Se puede ejecutar varias veces: cada ejecución sobrescribe el fichero de
salida en vez de acumular filas duplicadas.

Las tres decisiones de limpieza (ver README para el detalle con ejemplos
reales de los datos):
  1. Cambios de tipos y formatos: fecha a datetime, importe a numerico
     (el origen mezcla "1234.56" y "1.234,56 e"), tipo_contrato unificado
     (letras A/E/C/Z en 2019-2020 vs. palabras en 2021).
  2. Tratamiento de nulos: se distingue entre "no disponible" (el dato no
     existe en el origen) y NIF "*" (persona fisica anonimizada a proposito
     por la propia fuente, no es un hueco).
  3. Duplicados: solo se elimina una fila si es idéntica en TODAS las
     columnas de negocio. No se usa el expediente como clave unica porque
     un mismo expediente puede repartirse en varias lineas legitimas con
     distintos adjudicatarios (p. ej. varios vecinos de una comunidad
     facturados por el mismo importe en el expediente 106/2020/72).
"""

import re
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
IN_FILE = PROCESSED_DIR / "bronze_contratos_menores.csv"
OUT_FILE = PROCESSED_DIR / "contratos_menores_limpio.csv"

NO_DISPONIBLE = "no disponible"

# A partir de la subcabecera de los .ods ("A Obras, E Servicios, C
# Suministros, Z Otros") y de las palabras usadas tal cual en 2021.
TIPO_CONTRATO_MAP = {
    "a": "Obras",
    "e": "Servicios",
    "c": "Suministros",
    "z": "Otros",
    "obras": "Obras",
    "servicios": "Servicios",
    "suministro": "Suministros",
    "suministros": "Suministros",
    "otros": "Otros",
    "privado": "Privado",
    "concesion obras publicas": "Concesion de obras publicas",
}

BUSINESS_COLUMNS = [
    "expediente",
    "fecha_adjudicacion",
    "area_departamento",
    "objeto",
    "nif",
    "empresa_adjudicataria",
    "importe",
    "tipo_contrato",
    "anio",
    "trimestre",
]


# Correccion puntual de un alta duplicada por error de tecleo (revisado a
# mano: expediente 105/2020/1266, T1 2020, filas 555 y 557 del .ods
# original -> misma fecha, mismo NIF, mismo importe y la misma factura
# "2019/25" en el objeto; solo cambia "SERVICIO" por "SERVICIOS"). Se
# normaliza aqui, antes del filtro de duplicados, para que las dos filas
# queden identicas y la regla de "fila idéntica en todo" se encargue de
# eliminar la repetida. No es una regla generica de nombres parecidos:
# es una correccion especifica para este caso ya verificado a mano.
NOMBRE_EMPRESA_CORRECCIONES = {
    "SERVICIO DE HOSTELERIA OLLOMOL S.L.": "SERVICIOS DE HOSTELERIA OLLOMOL S.L.",
}

_PATRON_MILES_SIN_COMA = re.compile(r"^\d{1,3}(\.\d{3})+\.\d{2}$")


def _parse_importe(valor):
    """Normaliza importes que llegan como '1234.56' o '1.234,56 €'."""
    if pd.isna(valor):
        return pd.NA
    s = str(valor).strip()
    s = s.replace("€", "").replace("EUR", "").strip()
    s = s.replace(" ", "")
    if "," in s and "." in s:
        # formato espanol: el punto es separador de miles, la coma es decimal
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif _PATRON_MILES_SIN_COMA.match(s):
        # Caso puntual (expediente AD0/2021/130): "9.399.28" sin ninguna
        # coma. La agrupacion en grupos de 3 digitos + 2 decimales finales
        # coincide exactamente con el formato espanol de moneda; el unico
        # error es que el separador decimal es un punto en vez de una coma
        # (un solo caracter mal tecleado, igual que el caso de la fecha
        # "08/082019"). Se reconstruye uniendo los grupos de miles y usando
        # los 2 ultimos digitos como decimales.
        grupos = s.split(".")
        s = "".join(grupos[:-1]) + "." + grupos[-1]
    try:
        return float(s)
    except ValueError:
        return pd.NA


def _parse_fecha(serie: pd.Series) -> pd.Series:
    """La mayoría de ficheros guardan la fecha como 'YYYY-MM-DD HH:MM:SS',
    pero algunas filas de 2019 (T1 y T3) la traen como texto 'DD/MM/YYYY'.
    Se intenta primero el formato habitual y, para lo que quede sin
    convertir, se reintenta interpretando el día primero.
    """
    fecha = pd.to_datetime(serie, errors="coerce")
    pendientes = fecha.isna() & serie.notna()
    if pendientes.any():
        fecha_dayfirst = pd.to_datetime(serie[pendientes], errors="coerce", dayfirst=True)
        fecha.loc[pendientes] = fecha_dayfirst

    # Caso puntual (expediente 231/2019/290): "08/082019" en vez de
    # "08/08/2019". A diferencia del importe "9.399.28 €" (ambiguo, varias
    # lecturas posibles), aqui solo falta UN caracter (la barra entre mes y
    # anio) y solo hay una reconstruccion razonable, asi que se recupera.
    pendientes = fecha.isna() & serie.notna()
    if pendientes.any():
        reconstruida = serie[pendientes].str.replace(
            r"^(\d{2})/(\d{2})(\d{4})$", r"\1/\2/\3", regex=True
        )
        fecha.loc[pendientes] = pd.to_datetime(reconstruida, errors="coerce", dayfirst=True)
    return fecha


def _normalize_tipo_contrato(valor):
    if pd.isna(valor):
        return NO_DISPONIBLE
    v = str(valor).strip().lower()
    # quita acentos sueltos que llegaron mal codificados en el origen
    v = v.replace("ó", "o").replace("ú", "u")
    return TIPO_CONTRATO_MAP.get(v, str(valor).strip())


def _normalize_nif(valor):
    if pd.isna(valor):
        return NO_DISPONIBLE
    v = str(valor).strip()
    return v  # "*" se deja tal cual: es una anonimizacion deliberada de la fuente, no un hueco


def clean() -> pd.DataFrame:
    df = pd.read_csv(IN_FILE, dtype=str)

    df = df.rename(
        columns={
            "referencia": "expediente",
            "area_tramitadora": "area_departamento",
            "nombre_adjudicatario": "empresa_adjudicataria",
        }
    )

    # 1. Tipos y formatos
    df["empresa_adjudicataria"] = df["empresa_adjudicataria"].str.strip()
    df["empresa_adjudicataria"] = df["empresa_adjudicataria"].replace(NOMBRE_EMPRESA_CORRECCIONES)
    df["fecha_adjudicacion"] = _parse_fecha(df["fecha_adjudicacion"])
    df["importe"] = df["importe"].apply(_parse_importe)
    df["tipo_contrato"] = df["tipo_contrato"].apply(_normalize_tipo_contrato)
    df["anio"] = df["anio"].astype(int)
    df["trimestre"] = df["trimestre"].astype(int)

    # 2. Nulos: texto -> "no disponible" si realmente falta (no para el NIF
    # marcado con "*", que es una anonimizacion intencionada de la fuente).
    df["nif"] = df["nif"].apply(_normalize_nif)
    for col in ["expediente", "objeto", "area_departamento", "empresa_adjudicataria"]:
        df[col] = df[col].fillna(NO_DISPONIBLE)
    # importe y fecha son numericos/fecha: si faltan se deja nulo (NaN/NaT)
    # y se documenta el recuento en vez de inventar un valor.

    # 3. Duplicados: solo fila idéntica en todas las columnas de negocio.
    before = len(df)
    df = df.drop_duplicates(subset=BUSINESS_COLUMNS, keep="first")
    removed = before - len(df)

    df = df.sort_values(["anio", "trimestre", "expediente"]).reset_index(drop=True)
    return df, removed


def main():
    df, removed = clean()
    df.to_csv(OUT_FILE, index=False, encoding="utf-8")

    print(f"Filas de entrada (bronce): {removed + len(df)}")
    print(f"Duplicados exactos eliminados: {removed}")
    print(f"Filas finales: {len(df)}")
    print()
    print("Nulos tras limpieza:")
    print(f"  importe sin valor: {df['importe'].isna().sum()}")
    print(f"  fecha sin valor:   {df['fecha_adjudicacion'].isna().sum()}")
    print(f"  tipo_contrato = '{NO_DISPONIBLE}': {(df['tipo_contrato'] == NO_DISPONIBLE).sum()}")
    print(f"  nif anonimizado ('*'): {(df['nif'] == '*').sum()}")
    print(f"  nif = '{NO_DISPONIBLE}': {(df['nif'] == NO_DISPONIBLE).sum()}")
    print()
    print(f"Guardado en: {OUT_FILE}")


if __name__ == "__main__":
    main()
