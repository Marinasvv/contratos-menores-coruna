"""
Paso 3 (parte 1) - Construccion del modelo en estrella ("gold").

Lee la tabla limpia (data/processed/contratos_menores_limpio.csv, generada
por src/02_clean.py) y construye las 4 dimensiones + la tabla de hechos,
listas para cargar en Snowflake. Guarda cada una como CSV en data/gold/.

Se puede ejecutar varias veces: cada ejecucion sobrescribe los ficheros de
salida en vez de acumular filas duplicadas.

Grano del hecho: una fila por linea de contrato publicada (expediente +
adjudicatario + importe). Ver README para la justificacion completa.
"""

from pathlib import Path

import numpy as np
import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
GOLD_DIR = Path(__file__).resolve().parent.parent / "data" / "gold"
IN_FILE = PROCESSED_DIR / "contratos_menores_limpio.csv"

NO_DISPONIBLE = "no disponible"
CLAVE_NO_DISPONIBLE = -1

# Letra inicial del NIF/CIF espanol -> forma juridica. Tabla estandar de la
# AEAT para personas juridicas; un NIF que empieza por digito es DNI
# (persona fisica). No es exhaustiva para todas las letras residuales, pero
# cubre las que aparecen realmente en este dataset (ver comprobacion mas
# abajo, FORMA_JURIDICA_NO_MAPEADA).
FORMA_JURIDICA_POR_LETRA = {
    "A": "Sociedad Anonima",
    "B": "Sociedad Limitada",
    "C": "Sociedad Colectiva",
    "D": "Sociedad Comanditaria",
    "E": "Comunidad de Bienes",
    "F": "Sociedad Cooperativa",
    "G": "Asociacion",
    "H": "Comunidad de Propietarios",
    "J": "Sociedad Civil",
    "N": "Entidad Extranjera",
    "P": "Corporacion Local",
    "Q": "Organismo Publico",
    "R": "Congregacion Religiosa",
    "S": "Organo de la Administracion",
    "U": "Union Temporal de Empresas",
    "V": "Otros Tipos",
    "W": "Establecimiento Permanente de Entidad Extranjera",
    "X": "Persona Fisica Extranjera (NIE)",
    "Y": "Persona Fisica Extranjera (NIE)",
    "Z": "Persona Fisica Extranjera (NIE)",
}

UMBRAL_SIN_IVA_POR_TIPO = {
    # art. 118.1 LCSP (ver README): 40.000 obras, 15.000 servicios/suministros.
    # "Otros" se trata como servicios/suministros a falta de una categoria
    # legal propia. "Privado" y "Concesion de obras publicas" no tienen un
    # umbral de contrato menor aplicable en el mismo sentido -> se deja sin
    # umbral (NULL)
    "Obras": 40000.0,
    "Servicios": 15000.0,
    "Suministros": 15000.0,
    "Otros": 15000.0,
    "Privado": None,
    "Concesion de obras publicas": None,
    NO_DISPONIBLE: None,
}

FECHA_INICIO = pd.Timestamp("2019-01-01")
FECHA_FIN = pd.Timestamp("2021-12-31")

# Fechas oficiales de los dos estados de alarma COVID en España
INICIO_ESTADO_ALARMA = pd.Timestamp("2020-03-14")
FIN_ESTADO_ALARMA = pd.Timestamp("2021-05-09")


def _forma_juridica(nif: str) -> str:
    if nif == "*" or nif == NO_DISPONIBLE:
        return NO_DISPONIBLE
    primera = nif[0].upper()
    if primera.isdigit():
        return "Persona Fisica (DNI)"
    return FORMA_JURIDICA_POR_LETRA.get(primera, "Forma juridica no identificada")


def _tipo_persona(nif: str) -> str:
    if nif == "*":
        return "Persona fisica anonimizada"
    if nif == NO_DISPONIBLE:
        return NO_DISPONIBLE
    if nif[0].isdigit():
        return "Persona fisica identificada"
    return "Persona juridica"


