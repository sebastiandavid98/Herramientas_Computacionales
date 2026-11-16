CREATE SCHEMA IF NOT EXISTS academico;

-- Una fila por observación del CSV. El identificador se asigna en la carga.
CREATE TABLE IF NOT EXISTS academico.observaciones (
    id bigint PRIMARY KEY,
    genero text NOT NULL CHECK (genero IN ('F', 'M')),
    nacionalidad text NOT NULL,
    nacimiento text NOT NULL,
    nivel text NOT NULL CHECK (nivel IN ('lowerlevel', 'MiddleSchool', 'HighSchool')),
    grado text NOT NULL,
    seccion text NOT NULL,
    asignatura text NOT NULL,
    semestre text NOT NULL CHECK (semestre IN ('F', 'S')),
    tutor text NOT NULL,
    manos integer NOT NULL,
    recursos integer NOT NULL,
    anuncios integer NOT NULL,
    discusiones integer NOT NULL,
    encuesta text NOT NULL,
    satisfaccion text NOT NULL,
    ausencias text NOT NULL CHECK (ausencias IN ('Under-7', 'Above-7')),
    clase text NOT NULL CHECK (clase IN ('L', 'M', 'H')),
    puntaje integer NOT NULL,
    riesgo integer NOT NULL CHECK (riesgo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS academico.anova (
    factor text PRIMARY KEY, grupos integer, n integer, f double precision,
    p_anova double precision, eta double precision, p_levene double precision, p_kruskal double precision
);

CREATE TABLE IF NOT EXISTS academico.hipotesis (
    pregunta text PRIMARY KEY, variables text, n integer,
    estimacion double precision, valor_p double precision, prueba text
);

-- Estas vistas son las consultas que importa Power BI.
CREATE OR REPLACE VIEW academico.v_registros AS
SELECT id AS "ID de registro", nivel AS "Clave Nivel", semestre AS "Clave Semestre",
       genero AS "Clave Género", ausencias AS "Clave Ausencias", clase AS "Clave Clase",
       asignatura AS "Clave Asignatura", grado AS "Clave Grado", manos AS "Manos levantadas",
       recursos AS "Recursos visitados", anuncios AS "Anuncios vistos", discusiones AS "Discusiones",
       encuesta AS "Encuesta familiar", puntaje AS "Puntaje codificado", riesgo AS "Riesgo"
FROM academico.observaciones;

CREATE OR REPLACE VIEW academico.v_nivel AS
SELECT DISTINCT nivel AS "Código",
       CASE nivel WHEN 'lowerlevel' THEN 'Primaria' WHEN 'MiddleSchool' THEN 'Secundaria' ELSE 'Bachillerato' END AS "Nivel educativo"
FROM academico.observaciones;
CREATE OR REPLACE VIEW academico.v_semestre AS
SELECT DISTINCT semestre AS "Código", CASE semestre WHEN 'F' THEN '1' ELSE '2' END AS "Semestre"
FROM academico.observaciones;
CREATE OR REPLACE VIEW academico.v_genero AS
SELECT DISTINCT genero AS "Código", CASE genero WHEN 'F' THEN 'Femenino' ELSE 'Masculino' END AS "Género"
FROM academico.observaciones;
CREATE OR REPLACE VIEW academico.v_ausencias AS
SELECT DISTINCT ausencias AS "Código", ausencias AS "Rango de ausencias" FROM academico.observaciones;
CREATE OR REPLACE VIEW academico.v_clase AS
SELECT DISTINCT clase AS "Código",
       CASE clase WHEN 'H' THEN 'Alto' WHEN 'M' THEN 'Medio' ELSE 'Bajo' END AS "Clase de rendimiento"
FROM academico.observaciones;
CREATE OR REPLACE VIEW academico.v_asignatura AS
SELECT DISTINCT asignatura AS "Código", asignatura AS "Asignatura" FROM academico.observaciones;
CREATE OR REPLACE VIEW academico.v_grado AS
SELECT DISTINCT grado AS "Código", grado AS "Grado escolar" FROM academico.observaciones;
CREATE OR REPLACE VIEW academico.v_anova AS
SELECT factor AS "Factor", grupos AS "Grupos", n AS "N", f AS "F", p_anova AS "p ANOVA",
       eta AS "Eta cuadrado", p_levene AS "p Levene", p_kruskal AS "p Kruskal"
FROM academico.anova;
CREATE OR REPLACE VIEW academico.v_hipotesis AS
SELECT pregunta AS "Pregunta", variables AS "Variables", n AS "N", estimacion AS "Estimación",
       valor_p AS "p unilateral", prueba AS "Prueba",
       CASE WHEN valor_p < 0.05 THEN 'Rechazar H0' ELSE 'No se rechaza H0' END AS "Decisión al 5 %"
FROM academico.hipotesis;
