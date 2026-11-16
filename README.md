# Momento 3 · Rendimiento académico

El proyecto procesa el CSV de xAPI-Edu-Data con PySpark, lo almacena en PostgreSQL y usa los resultados de consultas SQL en un informe de Power BI con medidas DAX y una página de hipótesis. [Fuente en Kaggle](https://www.kaggle.com/datasets/aljarah/xAPI-Edu-Data)

## Abrir el informe

Descarga el archivo [Momento 3 - Rendimiento académico.pbix](Momento3_PowerBI/Momento%203%20-%20Rendimiento%20acad%C3%A9mico.pbix) y ábrelo en Power BI Desktop. Incluye los datos de la última carga y las cinco páginas. Para esta opción basta Power BI Desktop.

## Reproducir el flujo en Windows

1. Clona el repositorio y abre PowerShell en la carpeta del proyecto.

   ```powershell
   git clone https://github.com/sebastiandavid98/Herramientas_Computacionales.git
   cd Herramientas_Computacionales/Momento3_PowerBI
   ```

2. Ten disponibles Python, Java, PostgreSQL con `psql` y Power BI Desktop. El flujo se ejecutó con Python 3.14, Java 25 y PostgreSQL 17.

   ```powershell
   python -m pip install -r requirements.txt
   java -version
   ```

3. Inicia tu servidor PostgreSQL y crea una base vacía llamada `momento3_powerbi` en pgAdmin. Ajusta el puerto, usuario y ruta de `psql` a tu instalación. Configura la contraseña localmente en [el archivo de contraseñas de PostgreSQL](https://www.postgresql.org/docs/17/libpq-pgpass.html) si tu servidor la solicita.

   ```powershell
   $env:PGHOST = '127.0.0.1'
   $env:PGPORT = '5432'
   $env:PGUSER = 'postgres'
   $env:PGDATABASE = 'momento3_powerbi'
   $env:PSQL = 'C:\Program Files\PostgreSQL\17\bin\psql.exe'
   $env:OPENBLAS_NUM_THREADS = '1'
   $env:PYSPARK_SUBMIT_ARGS = '--driver-memory 512m pyspark-shell'
   ```

4. Ejecuta el ETL y revisa las consultas. El ETL crea el esquema `academico` y recarga sus tres tablas, por lo que conviene usar una base dedicada al proyecto.

   ```powershell
   python scripts/04_etl_pyspark.py
   & $env:PSQL -X -v ON_ERROR_STOP=1 -P pager=off -f sql/consultas.sql
   ```

5. Con Power BI cerrado, genera el proyecto desde las vistas de tu base.

   ```powershell
   python scripts/05_configurar_power_bi_postgres.py --servidor "${env:PGHOST}:${env:PGPORT}" --base $env:PGDATABASE
   ```

   Abre el archivo `.pbip`, pulsa **Inicio → Actualizar** y guarda como `.pbix` si necesitas entregar una nueva copia. El informe importa una copia de los resultados SQL. Para actualizarla con datos nuevos, repite el ETL y la generación.

En **Panorama** comprueba que aparezcan **480 observaciones**, un **índice medio de 70,6** y **29,6 % de rendimiento alto**. El CSV trae categorías escolares de rendimiento. Las hipótesis usan la proporción de categoría alta y su asociación con el rango de ausencias.
