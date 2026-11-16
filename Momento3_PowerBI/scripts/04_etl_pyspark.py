"""Lee el CSV con PySpark, calcula las variables y carga PostgreSQL en una transacción."""

import csv
import importlib
import io
import os
import subprocess

from pyspark.sql import SparkSession, functions as F
from scipy.stats import binomtest, fisher_exact

project = importlib.import_module("03_generar_power_bi")
PSQL = os.environ.get("PSQL", r"C:\Program Files\PostgreSQL\17\bin\psql.exe")
CSV_FIELDS = [
    "gender", "NationalITy", "PlaceofBirth", "StageID", "GradeID", "SectionID",
    "Topic", "Semester", "Relation", "raisedhands", "VisITedResources",
    "AnnouncementsView", "Discussion", "ParentAnsweringSurvey",
    "ParentschoolSatisfaction", "StudentAbsenceDays", "Class",
]


def copy(table, rows):
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return f"COPY academico.{table} FROM STDIN WITH (FORMAT csv);\n{buffer.getvalue()}\\.\n"


def main():
    if os.environ.get("JAVA_HOME"):
        os.environ["JAVA_HOME"] = os.environ["JAVA_HOME"].rstrip("\\/")
    spark = (
        SparkSession.builder.master("local[2]").appName("Rendimiento académico")
        .config("spark.ui.enabled", "false").config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1").getOrCreate()
    )
    try:
        raw = spark.read.option("header", True).option("mode", "FAILFAST").csv(project.RAW.as_posix())
        if set(raw.columns) != set(CSV_FIELDS):
            raise ValueError("Las columnas no coinciden con xAPI-Edu-Data")
        fields = CSV_FIELDS
        clean = raw.select(*(F.trim(F.col(name)).alias(name) for name in fields))
        invalid = F.lit(False)
        numbers = ["raisedhands", "VisITedResources", "AnnouncementsView", "Discussion"]
        for name in fields:
            invalid = invalid | F.col(name).isNull()
            if name not in numbers:
                invalid = invalid | (F.col(name) == "")
        clean = clean.select(*(F.col(name).cast("int").alias(name) if name in numbers else F.col(name) for name in fields))
        for name in numbers:
            invalid = invalid | ~F.col(name).between(0, 100)
        invalid = invalid | ~F.col("Class").isin("L", "M", "H") | ~F.col("StudentAbsenceDays").isin("Under-7", "Above-7")
        if clean.filter(invalid).take(1):
            raise ValueError("El CSV contiene valores inesperados")
        transformed = clean.withColumn(
            "puntaje", F.when(F.col("Class") == "H", 90).when(F.col("Class") == "M", 70).otherwise(50)
        ).withColumn("riesgo", ((F.col("Class") == "L") & (F.col("StudentAbsenceDays") == "Above-7")).cast("int"))
        rows = transformed.orderBy(*fields).collect()
    finally:
        spark.stop()
    if not rows:
        raise ValueError("El CSV no contiene observaciones")

    analysis = [row.asDict() for row in rows]
    under = [row for row in rows if row.StudentAbsenceDays == "Under-7"]
    above = [row for row in rows if row.StudentAbsenceDays == "Above-7"]
    high_under = sum(row.Class == "H" for row in under)
    high_above = sum(row.Class == "H" for row in above)
    tests = [
        ("¿La proporción alta supera el 25 %?", "Clase alta", len(rows), (high_under + high_above) / len(rows),
         binomtest(high_under + high_above, len(rows), 0.25, alternative="greater").pvalue, "Binomial unilateral"),
        ("¿La proporción alta es mayor en Under-7?", "Clase alta y rango de ausencias", len(rows),
         high_under / len(under) - high_above / len(above),
         fisher_exact([[high_under, len(under) - high_under], [high_above, len(above) - high_above]], alternative="greater").pvalue,
         "Fisher unilateral"),
    ]
    schema = (project.ROOT / "sql" / "modelo.sql").read_text(encoding="utf-8")
    script = schema + "\nTRUNCATE academico.observaciones, academico.anova, academico.hipotesis;\n"
    script += copy("observaciones", ((i, *row) for i, row in enumerate(rows, start=1)))
    script += copy("anova", project.anova(analysis))
    script += copy("hipotesis", tests)
    subprocess.run(
        [PSQL, "-X", "-v", "ON_ERROR_STOP=1", "--single-transaction", "-f", "-"],
        input=script.encode("utf-8"), env={**os.environ, "PGCLIENTENCODING": "UTF8"}, check=True,
    )
    print(f"Carga completa: {len(rows)} filas, {len(set(rows))} combinaciones distintas.")
    for question, _, _, estimate, p, method in tests:
        print(f"{method} | {question} | estimación={estimate:.4f} | p={p:.4g}")


if __name__ == "__main__":
    main()
