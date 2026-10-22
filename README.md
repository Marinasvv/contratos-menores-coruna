# Contratos menores — Concello da Coruña

Pipeline de datos (fuente pública → limpieza → Snowflake → SQL → Power BI) sobre los contratos menores publicados por el Concello da Coruña, con foco en comparar la contratación antes, durante y después del COVID (2019-2021). Proyecto del reto práctico de datos descrito en [docs/enunciado.md](docs/enunciado.md).

## Fuente de datos

- **Organismo:** Concello da Coruña – Portal de Transparencia
- **Página:** https://www.coruna.gal/transparencia/es/claridad-en-la-gestion/contratacion/contratos-menores?argIdioma=es
- **Formato:** hoja de cálculo. T1-T3 2019 son `.xlsx`; T4 2019 y todo 2020-2021 son `.ods`. Un fichero por trimestre.
- **Cobertura elegida:** 1 de enero de 2019 a 31 de diciembre de 2021 (3 años completos, 12 trimestres)
- **Por qué este rango:** se eligió para poder comparar un año "normal" (2019) con el año de la pandemia (2020, estado de alarma desde marzo) y el año de recuperación (2021), y así responder si la contratación de emergencia por COVID dejó huella visible en los contratos menores. Nota importante: muchas compras urgentes de material sanitario/EPIs durante 2020 se tramitaron por la vía de "contratación de emergencia" (art. 120 LCSP), un régimen distinto al de "contrato menor" que por tanto puede no aparecer en este listado — un hueco o ausencia de pico también es un resultado válido a documentar, no un fallo de los datos. Esa vía nace con el art. 16 del RD-ley 7/2020, lo modifica el RD-ley 8/2020, pero el que **extiende el régimen de emergencia a los ayuntamientos** (y no solo a la Administración General del Estado) es el **RD-ley 9/2020** — el relevante para A Coruña.
- **Base legal:** art. 63.4 de la LCSP (publicación trimestral de contratos menores). El umbral de "contrato menor" (art. 118.1 LCSP) se usó en la limpieza para resolver un importe ambiguo (ver sección de limpieza): **40.000 € para obras y 15.000 € para suministros/servicios**, sobre el valor estimado **sin IVA**. Verificado por varias fuentes secundarias independientes (instrucciones de contratación de universidades públicas, nota del Ministerio de Hacienda, derecholocal.es); el RD-ley 3/2020 (BOE 5/02/2020) modificó este artículo dentro de nuestro periodo pero no cambió estas cifras, solo añadió la exigencia de un informe de justificación. Pendiente: contrastar contra el texto consolidado en boe.es si se cita en la defensa, ya que las fuentes usadas son secundarias.
  - ⚠️ **El umbral legal excluye el IVA, pero nuestra columna `importe` lo incluye** (la propia cabecera del origen dice "Precio de adjudicación **con IVA**").

| Fichero                                                | Periodo | Fecha descarga | URL                                                        |
| ------------------------------------------------------ | ------- | -------------- | ---------------------------------------------------------- |
| 201901_Menores_1er_trimestre_2019.xlsx                 | T1 2019 | 20/10/2026     | https://www.coruna.gal/documentos/descarga.jsp?19396554153 |
| 201902_Menores_2__trimestre_2019.xlsx                  | T2 2019 | 20/10/2026     | https://www.coruna.gal/documentos/descarga.jsp?19396654144 |
| 201903_Menores_3er_trimestre_2019.xlsx                 | T3 2019 | 20/10/2026     | https://www.coruna.gal/documentos/descarga.jsp?19396754135 |
| 201904_Menores_4__trimestre_2019_open_document.ods     | T4 2019 | 20/10/2026     | https://www.coruna.gal/documentos/descarga.jsp?19396854126 |
| 202001_PUBLICACION_MENORES_PRIMER_TRIMESTRE_2020.ods   | T1 2020 | 20/10/2026     | https://www.coruna.gal/documentos/descarga.jsp?19396954117 |
| 202002_PUBLICACION_MENORES_SEGUNDO_TRIMESTRE_2020.ods  | T2 2020 | 20/10/2026     | https://www.coruna.gal/documentos/descarga.jsp?19397054108 |
| 202003_PUBLICACION_MENORES_TERCER_TRIMESTRE_2020.ods   | T3 2020 | 20/10/2026     | https://www.coruna.gal/documentos/descarga.jsp?19397154099 |
| 202004_PUBLICACION_MENORES_CUARTO_TRIMESTRE_2020.ods   | T4 2020 | 20/10/2026     | https://www.coruna.gal/documentos/descarga.jsp?19397554063 |
| 202101_PUBLICACION_MENORES_PRIMER_TRIMESTRE_2021.ods   | T1 2021 | 20/10/2026     | https://www.coruna.gal/documentos/descarga.jsp?19398054018 |
| 202102_PUBLICACION_MENORES_SEGUNDO_TRIMESTRE_2021.ods  | T2 2021 | 20/10/2026     | https://www.coruna.gal/documentos/descarga.jsp?19398154009 |
| 202103_PUBLICACION_MENORES_TERCEIRO_TRIMESTRE_2021.ods | T3 2021 | 20/10/2026     | https://www.coruna.gal/documentos/descarga.jsp?19400053838 |
| 202104_PUBLICACION_MENORES_CUARTO_TRIMESTRE_2021.ods   | T4 2021 | 20/10/2026     | https://www.coruna.gal/documentos/descarga.jsp?19399653874 |

