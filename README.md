## Fuente de datos

- **Organismo:** Concello da Coruña – Portal de Transparencia
- **Página:** https://www.coruna.gal/transparencia/es/claridad-en-la-gestion/contratacion/contratos-menores?argIdioma=es
- **Formato:** hoja de cálculo. T1-T3 2019 son `.xlsx`; T4 2019 y todo 2020-2021 son `.ods`. Un fichero por trimestre.
- **Cobertura elegida:** 1 de enero de 2019 a 31 de diciembre de 2021 (3 años completos, 12 trimestres)
- **Por qué este rango:** se eligió para poder comparar un año "normal" (2019) con el año de la pandemia (2020, estado de alarma desde marzo) y el año de recuperación (2021), y así responder si la contratación de emergencia por COVID dejó huella visible en los contratos menores. Nota importante: muchas compras urgentes de material sanitario/EPIs durante 2020 se tramitaron por la vía de "contratación de emergencia" (art. 120 LCSP, RD-ley 7/2020 y 8/2020), que es un régimen distinto al de "contrato menor" y por tanto puede no aparecer en este listado — un hueco o ausencia de pico también es un resultado válido a documentar, no un fallo de los datos.
- **Base legal:** art. 63.4 de la LCSP (publicación trimestral de contratos menores)

| Fichero | Periodo | Fecha descarga | URL |
|---|---|---|---|
| 201901_Menores_1er_trimestre_2019.xlsx | T1 2019 | 20/10/2026 | https://www.coruna.gal/documentos/descarga.jsp?19396554153 |
| 201902_Menores_2__trimestre_2019.xlsx | T2 2019 | 20/10/2026 | https://www.coruna.gal/documentos/descarga.jsp?19396654144 |
| 201903_Menores_3er_trimestre_2019.xlsx | T3 2019 | 20/10/2026 | https://www.coruna.gal/documentos/descarga.jsp?19396754135 |
| 201904_Menores_4__trimestre_2019_open_document.ods | T4 2019 | 20/10/2026 | https://www.coruna.gal/documentos/descarga.jsp?19396854126 |
| 202001_PUBLICACION_MENORES_PRIMER_TRIMESTRE_2020.ods | T1 2020 | 20/10/2026 | https://www.coruna.gal/documentos/descarga.jsp?19396954117 |
| 202002_PUBLICACION_MENORES_SEGUNDO_TRIMESTRE_2020.ods | T2 2020 | 20/10/2026 | https://www.coruna.gal/documentos/descarga.jsp?19397054108 |
| 202003_PUBLICACION_MENORES_TERCER_TRIMESTRE_2020.ods | T3 2020 | 20/10/2026 | https://www.coruna.gal/documentos/descarga.jsp?19397154099 |
| 202004_PUBLICACION_MENORES_CUARTO_TRIMESTRE_2020.ods | T4 2020 | 20/10/2026 | https://www.coruna.gal/documentos/descarga.jsp?19397554063 |
| 202101_PUBLICACION_MENORES_PRIMER_TRIMESTRE_2021.ods | T1 2021 | 20/10/2026 | https://www.coruna.gal/documentos/descarga.jsp?19398054018 |
| 202102_PUBLICACION_MENORES_SEGUNDO_TRIMESTRE_2021.ods | T2 2021 | 20/10/2026 | https://www.coruna.gal/documentos/descarga.jsp?19398154009 |
| 202103_PUBLICACION_MENORES_TERCEIRO_TRIMESTRE_2021.ods | T3 2021 | 20/10/2026 | https://www.coruna.gal/documentos/descarga.jsp?19400053838 |
| 202104_PUBLICACION_MENORES_CUARTO_TRIMESTRE_2021.ods | T4 2021 | 20/10/2026 | https://www.coruna.gal/documentos/descarga.jsp?19399653874 |

## Extracción (`src/01_extract.py`)

El portal no usa una plantilla estable entre trimestres. Esto se detectó mirando a mano, fichero a fichero, tanto los `.xlsx` (2019) como los `.ods` (2020-2021) con `pandas.read_excel(..., header=None)`, es decir, viendo la hoja "en crudo" antes de asumir dónde está la cabecera:

- **"Plano"**: la cabecera ocupa la fila 0 y los datos empiezan en la fila 1. Solo ocurre en **T1 2019**. No tiene columna de tipo de contrato.
- **"Con portada"**: varias filas de título y aviso legal (sobre la omisión del NIF de personas físicas), luego la fila de cabecera real (localizada buscando la celda `"Referencia"`) y una fila de subcabecera que se descarta. Es el formato de **T2, T3 y T4 2019, y de todo 2020 y 2021**.

Dentro del grupo "con portada" el número de columnas también varía de un trimestre a otro, otra vez comprobado abriendo cada fichero a mano:

| Trimestre | Formato | Extensión | Nº columnas | Particularidad |
|---|---|---|---|---|
| T1 2019 | Plano | .xlsx | 9 | Sin columna de tipo de contrato; en cambio sí trae "técnico responsable" y "duración", que no existen en el resto |
| T2 2019 | Con portada | .xlsx | 9 | — |
| T3 2019 | Con portada | .xlsx | 9 | — |
| **T4 2019** | Con portada | .ods | **10** | **Única con columna NACIONALIDAD** (casi siempre vacía) |
| T1-T4 2020 | Con portada | .ods | 9 | Columna en blanco al principio de la hoja (desplaza todo una posición) |
| T1-T4 2021 | Con portada | .ods | 8 | Sin la columna en blanco inicial de 2020 |

Como ni el número ni el orden de columnas es estable, el script **no mapea por posición sino por el texto de la cabecera** (busca la celda `"Referencia"`, `"Objeto"`, `"NIF"`, etc. y a partir de ahí decide qué columna es cada cosa). Así, la columna NACIONALIDAD de T4 2019 o la columna en blanco de 2020 simplemente no se mapean a nada y se descartan solas, sin romper el resto del esquema.

El script lee los 12 ficheros de `data/raw/`, los normaliza a un esquema común (`referencia`, `tipo_contrato`, `objeto`, `fecha_adjudicacion`, `nif`, `nombre_adjudicatario`, `importe`, `area_tramitadora` + metadatos `anio`/`trimestre`/`fichero_origen`) y guarda el resultado consolidado, sin tipar ni limpiar todavía, en `data/processed/bronze_contratos_menores.csv`. Se puede volver a ejecutar sin duplicar filas: cada ejecución sobrescribe el fichero de salida.


```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/01_extract.py
```
