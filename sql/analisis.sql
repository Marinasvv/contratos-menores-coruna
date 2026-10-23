-- Paso 4 - SQL y analisis.
--
-- Consultas sobre el modelo en estrella cargado en Snowflake
-- (fact_contratos + dim_fecha/dim_empresa/dim_area/dim_tipo_contrato).
--
-- Para "por año"/"por mes" se usa siempre la FECHA DE ADJUDICACION real
-- (dim_fecha), no el trimestre de publicacion del fichero (anio_publicacion/
-- trimestre_publicacion en fact_contratos): refleja cuando se gasto de
-- verdad, no cuando salio el PDF trimestral.
--


-- =====================================================================
-- 1. Contratos e importe total por año (pregunta 1 del objetivo)
-- Agregacion simple. El expediente con fecha fuera del periodo 2019-2021
-- (GEY/2019/18, fecha_key = -1) sale en su propio grupo "no disponible" en
-- vez de desaparecer sin mas.
-- =====================================================================
SELECT
    COALESCE(df.anio::VARCHAR, 'no disponible') AS anio,
    COUNT(*)                                     AS num_contratos,
    SUM(fc.importe_con_iva)                      AS importe_total_con_iva,
    ROUND(AVG(fc.importe_con_iva), 2)            AS importe_medio_con_iva
FROM fact_contratos fc
JOIN dim_fecha df ON fc.fecha_key = df.fecha_key
GROUP BY df.anio
ORDER BY df.anio;

-- Conclusión: el número de contratos se mantiene bastante estable entre los
-- 3 años (2.974 / 2.724 / 2.722), pero el importe total y el importe medio
-- dan un salto claro en 2020 (10,41 M€ / 3.824,72 € de media) frente a 2019
-- (6,09 M€ / 2.051,50 € de media) y se mantienen altos en 2021 (9,21 M€ /
-- 3.386,58 € de media, casi 2.000 € mas que en 2019). Es decir: no se
-- contrataron muchos más contratos durante el COVID, pero cada contrato
-- individual fue, de media, bastante más caro.

-- =====================================================================
-- 2. Ranking de empresas/adjudicatarios por gasto total (pregunta 2)
-- Agregacion + ordenacion (ranking). Incluye tanto personas juridicas como
-- fisicas (identificadas o anonimizadas): la pregunta es "quien concentra
-- mas gasto", no solo "que empresas".
-- Se puede filtrar por tipo_persona si se quiere ver solo empresas.
-- =====================================================================
SELECT
    de.nombre_normalizado,
    de.tipo_persona,
    de.forma_juridica,
    COUNT(*)                     AS num_contratos,
    SUM(fc.importe_con_iva)      AS importe_total_con_iva
FROM fact_contratos fc
JOIN dim_empresa de ON fc.empresa_key = de.empresa_key
WHERE de.empresa_key != -1
GROUP BY de.empresa_key, de.nombre_normalizado, de.tipo_persona, de.forma_juridica
ORDER BY importe_total_con_iva DESC NULLS LAST
LIMIT 20;

-- Conclusión: el top 20 de adjudicatarios por gasto está dominado por
-- Sociedades Limitadas (90%) frente a Sociedades Anónimas (10%), y casi
-- todas pertenecen al sector de obras/infraestructuras/construccion
-- (CONSTRUCCIONES LOPEZ CAO, JARDINERIA ARCE, ARIAS INFRAESTRUCTURAS,
-- INSTALACIONES DEPORTIVAS GALLEGAS, OBRAS RAMON COTELO, CIMBRA
-- CONTRACTS...). El gasto en contratos menores no está repartido de forma
-- uniforme entre sectores: se concentra claramente en empresas de obra
-- civil y mantenimiento de infraestructura municipal.

-- =====================================================================
-- 3. Desglose de gasto por area y por tipo de contrato (pregunta 3)
-- Dos agregaciones distintas unidas en un solo resultado (columna
-- "dimension" indica cual de las dos es cada fila), ordenadas por gasto
-- dentro de cada una.
-- =====================================================================

SELECT 'area' AS dimension, da.area_departamento AS valor,
       COUNT(*) AS num_contratos, SUM(fc.importe_con_iva) AS importe_total_con_iva