## Extracción (`src/01_extract.py`)

El portal no usa una plantilla estable entre trimestres. Esto se detectó mirando a mano, fichero a fichero, tanto los `.xlsx` (2019) como los `.ods` (2020-2021) con `pandas.read_excel(..., header=None)`, es decir, viendo la hoja "en crudo" antes de asumir dónde está la cabecera:

- **"Plano"**: la cabecera ocupa la fila 0 y los datos empiezan en la fila 1. Solo ocurre en **T1 2019**. No tiene columna de tipo de contrato.
- **"Con portada"**: varias filas de título y aviso legal (sobre la omisión del NIF de personas físicas), luego la fila de cabecera real (localizada buscando la celda `"Referencia"`) y una fila de subcabecera que se descarta. Es el formato de **T2, T3 y T4 2019, y de todo 2020 y 2021**.

Dentro del grupo "con portada" el número de columnas también varía de un trimestre a otro, otra vez comprobado abriendo cada fichero a mano:

| Trimestre         | Formato     | Extensión | Nº columnas | Particularidad                                                                                                       |
| ----------------- | ----------- | ---------- | ------------ | -------------------------------------------------------------------------------------------------------------------- |
| T1 2019           | Plano       | .xlsx      | 9            | Sin columna de tipo de contrato; en cambio sí trae "técnico responsable" y "duración", que no existen en el resto |
| T2 2019           | Con portada | .xlsx      | 9            | —                                                                                                                   |
| T3 2019           | Con portada | .xlsx      | 9            | —                                                                                                                   |
| **T4 2019** | Con portada | .ods       | **10** | **Única con columna NACIONALIDAD** (casi siempre vacía)                                                      |
| T1-T4 2020        | Con portada | .ods       | 9            | Columna en blanco al principio de la hoja (desplaza todo una posición)                                              |
| T1-T4 2021        | Con portada | .ods       | 8            | Sin la columna en blanco inicial de 2020                                                                             |

Como ni el número ni el orden de columnas es estable, el script **no mapea por posición sino por el texto de la cabecera** (busca la celda `"Referencia"`, `"Objeto"`, `"NIF"`, etc. y a partir de ahí decide qué columna es cada cosa). Así, la columna NACIONALIDAD de T4 2019 o la columna en blanco de 2020 simplemente no se mapean a nada y se descartan solas, sin romper el resto del esquema.

El script lee los 12 ficheros de `data/raw/`, los normaliza a un esquema común (`referencia`, `tipo_contrato`, `objeto`, `fecha_adjudicacion`, `nif`, `nombre_adjudicatario`, `importe`, `area_tramitadora` + metadatos `fila_origen`/`anio`/`trimestre`/`fichero_origen`) y guarda el resultado consolidado, sin limpiar todavía, en `data/processed/bronze_contratos_menores.csv`. Se puede volver a ejecutar sin duplicar filas: cada ejecución sobrescribe el fichero de salida.

`fila_origen` guarda el número de fila tal como se ve en la hoja de cálculo original (Excel/LibreOffice cuentan desde 1), para poder localizar a mano cualquier registro concreto si hace falta justificarlo. El script también imprime, fichero a fichero, cuántas filas de relleno descarta (ver más abajo): 208 en T3 2019 y 14.151 en T4 2019, el resto con 0 — ningún contrato se pierde, solo huecos vacíos del rango de celdas de la hoja.

Nota: el bronce no pretende ser un facsímil visual del fichero original — por ejemplo, un importe puede aparecer como `"800"` o `"800.0"` según el fichero, según cómo pandas interprete esa celda en cada motor de lectura. No se ha dedicado esfuerzo a homogeneizar eso, porque es puramente cosmético: el paso de limpieza (`02_clean.py`) convierte ambas formas al mismo número y no cambia el resultado del análisis.

