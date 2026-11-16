-- 1. Índice por asignatura y semestre
SELECT asignatura, semestre, COUNT(*) AS n, ROUND(AVG(puntaje), 2) AS indice
FROM academico.observaciones GROUP BY asignatura, semestre ORDER BY asignatura, semestre;

-- 2. Riesgo de la muestra. La base de origen carece de facultad y retiro.
SELECT COUNT(*) AS n, SUM(riesgo) AS casos_riesgo, ROUND(100 * AVG(riesgo), 2) AS pct_riesgo
FROM academico.observaciones;

-- 3. Género
SELECT genero, COUNT(*) AS n, ROUND(AVG(puntaje), 2) AS indice
FROM academico.observaciones GROUP BY genero ORDER BY genero;

-- 4. Nivel escolar, la agrupación disponible en el CSV
SELECT nivel, COUNT(*) AS n, ROUND(AVG(puntaje), 2) AS indice
FROM academico.observaciones GROUP BY nivel ORDER BY nivel;

-- 5. Comparación de los dos semestres
SELECT semestre, COUNT(*) AS n, ROUND(AVG(puntaje), 2) AS indice
FROM academico.observaciones GROUP BY semestre ORDER BY semestre;

-- 6. Top diez por conteo de categoría baja
SELECT asignatura, COUNT(*) FILTER (WHERE clase = 'L') AS bajos, COUNT(*) AS n,
       ROUND(100 * AVG((clase = 'L')::integer), 2) AS pct_bajo
FROM academico.observaciones GROUP BY asignatura ORDER BY bajos DESC, asignatura LIMIT 10;

-- 7. Ausencias y categoría alta
SELECT ausencias, COUNT(*) AS n, COUNT(*) FILTER (WHERE clase = 'H') AS altos,
       ROUND(100 * AVG((clase = 'H')::integer), 2) AS pct_alto
FROM academico.observaciones GROUP BY ausencias ORDER BY ausencias;

-- 8. Registros de categoría alta
SELECT id, asignatura, semestre, grado, ausencias FROM academico.observaciones
WHERE clase = 'H' ORDER BY id;

-- 9. Grado escolar, la agrupación disponible para comparar grupos
SELECT grado, COUNT(*) AS n, ROUND(AVG(puntaje), 2) AS indice
FROM academico.observaciones GROUP BY grado ORDER BY grado;

-- 10. Participación por clase, respuesta familiar y contrastes
SELECT clase, AVG(manos), AVG(recursos), AVG(anuncios), AVG(discusiones)
FROM academico.observaciones GROUP BY clase ORDER BY clase;
SELECT encuesta, COUNT(*) AS n, ROUND(AVG(puntaje), 2) AS indice
FROM academico.observaciones GROUP BY encuesta ORDER BY encuesta;
SELECT * FROM academico.v_hipotesis ORDER BY "Pregunta";
SELECT * FROM academico.v_anova ORDER BY "p ANOVA";
