-- Paso 3 - DDL del modelo en estrella en Snowflake.
--
-- Grano de fact_contratos: una fila por linea de contrato publicada
-- (expediente + adjudicatario + importe). Ver README para la justificacion.
--
-- Las claves foraneas NUNCA son NULL: cada dimension tiene una fila
-- "no disponible" con clave -1 (convencion Kimball), asi que no hace falta
-- permitir NULL en ninguna columna de clave.
--

CREATE TABLE IF NOT EXISTS dim_fecha (
    fecha_key       INTEGER      NOT NULL,
    fecha           DATE,
    anio            INTEGER,
    trimestre       INTEGER,
    mes             INTEGER,
    nombre_mes      VARCHAR(20),
    dia_semana      VARCHAR(20),
    periodo_covid   VARCHAR(30)  NOT NULL,
    CONSTRAINT pk_dim_fecha PRIMARY KEY (fecha_key)
);

CREATE TABLE IF NOT EXISTS dim_empresa (
    empresa_key         INTEGER       NOT NULL,
    nif                 VARCHAR(20)   NOT NULL,
    nombre_normalizado  VARCHAR(500)  NOT NULL,
    tipo_persona        VARCHAR(50)   NOT NULL,
    forma_juridica       VARCHAR(100)  NOT NULL,
    CONSTRAINT pk_dim_empresa PRIMARY KEY (empresa_key)
);

CREATE TABLE IF NOT EXISTS dim_area (
    area_key            INTEGER       NOT NULL,
    area_departamento   VARCHAR(200)  NOT NULL,
    CONSTRAINT pk_dim_area PRIMARY KEY (area_key)
);

CREATE TABLE IF NOT EXISTS dim_tipo_contrato (
    tipo_contrato_key  INTEGER       NOT NULL,
    tipo_contrato      VARCHAR(50)   NOT NULL,
    umbral_sin_iva     NUMBER(12,2),
    CONSTRAINT pk_dim_tipo_contrato PRIMARY KEY (tipo_contrato_key)
);

CREATE TABLE IF NOT EXISTS fact_contratos (
    fecha_key                  INTEGER        NOT NULL,
    empresa_key                INTEGER        NOT NULL,
    area_key                   INTEGER        NOT NULL,
    tipo_contrato_key          INTEGER        NOT NULL,
    importe_con_iva            NUMBER(12,2),
    importe_sin_iva_estimado   NUMBER(12,2),
    supera_umbral               BOOLEAN        NOT NULL,
    cerca_umbral                BOOLEAN        NOT NULL,
    expediente                 VARCHAR(50)    NOT NULL,
    objeto                      VARCHAR(2000)  NOT NULL,
    anio_publicacion           INTEGER        NOT NULL,
    trimestre_publicacion       INTEGER        NOT NULL,
    fila_origen                 INTEGER        NOT NULL,
    fichero_origen               VARCHAR(200)   NOT NULL,
    CONSTRAINT fk_fecha FOREIGN KEY (fecha_key) REFERENCES dim_fecha (fecha_key),
    CONSTRAINT fk_empresa FOREIGN KEY (empresa_key) REFERENCES dim_empresa (empresa_key),
    CONSTRAINT fk_area FOREIGN KEY (area_key) REFERENCES dim_area (area_key),
    CONSTRAINT fk_tipo_contrato FOREIGN KEY (tipo_contrato_key) REFERENCES dim_tipo_contrato (tipo_contrato_key)
);