## Limpieza y transformación (`src/02_clean.py`)

Lee `data/processed/bronze_contratos_menores.csv` y escribe `data/processed/contratos_menores_limpio.csv`, con los campos pedidos ya tipados: `expediente`, `fecha_adjudicacion`, `area_departamento`, `objeto`, `nif`, `empresa_adjudicataria`, `importe`, `tipo_contrato` (+ `anio`/`trimestre`). Se puede volver a ejecutar sin duplicar filas.

### 1. Cambios de tipos y formatos

- **`fecha_adjudicacion` → fecha**: casi todos los ficheros traen la fecha como `"2019-03-01 00:00:00"`, pero en **T1 y T3 de 2019** algunas filas la traen como texto `"30/01/2019"` (día/mes/año). Si se usa solo el formato estándar, 41 filas se quedaban sin fecha. El script intenta primero el formato estándar y, para lo que falla, reintenta interpretando el día primero. Queda un caso más concreto: el expediente `231/2019/290` tiene `"08/082019"` en el origen — se puede reconstruir con confianza: solo falta un carácter (la barra entre mes y año, `082019` = `08`+`2019` pegados) y solo hay una lectura razonable (`08/08/2019`), así que el script detecta ese patrón concreto y lo recupera en vez de dejarlo vacío.
- **`importe` → número**: el origen mezcla `"1234.56"` (punto decimal, sin símbolo) con formato español `"1.234,56 €"` (punto de millares, coma decimal, símbolo de euro). El script quita el símbolo `€`, y si el valor tiene coma y punto a la vez asume que el punto es de millares; si solo tiene coma, la trata como decimal. Caso puntual: el expediente `AD0/2021/130` tiene `"9.399.28 €"` (dos puntos, sin ninguna coma). La agrupación en grupos de 3 dígitos + 2 decimales finales (`9` + `.399` + `.28`) coincide exactamente con el formato español de moneda, y el único error es que el separador decimal es un punto en vez de una coma — un solo carácter mal tecleado, igual que el caso de la fecha. Además, la lectura alternativa (ignorar la puntuación y leer `939.928 €`) superaría varias veces el umbral legal de 15.000 € para servicios (ver más abajo), por lo que ni siquiera podría estar legalmente publicado como contrato menor — el contexto confirma la lectura correcta. Se reconstruye a `9399.28`. Solo queda **1 importe** que de verdad no existe en el origen (expediente `GA2/2019/49`, T4 2019): esa fila no tiene ningún valor de importe en la hoja de cálculo, no es un error de formato, y se deja vacío.
- **`tipo_contrato` → categoría unificada**: 2019-2020 usan letras (`A`, `E`, `C`, `Z`) y 2021 usa palabras (`Obras`, `Servicios`, `Suministro`/`Suministros`, `Privado`), con espacios sueltos en algunos valores (`"Servicios "`) y una categoría rara que solo aparece una vez (`"Concesión obras públicas"`). El script traduce las letras a su significado real (`A`→Obras, `E`→Servicios, `C`→Suministros, `Z`→Otros, según la propia leyenda que trae cada fichero en la subcabecera) y unifica mayúsculas/espacios para que 2019, 2020 y 2021 se puedan comparar en el mismo gráfico.
- **`empresa_adjudicataria` y `objeto` → espacios normalizados**: se encontró, al preparar el modelo de Snowflake, que **1.795 filas** de `empresa_adjudicataria` y **1.154 de `objeto`** tienen espacios dobles o un espacio suelto antes de una coma (ej. `"ANTELO LAVANDEIRA , CLAUDIO"` en vez de `"ANTELO LAVANDEIRA, CLAUDIO"`). No es un error de una fila concreta, es ruido de formato extendido por todo el dataset: antes de corregirlo, el mismo NIF `34889996P` (una sola persona con 3 contratos distintos y legítimos) aparecía con 2 variantes de nombre, y los nombres únicos de `empresa_adjudicataria` bajaban de 2.535 a 2.519 solo con normalizar esto — es decir, 16 "personas distintas" eran en realidad la misma persona partida en dos por un espacio. Se corrige con una regla general (colapsar espacios, quitar el espacio antes de coma), no con parches por fila.

### 2. Tratamiento de nulos

Se distinguen dos situaciones que **no son lo mismo**, aunque las dos parezcan "un hueco":

