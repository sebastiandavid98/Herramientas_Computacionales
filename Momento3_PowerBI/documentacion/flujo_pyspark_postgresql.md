# Entrega corregida de rendimiento académico

## Flujo de trabajo

1. **PySpark** lee el CSV, limpia espacios, valida categorías, convierte los indicadores de participación a números y deriva el índice y el riesgo académico.
2. **PostgreSQL** almacena 480 observaciones, seis resultados exploratorios de ANOVA y dos pruebas de hipótesis. La carga reemplaza esas tablas en una transacción para que ejecutar el script otra vez no agregue duplicados. Se conservan las 480 observaciones de origen porque la fuente carece de identificador de estudiante.
3. **SQL** organiza los datos con vistas sobre las tablas. Se usa una tabla de observaciones porque el archivo es pequeño. Las vistas de asignatura, semestre, género, nivel, grado, ausencias y clase se conectan a los registros en Power BI con relaciones 1 a muchos. El archivo `sql/consultas.sql` contiene las consultas analíticas de los diez puntos de la consigna.
4. **Power BI** importa una copia de los resultados de las vistas SQL del esquema `academico`, exportada con `psql`. Esto permite presentar el informe sin depender de la conexión local ni de su certificado. Las medidas DAX responden a los filtros. Las pruebas estadísticas corresponden a la muestra completa.

## Reproducir en este equipo

Desde la carpeta `Momento3_PowerBI`, con PySpark, Java, SciPy y el cliente PostgreSQL disponibles:

```powershell
$env:PGHOST = '127.0.0.1'
$env:PGPORT = '55432'
$env:PGUSER = 'postgres'
$env:PGDATABASE = 'momento3_powerbi'
$env:OPENBLAS_NUM_THREADS = '1'
$env:PYSPARK_SUBMIT_ARGS = '--driver-memory 512m pyspark-shell'
python scripts/04_etl_pyspark.py
& 'C:/Program Files/PostgreSQL/17/bin/psql.exe' -X -v ON_ERROR_STOP=1 -f sql/consultas.sql
python scripts/05_configurar_power_bi_postgres.py
```

La instancia de práctica está en la carpeta `.postgres-academico` del espacio de trabajo, un nivel por encima de esta carpeta del proyecto. Solo escucha en `127.0.0.1:55432`. Si se detiene, se puede iniciar desde esta carpeta con:

```powershell
$datosPg = (Resolve-Path -LiteralPath '../.postgres-academico').Path
& 'C:/Program Files/PostgreSQL/17/bin/pg_ctl.exe' -D $datosPg -l (Join-Path $datosPg 'servidor.log') -o '-h 127.0.0.1 -p 55432' -w start
```

Abre `Momento 3 - Rendimiento académico.pbip` y usa **Inicio → Actualizar** para cargar los resultados incorporados. Cuando cambien los datos en PostgreSQL, vuelve a ejecutar el ETL y el generador con Power BI cerrado. En otro equipo puedes crear una base vacía, configurar las variables de conexión y usar `--servidor HOST:PUERTO --base BASE`. Si el profesor requiere el conector nativo, añade `--conexion-directa` y usa una instancia cuyo certificado sea válido y de confianza para Power BI.

## Dos preguntas de hipótesis

El CSV trae tres categorías de rendimiento. Usamos la variable **categoría alta (sí/no)**, que se puede comprobar directamente con los datos. Un promedio de notas superior a 5 requeriría calificaciones exactas y la escala original.

| Pregunta | H₀ | H₁ | Resultado |
|---|---|---|---|
| ¿Más del 25 % de las observaciones tiene rendimiento alto? | La proporción es como máximo 25 %. | La proporción supera 25 %. | 142 de 480, o 29,58 %. Prueba binomial unilateral, p = 0,01276. |
| ¿La categoría alta es más frecuente en Under-7? | La proporción alta en Under-7 es igual o menor que en Above-7. | La proporción alta en Under-7 es mayor. | 138 de 289 frente a 4 de 191, una diferencia de 45,66 puntos porcentuales. Prueba exacta de Fisher unilateral, p ≈ 1,22 × 10⁻³². |

En ambas pruebas, p es menor que 0,05 y se rechaza H₀ bajo los supuestos del análisis. El 25 % es un umbral de referencia elegido para el ejercicio. Las conclusiones son exploratorias porque no se puede confirmar la independencia entre observaciones de una misma persona. La asociación con las ausencias no demuestra una causa.

[Fuente xAPI-Edu-Data en Kaggle](https://www.kaggle.com/datasets/aljarah/xAPI-Edu-Data)
