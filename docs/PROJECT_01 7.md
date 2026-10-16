# Reto práctico de datos

## Contratos menores de un ayuntamiento

## Contexto

Los ayuntamientos publican información sobre sus contratos menores, pero suele aparecer en Excel, PDF o listados web. El reto consiste en convertir una fuente pública en un pequeño producto de datos que permita entender cómo se distribuye el gasto.

Cada alumno elige un ayuntamiento y documenta la fuente consultada. No se busca reunir muchos datos, sino trabajar un conjunto suficiente para justificar decisiones y obtener conclusiones fiables.

Los contratos menores son adjudicaciones de importe limitado. Si el análisis incluye la proximidad a un umbral legal, hay que citar la referencia utilizada y presentarlo como una señal para investigar, no como prueba de irregularidad.

## Objetivo

Construir en cinco días una pipeline sencilla:

**fuente pública → datos limpios → Snowflake → SQL → Power BI → conclusiones**

El proyecto debe responder, como mínimo, a estas preguntas:

1. ¿Cuántos contratos e importe total hay por año?
2. ¿Qué empresas concentran más gasto?
3. ¿Qué áreas o tipos de contrato concentran más gasto?
4. ¿Qué patrones o posibles anomalías merecen investigación?

## Alcance mínimo

### 1. Fuente y extracción

- Usar una fuente pública del portal de transparencia o contratación del ayuntamiento.
- Trabajar, como mínimo, con un periodo o conjunto de documentos acotado y representativo.
- Guardar los originales en `data/raw/` y anotar en el README la URL, la fecha de descarga y la cobertura.
- Crear un script o notebook que lea la fuente y pueda ejecutarse de nuevo sin duplicar resultados.

No es obligatorio automatizar la descarga del portal. Si el formato exige decisiones especiales (PDF, codificación, tablas irregulares), hay que explicarlas brevemente.

### 2. Limpieza y transformación

Obtener una tabla de contratos con los campos disponibles más relevantes:

- expediente
- fecha
- área o departamento
- objeto
- NIF y empresa adjudicataria
- importe
- tipo de contrato

Si un campo no existe en la fuente, se indica `no disponible` y no se inventan valores.

Hay que documentar tres cosas: cambios de tipos y formatos, tratamiento de nulos y regla usada para detectar duplicados. El resultado se guarda en `data/processed/`.

### 3. Carga y modelo en Snowflake

- Cargar el resultado limpio en Snowflake.
- Crear una tabla de hechos `fact_contratos` y, si aporta valor, dimensiones de empresa, fecha, área o tipo.
- Usar tipos adecuados para fechas e importes.
- Ejecutar controles de conteo, nulos importantes y duplicados.
- Mantener las credenciales fuera del repositorio, mediante variables de entorno o `.env`; incluir `.env` en `.gitignore`.

El modelo debe tener una granularidad declarada: por ejemplo, una fila por contrato o expediente.

### 4. SQL y análisis

Crear al menos cuatro consultas SQL, legibles y comentadas, que respondan a las preguntas del objetivo. Una de ellas debe investigar un patrón elegido por el alumno, por ejemplo contratos repetidos con una empresa o importes próximos al límite legal aplicable.

Las consultas deben incluir al menos una agregación, una ordenación para obtener un ranking y una comprobación de calidad. No se valora el número de consultas, sino que los resultados sean interpretables.

### 5. Power BI

Crear un informe sencillo para una persona no técnica que incluya:

- número de contratos, importe total e importe medio;
- evolución temporal del gasto;
- ranking de empresas;
- distribución por área o tipo de contrato;
- filtros por año y, cuando existan, empresa y tipo.

El informe debe indicar el periodo analizado y la fuente de los datos.

## Evidencias de trabajo propio

Además del código, cada alumno entregará un `README.md` breve con:

- un esquema de la pipeline;
- la fuente elegida y por qué es adecuada;
- tres decisiones de limpieza explicadas con ejemplos reales de los datos;
- una limitación de los datos y cómo afecta a las conclusiones;
- tres hallazgos respaldados por cifras;
- una mejora que haría con más tiempo.

Todo lo que se entregue —informe, modelo, consultas, transformaciones y conclusiones— debe poder explicarse con el mayor nivel de detalle. No basta con mostrar el resultado: hay que justificar cada decisión y rastrear cada cifra hasta el dato de origen.

## Entregables

Repositorio GitHub con una estructura similar a esta:

```text
data/raw/
data/processed/
src/                 # extracción y transformación
sql/                 # modelo y consultas
powerbi/             # archivo .pbix
README.md
requirements.txt     # o pyproject.toml
.gitignore
```

El repositorio debe permitir entender cómo ejecutar el proyecto desde cero. No se deben subir credenciales ni datos personales innecesarios.

## Evaluación

| Criterio | Peso |
|---|---:|
| Calidad de la fuente, limpieza y controles | 25% |
| Modelo Snowflake y consultas SQL | 25% |
| Informe y claridad de los hallazgos | 20% |
| README, trazabilidad y organización | 10% |
| Defensa oral y prueba de comprensión | 20% |

Se penaliza presentar código o conclusiones que el alumno no pueda explicar. Se valora más una decisión razonada y bien documentada que una solución más compleja sin justificación.

## Presentación

Duración: unos **30 minutos**. No se trata de leer diapositivas. Todo lo que aparezca en el informe, el modelo o el código debe poder explicarse al mayor nivel de detalle: origen del dato, transformación aplicada, criterio usado y efecto sobre el resultado.

1. **Exposición del informe Power BI (role play)**  
   El alumno actúa como consultor y el tutor como usuario de negocio. El consultor presenta el informe, recorre las visualizaciones y explica qué ve el negocio, de dónde sale cada KPI y qué decisiones permite tomar. El usuario puede pedir filtros, aclaraciones o un recálculo sobre la marcha.

2. **Resolución de preguntas de negocio**  
   El alumno responde a las preguntas del objetivo y a las que formule el tutor. Cada respuesta debe ir acompañada de la cifra, el recorte temporal, las limitaciones del dato y, si aplica, una reserva sobre la interpretación.

3. **Construcción y razonamiento**  
   Recorrido detallado de la pipeline: fuente, extracción, limpiezas, carga, modelo, consultas SQL y medidas de Power BI. Hay que justificar las consideraciones adoptadas (granularidad, nulos, duplicados, relaciones, umbrales legales, exclusiones) y mostrar al menos un registro de principio a fin.
  