- **El dato no existe en el origen** → se marca como `no disponible`. Pasa con `tipo_contrato` en **todo T1 2019** (807 filas: ese trimestre no publicó esa columna), con 2 NIF realmente vacíos, y con los `expediente`/`objeto`/`area_departamento`/`empresa_adjudicataria` si llegaran vacíos (no ha pasado ningún caso real, pero queda cubierto).
- **El dato está intencionadamente anonimizado por la propia fuente** → el NIF aparece como `"*"` en 953 filas. El propio fichero lo explica en su nota legal: se omite el NIF de las personas físicas adjudicatarias por protección de datos (Criterio interpretativo 4/2015 del Consejo de Transparencia). Esto **no** se convierte en `no disponible`: es un valor real y deliberado, no un hueco, y lo correcto es dejarlo tal cual y documentar por qué existe.
- El único campo numérico que falta de verdad (1 importe, expediente `GA2/2019/49`, ver punto anterior) se deja vacío (`NaN`/nulo) en vez de con el texto `no disponible`, porque mezclar texto en una columna numérica rompería los cálculos en SQL/Power BI más adelante; se documenta aquí el recuento en vez de maquillarlo en la propia columna. (La única fecha que faltaba, expediente `231/2019/290`, se recuperó — ver punto 1.)

### 3. Duplicados

**Regla 1 (duplicado exacto dentro del mismo trimestre)**: se considera duplicado si una fila es **idéntica en todas las columnas de negocio** (expediente, fecha, NIF, empresa, objeto, importe, área, tipo, año, trimestre). Con esa regla se eliminan **2 filas**:

- Expediente `631/2020/64`: repetida exactamente igual dos veces (duplicado exacto, sin más).
- Expediente `105/2020/1266` (T1 2020, filas 555 y 557 del `.ods` original): misma fecha, mismo NIF, mismo importe (5.487,56 €) y la misma factura (`"2019/25"`) citada en el objeto — solo cambiaba el nombre de la empresa en una letra (`"SERVICIO"` vs. `"SERVICIOS"` DE HOSTELERIA OLLOMOL S.L.). Revisado a mano antes de decidir: es un alta duplicada por error de tecleo en el nombre, no dos pagos distintos. Se normaliza ese nombre concreto (`NOMBRE_EMPRESA_CORRECCIONES` en el script) y la regla de "fila idéntica" hace el resto. No es una regla genérica de "nombres parecidos" — habría sido arriesgado aplicar coincidencia difusa al resto del dataset — es una corrección puntual para este caso ya verificado.

**Regla 2 (republicación entre trimestres)**: hallazgo posterior, al construir el modelo de Snowflake y comprobar duplicados en `fact_contratos` sin año/trimestre. **7 contratos de 2019** aparecen tal cual (mismo expediente, fecha, NIF, empresa, importe, objeto y área) en el fichero de un trimestre **y otra vez en el fichero del trimestre siguiente** (ej. `230/2019/224`, publicado en T2 y de nuevo en T3). No lo detectaba la regla 1 porque esa regla incluye año/trimestre a propósito — aquí es precisamente lo que hay que ignorar para verlo. Se elimina la copia más tardía y se conserva la primera publicación (ordenando por año/trimestre antes de aplicar la regla). Caso particular dentro de este grupo: el expediente `230/2019/158` se publicó en T1 2019 (sin `tipo_contrato`, como todo ese trimestre) y se repitió en T2 2019 (ya con `tipo_contrato = "Suministros"`) — por eso esta segunda regla **no** usa `tipo_contrato` como parte de la comparación, o se habría tratado como "distinto" solo por ese hueco estructural de T1 2019, no por ser un contrato diferente.

**Por qué NO se usa el expediente como clave única de duplicado**: un mismo número de expediente puede repartirse legítimamente en varias líneas distintas, y no son duplicados:

- El expediente `238/2019/118` tiene 6 líneas con el mismo expediente pero 6 empresas y conceptos distintos (alojamiento, catering, material, diseño...) — es un evento con varios proveedores bajo un mismo expediente.
- El expediente `106/2020/72` tiene **27 líneas** con el mismo importe (9.075,00 €) y el mismo objeto, pero cada una a nombre de una persona distinta — es una reparación de un edificio repercutida a cada vecino de la comunidad de propietarios, no una fila repetida 27 veces por error.

Si se hubiera usado "mismo expediente + mismo importe + mismo NIF" como regla de duplicado, este segundo caso se habría borrado por error (los 27 vecinos comparten NIF `"*"` al estar anonimizados), perdiendo información real de transparencia. Por la misma razón, **no se usa una comparación "difusa" de nombres de empresa** como regla general (dar por duplicado todo lo que se parezca mucho habría arriesgado falsos positivos en otras filas) — el caso `105/2020/1266` de arriba se resolvió a mano, revisando el `.ods` original, no con una heurística automática de similitud de texto.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/01_extract.py
python src/02_clean.py
```