def build_dim_empresa(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, int, int]:
    """Construye dim_empresa con clave hibrida (ver README, seccion Snowflake):
    - NIF real (!= "*")        -> identidad = NIF (el nombre puede traer
      typos/variantes y no es fiable como clave; el NIF si lo es).
    - NIF "*" (anonimizado)    -> identidad = NIF + nombre (el NIF no
      distingue a las 953 personas distintas que lo comparten; el nombre,
      ya normalizado en la limpieza, es la unica informacion que si lo hace).
    """
    tmp = df[["nif", "empresa_adjudicataria"]].copy()
    tmp["identidad"] = np.where(
        tmp["nif"] == "*",
        tmp["nif"] + "||" + tmp["empresa_adjudicataria"],
        tmp["nif"],
    )

    # Controles de calidad que justifican la clave hibrida
    reales = tmp[tmp["nif"] != "*"]
    nifs_con_varios_nombres = reales.groupby("nif")["empresa_adjudicataria"].nunique()
    n_nifs_ambiguos = int((nifs_con_varios_nombres > 1).sum())
    n_nombres_bajo_asterisco = int(tmp[tmp["nif"] == "*"]["empresa_adjudicataria"].nunique())

    agg = (
        tmp.groupby("identidad")
        .agg(nif=("nif", "first"), nombre_normalizado=("empresa_adjudicataria", "first"))
        .reset_index()
    )
    agg["tipo_persona"] = agg["nif"].apply(_tipo_persona)
    agg["forma_juridica"] = agg["nif"].apply(_forma_juridica)
    agg = agg.sort_values("identidad").reset_index(drop=True)
    agg["empresa_key"] = agg.index + 1

    fila_no_disponible = pd.DataFrame(
        [
            {
                "identidad": NO_DISPONIBLE,
                "nif": NO_DISPONIBLE,
                "nombre_normalizado": NO_DISPONIBLE,
                "tipo_persona": NO_DISPONIBLE,
                "forma_juridica": NO_DISPONIBLE,
                "empresa_key": CLAVE_NO_DISPONIBLE,
            }
        ]
    )
    dim = pd.concat([fila_no_disponible, agg], ignore_index=True)

    mapa = agg.set_index("identidad")["empresa_key"]
    empresa_key_por_fila = tmp["identidad"].map(mapa)

    dim = dim[["empresa_key", "nif", "nombre_normalizado", "tipo_persona", "forma_juridica"]]
    return dim, empresa_key_por_fila, n_nifs_ambiguos, n_nombres_bajo_asterisco