FROM fact_contratos fc
JOIN dim_area da ON fc.area_key = da.area_key
GROUP BY da.area_departamento

UNION ALL

SELECT 'tipo_contrato' AS dimension, tc.tipo_contrato AS valor,
       COUNT(*) AS num_contratos, SUM(fc.importe_con_iva) AS importe_total_con_iva
FROM fact_contratos fc
JOIN dim_tipo_contrato tc ON fc.tipo_contrato_key = tc.tipo_contrato_key
GROUP BY tc.tipo_contrato

ORDER BY dimension, importe_total_con_iva DESC;

-- Conclusión: el área que más gasto concentra es "SERVICIOS GENERALES DE
-- INFRAESTRUCTURAS" (3.591.764,47 € en 207 contratos), seguida de
-- "SERVICIOS GENERALES DE CI" (2.589.078,59 €, pero con 1.002 contratos:
-- mucho más volumen, importe medio más bajo) y "GESTION DE DEPORTES"
-- (2.488.288,89 €). Por tipo de contrato, "Servicios" domina claramente
-- (11.812.976,44 €), casi el doble que "Obras" (6.626.798,48 €) pese a que
-- Obras tiene umbrales legales más altos (40.000 € vs 15.000 €) - hay mucho
-- más VOLUMEN de contratos de servicios, no necesariamente contratos
-- individuales más caros.
--

-- =====================================================================
-- 4. Patrón elegido para investigar: contratos cerca del umbral legal
-- (posible fraccionamiento). Usa los indicadores ya calculados en el
-- modelo (cerca_umbral, >=90% del umbral sin superarlo).
-- =====================================================================
SELECT
    fc.expediente,
    de.nombre_normalizado,
    tc.tipo_contrato,
    fc.importe_sin_iva_estimado,
    tc.umbral_sin_iva,
    ROUND(100.0 * fc.importe_sin_iva_estimado / tc.umbral_sin_iva, 1) AS pct_del_umbral,
    da.area_departamento,
    fc.objeto
FROM fact_contratos fc
JOIN dim_empresa de ON fc.empresa_key = de.empresa_key
JOIN dim_tipo_contrato tc ON fc.tipo_contrato_key = tc.tipo_contrato_key
JOIN dim_area da ON fc.area_key = da.area_key
WHERE fc.cerca_umbral = TRUE
ORDER BY pct_del_umbral DESC;

-- Conclusión: el resultado (301 filas) muestra contratos individuales con
-- su porcentaje exacto respecto al umbral legal de su tipo, muchos de
-- ellos en el 100,0% (importe exacto al límite, ni un céntimo de más,
-- ej. 15.000,00 € o 40.000,00 € justos).

-- =====================================================================
-- 5. Comparativa Pre-COVID / Estado de alarma / Post-estado de alarma
-- Responde a la hipotesis central del proyecto (por que se eligio
-- 2019-2021). Un solo filtro (periodo_covid, ya calculado en dim_fecha)
-- en vez de acotar fechas a mano en cada consulta.
--
-- Los 3 periodos no duran lo mismo (Pre-COVID ~14 meses, Estado de
-- alarma ~13 meses, Post-estado de alarma solo ~7 meses, porque
-- nuestro periodo de análisis termina el 31/12/2021) - comparar solo
-- totales en bruto favorece a los periodos más largos. Se añade
-- "contratos_por_mes" para poder comparar de forma justa.
-- =====================================================================
WITH duracion_periodo AS (
    SELECT 'Pre-COVID' AS periodo_covid, 437 AS duracion_dias
    UNION ALL SELECT 'Estado de alarma', 421
    UNION ALL SELECT 'Post-estado de alarma', 235
)
SELECT
    df.periodo_covid,
    COUNT(*)                                          AS num_contratos,
    SUM(fc.importe_con_iva)                            AS importe_total_con_iva,
    ROUND(AVG(fc.importe_con_iva), 2)                  AS importe_medio_con_iva,
    dp.duracion_dias,
    ROUND(COUNT(*) / (dp.duracion_dias / 30.4), 1)     AS contratos_por_mes,
    ROUND(SUM(fc.importe_con_iva) / (dp.duracion_dias / 30.4), 2) AS importe_total_por_mes
FROM fact_contratos fc
JOIN dim_fecha df ON fc.fecha_key = df.fecha_key
JOIN duracion_periodo dp ON dp.periodo_covid = df.periodo_covid
WHERE df.fecha_key != -1
GROUP BY df.periodo_covid, dp.duracion_dias
ORDER BY MIN(df.fecha);

-- Conclusión: normalizando por mes, el ritmo de contratación es parecido
-- en los 3 periodos (Pre-COVID ~245/mes, Estado de alarma ~214/mes, Post
-- ~250/mes) - la caída real durante el estado de alarma es de solo ~13%,
-- mucho más suave de lo que sugerian los totales en bruto (que estaban
-- sesgados porque "Post-estado de alarma" dura menos tiempo: 7,7 meses
-- frente a los ~14 de los otros dos). Lo que se mantiene robusto tras
-- la corrección es el importe medio por contrato (no depende de la
-- duración del periodo): 2.127,55 € Pre-COVID -> 3.873,61 € en estado de
-- alarma -> 3.499,27 € después. El número de contratos apenas cambia, pero
-- cada uno es, de media, bastante más caro durante el COVID.


-- =====================================================================
-- 6. Estacionalidad: en que meses se concentran más contratos
-- Agregación + ordenación.
-- =====================================================================
SELECT
    df.mes,
    df.nombre_mes,
    COUNT(*)                 AS num_contratos,
    SUM(fc.importe_con_iva)  AS importe_total_con_iva
FROM fact_contratos fc
JOIN dim_fecha df ON fc.fecha_key = df.fecha_key
WHERE df.fecha_key != -1
GROUP BY df.mes, df.nombre_mes
ORDER BY num_contratos DESC;

-- Conclusión: noviembre concentra claramente mas contratos (1.167) y más
-- gasto (4.564.171,44 €) que cualquier otro mes, seguido de octubre (932 /
-- 3.501.186,96 €) - casi el doble que la media del resto de meses. Agosto
-- (484) y enero (496) son los mas bajos. El patrón encaja con el cierre
-- del ejercicio presupuestario municipal y con
-- el parón estival de agosto.

-- =====================================================================
-- 7. Comprobación de calidad
-- Mismos controles que ya corre src/04_load_snowflake.py al cargar
-- =====================================================================
SELECT 'fk_nulas_fecha' AS control, COUNT(*) AS valor
FROM fact_contratos WHERE fecha_key IS NULL
UNION ALL
SELECT 'fk_nulas_empresa', COUNT(*) FROM fact_contratos WHERE empresa_key IS NULL
UNION ALL
SELECT 'fk_nulas_area', COUNT(*) FROM fact_contratos WHERE area_key IS NULL
UNION ALL
SELECT 'fk_nulas_tipo_contrato', COUNT(*) FROM fact_contratos WHERE tipo_contrato_key IS NULL
UNION ALL
SELECT 'huerfanas_fecha', COUNT(*)
FROM fact_contratos fc LEFT JOIN dim_fecha df ON fc.fecha_key = df.fecha_key
WHERE df.fecha_key IS NULL
UNION ALL
SELECT 'huerfanas_empresa', COUNT(*)
FROM fact_contratos fc LEFT JOIN dim_empresa de ON fc.empresa_key = de.empresa_key
WHERE de.empresa_key IS NULL
UNION ALL
SELECT 'huerfanas_area', COUNT(*)
FROM fact_contratos fc LEFT JOIN dim_area da ON fc.area_key = da.area_key
WHERE da.area_key IS NULL
UNION ALL
SELECT 'huerfanas_tipo_contrato', COUNT(*)
FROM fact_contratos fc LEFT JOIN dim_tipo_contrato tc ON fc.tipo_contrato_key = tc.tipo_contrato_key
WHERE tc.tipo_contrato_key IS NULL
UNION ALL
SELECT 'duplicados_exactos', COUNT(*) FROM (
    SELECT expediente, empresa_key, importe_con_iva, fecha_key, objeto, COUNT(*) AS n
    FROM fact_contratos
    GROUP BY expediente, empresa_key, importe_con_iva, fecha_key, objeto
    HAVING COUNT(*) > 1
);