def build_dim_area(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    areas = sorted(df["area_departamento"].dropna().unique())
    areas = [a for a in areas if a != NO_DISPONIBLE]
    dim = pd.DataFrame({"area_departamento": areas})
    dim["area_key"] = dim.index + 1
    fila_no_disponible = pd.DataFrame(
        [{"area_departamento": NO_DISPONIBLE, "area_key": CLAVE_NO_DISPONIBLE}]
    )
    dim = pd.concat([fila_no_disponible, dim], ignore_index=True)[["area_key", "area_departamento"]]

    mapa = dim.set_index("area_departamento")["area_key"]
    area_key_por_fila = df["area_departamento"].map(mapa)
    return dim, area_key_por_fila


def build_dim_tipo_contrato(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    categorias = sorted(c for c in df["tipo_contrato"].unique() if c != NO_DISPONIBLE)
    dim = pd.DataFrame({"tipo_contrato": categorias})
    dim["tipo_contrato_key"] = dim.index + 1
    fila_no_disponible = pd.DataFrame(
        [{"tipo_contrato": NO_DISPONIBLE, "tipo_contrato_key": CLAVE_NO_DISPONIBLE}]
    )
    dim = pd.concat([fila_no_disponible, dim], ignore_index=True)
    dim["umbral_sin_iva"] = dim["tipo_contrato"].map(UMBRAL_SIN_IVA_POR_TIPO)
    dim = dim[["tipo_contrato_key", "tipo_contrato", "umbral_sin_iva"]]

    mapa = dim.set_index("tipo_contrato")["tipo_contrato_key"]
    tipo_key_por_fila = df["tipo_contrato"].map(mapa)
    return dim, tipo_key_por_fila


def build_dim_fecha() -> pd.DataFrame:
    fechas = pd.date_range(FECHA_INICIO, FECHA_FIN, freq="D")
    dim = pd.DataFrame({"fecha": fechas})
    dim["fecha_key"] = dim["fecha"].dt.strftime("%Y%m%d").astype(int)
    dim["anio"] = dim["fecha"].dt.year
    dim["trimestre"] = dim["fecha"].dt.quarter
    dim["mes"] = dim["fecha"].dt.month
    dim["nombre_mes"] = dim["fecha"].dt.month_name(locale=None)
    dim["dia_semana"] = dim["fecha"].dt.day_name(locale=None)
    dim["periodo_covid"] = np.where(
        dim["fecha"] < INICIO_ESTADO_ALARMA,
        "Pre-COVID",
        np.where(dim["fecha"] <= FIN_ESTADO_ALARMA, "Estado de alarma", "Post-estado de alarma"),
    )
    fila_no_disponible = pd.DataFrame(
        [
            {
                "fecha_key": CLAVE_NO_DISPONIBLE,
                "fecha": pd.NaT,
                "anio": None,
                "trimestre": None,
                "mes": None,
                "nombre_mes": NO_DISPONIBLE,
                "dia_semana": NO_DISPONIBLE,
                "periodo_covid": NO_DISPONIBLE,
            }
        ]
    )
    dim = pd.concat([fila_no_disponible, dim], ignore_index=True)
    return dim[
        ["fecha_key", "fecha", "anio", "trimestre", "mes", "nombre_mes", "dia_semana", "periodo_covid"]
    ]


def build_fact(df: pd.DataFrame, empresa_key, area_key, tipo_key, dim_tipo: pd.DataFrame) -> pd.DataFrame:
    fact = df.copy()
    fecha = pd.to_datetime(fact["fecha_adjudicacion"])
    # Si la fecha de adjudicacion cae fuera del periodo declarado (2019-2021),
    # se trata como "no disponible" en vez de ampliar dim_fecha por un caso
    # aislado. Caso real: expediente GEY/2019/18, fecha 2018-01-15 (un anio
    # antes de nuestro periodo), publicado igualmente en el fichero de T1
    # 2019 - el trimestre/anio de publicacion siguen correctos para
    # trazabilidad, solo se pierde la fecha exacta para el eje temporal.
    fecha_en_rango = fecha.notna() & (fecha >= FECHA_INICIO) & (fecha <= FECHA_FIN)
    fact["fecha_key"] = np.where(
        fecha_en_rango,
        fecha.dt.strftime("%Y%m%d"),
        None,
    )
    fact["fecha_key"] = fact["fecha_key"].fillna(str(CLAVE_NO_DISPONIBLE)).astype(int)
    fact["empresa_key"] = empresa_key.fillna(CLAVE_NO_DISPONIBLE).astype(int)
    fact["area_key"] = area_key.fillna(CLAVE_NO_DISPONIBLE).astype(int)
    fact["tipo_contrato_key"] = tipo_key.fillna(CLAVE_NO_DISPONIBLE).astype(int)

    fact["importe_con_iva"] = fact["importe"]
    fact["importe_sin_iva_estimado"] = (fact["importe"] / 1.21).round(2)

    umbral = fact["tipo_contrato_key"].map(dim_tipo.set_index("tipo_contrato_key")["umbral_sin_iva"])
    fact["supera_umbral"] = fact["importe_sin_iva_estimado"] > umbral
    fact["cerca_umbral"] = (fact["importe_sin_iva_estimado"] >= 0.9 * umbral) & ~fact["supera_umbral"]
    # Si no hay umbral aplicable (Privado, Concesion, no disponible) ninguno
    # de los dos indicadores tiene sentido: se deja en False, no en NULL,
    # porque son flags booleanos de "hecho detectado", no un dato ausente.
    fact.loc[umbral.isna(), ["supera_umbral", "cerca_umbral"]] = False

    fact = fact.rename(columns={"anio": "anio_publicacion", "trimestre": "trimestre_publicacion"})

    columnas = [
        "fecha_key",
        "empresa_key",
        "area_key",
        "tipo_contrato_key",
        "importe_con_iva",
        "importe_sin_iva_estimado",
        "supera_umbral",
        "cerca_umbral",
        "expediente",
        "objeto",
        "anio_publicacion",
        "trimestre_publicacion",
        "fila_origen",
        "fichero_origen",
    ]
    return fact[columnas]


def main():
    df = pd.read_csv(PROCESSED_DIR / "contratos_menores_limpio.csv", dtype={"nif": str})
    df["nif"] = df["nif"].fillna(NO_DISPONIBLE)

    dim_fecha = build_dim_fecha()
    dim_empresa, empresa_key, n_nifs_ambiguos, n_nombres_asterisco = build_dim_empresa(df)
    dim_area, area_key = build_dim_area(df)
    dim_tipo, tipo_key = build_dim_tipo_contrato(df)
    fact = build_fact(df, empresa_key, area_key, tipo_key, dim_tipo)

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    dim_fecha.to_csv(GOLD_DIR / "dim_fecha.csv", index=False)
    dim_empresa.to_csv(GOLD_DIR / "dim_empresa.csv", index=False)
    dim_area.to_csv(GOLD_DIR / "dim_area.csv", index=False)
    dim_tipo.to_csv(GOLD_DIR / "dim_tipo_contrato.csv", index=False)
    fact.to_csv(GOLD_DIR / "fact_contratos.csv", index=False)

    print("=== Justificacion de la clave hibrida en dim_empresa ===")
    print(f"  Filas con NIF = '*': {(df['nif'] == '*').sum()}")
    print(f"  Nombres distintos bajo NIF='*': {n_nombres_asterisco}  (si se usara solo NIF, se perderian estas identidades)")
    print(f"  NIFs reales con mas de un nombre distinto: {n_nifs_ambiguos}  (si se usara NIF+nombre, se partirian estas personas)")
    print()

    print("=== Controles de conteo ===")
    print(f"  Filas en silver (contratos_menores_limpio.csv): {len(df)}")
    print(f"  Filas en fact_contratos: {len(fact)}")
    assert len(df) == len(fact), "El hecho debe tener el mismo numero de filas que la capa silver (mismo grano)"
    print(f"  dim_fecha: {len(dim_fecha)} filas ({(FECHA_FIN - FECHA_INICIO).days + 1} dias + 1 'no disponible')")
    print(f"  dim_empresa: {len(dim_empresa)} filas")
    print(f"  dim_area: {len(dim_area)} filas")
    print(f"  dim_tipo_contrato: {len(dim_tipo)} filas")
    print()

    print("=== Controles de nulos en claves foraneas (deben ser 0: nunca NULL, usan -1) ===")
    for col in ["fecha_key", "empresa_key", "area_key", "tipo_contrato_key"]:
        print(f"  {col} nulos: {fact[col].isna().sum()}")
    print()

    print("=== Controles de duplicados ===")
    duplicados_fact = fact.duplicated(
        subset=["expediente", "empresa_key", "importe_con_iva", "fecha_key", "objeto"]
    ).sum()
    print(f"  Filas de fact_contratos duplicadas en todo su contenido de negocio: {duplicados_fact}")
    print()

    print("=== Controles de integridad referencial (filas sin dimension correspondiente, deben ser 0) ===")
    print(f"  fecha_key -> dim_fecha: {(~fact['fecha_key'].isin(dim_fecha['fecha_key'])).sum()}")
    print(f"  empresa_key -> dim_empresa: {(~fact['empresa_key'].isin(dim_empresa['empresa_key'])).sum()}")
    print(f"  area_key -> dim_area: {(~fact['area_key'].isin(dim_area['area_key'])).sum()}")
    print(f"  tipo_contrato_key -> dim_tipo_contrato: {(~fact['tipo_contrato_key'].isin(dim_tipo['tipo_contrato_key'])).sum()}")
    print()

    print(f"Guardado en: {GOLD_DIR}")


if __name__ == "__main__":
    main()
