"""Crea una variante del informe que importa las vistas de PostgreSQL."""

import argparse
import base64
import importlib
import json
import os
import subprocess

report = importlib.import_module("03_generar_power_bi")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--servidor", default="127.0.0.1:55432")
    parser.add_argument("--base", default="momento3_powerbi")
    parser.add_argument("--conexion-directa", action="store_true", help="Configura el conector nativo de PostgreSQL")
    options = parser.parse_args()
    report.NAME = "Momento 3 - Rendimiento académico"
    report.MODEL = report.ROOT / f"{report.NAME}.SemanticModel"
    report.REPORT = report.ROOT / f"{report.NAME}.Report"
    report.DEFINITION = report.REPORT / "definition"
    report.build_model()
    report.build_report()

    model_file = report.MODEL / "model.bim"
    model = json.loads(model_file.read_text(encoding="utf-8"))
    hypotheses = report.table("Hipótesis", [
        ("Pregunta", "string"), ("Variables", "string"), ("N", "int64"),
        ("Estimación", "double"), ("p unilateral", "double"), ("Prueba", "string"),
        ("Decisión al 5 %", "string"),
    ], "#table({}, {})")
    next(col for col in hypotheses["columns"] if col["name"] == "Estimación")["formatString"] = "0.0%"
    model["model"]["tables"].append(hypotheses)
    views = {
        "Registros": "registros", "Nivel": "nivel", "Semestre": "semestre",
        "Género": "genero", "Ausencias": "ausencias", "Clase": "clase",
        "Asignatura": "asignatura", "Grado": "grado", "ANOVA": "anova", "Hipótesis": "hipotesis",
    }
    server, db = (f'"{value.replace(chr(34), chr(34) * 2)}"' for value in (options.servidor, options.base))
    for table in model["model"]["tables"]:
        view = views[table["name"]]
        if options.conexion_directa:
            source = (
                f'let Fuente = PostgreSQL.Database({server}, {db}, [CreateNavigationProperties=false]) '
                f'in Fuente{{[Schema="academico",Item="v_{view}"]}}[Data]'
            )
        else:
            # Una copia de los resultados de SQL permite presentar el tablero sin servidor.
            psql = importlib.import_module("04_etl_pyspark").PSQL
            host, _, port = options.servidor.rpartition(":")
            result = subprocess.run(
                [psql, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-h", host, "-p", port,
                 "-d", options.base, "-c", f"COPY (SELECT * FROM academico.v_{view}) TO STDOUT CSV HEADER"],
                env={**os.environ, "PGCLIENTENCODING": "UTF8"}, capture_output=True, check=True,
            )
            encoded = base64.b64encode(result.stdout).decode("ascii")
            types = {"int64": "Int64.Type", "double": "type number", "string": "type text"}
            casts = ", ".join(f'{{"{column["name"]}", {types[column["dataType"]]}}}' for column in table["columns"])
            source = (
                f'let Fuente = Csv.Document(Binary.FromText("{encoded}", BinaryEncoding.Base64), '
                f'[Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]), '
                f'Encabezados = Table.PromoteHeaders(Fuente, [PromoteAllScalars=true]) '
                f'in Table.TransformColumnTypes(Encabezados, {{{casts}}}, "en-US")'
            )
        table["partitions"][0]["source"]["expression"] = source
    report.write(model_file, model)

    pages = report.DEFINITION / "pages"
    metadata_file = pages / "pages.json"
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    metadata["pageOrder"].append("hipotesis")
    report.write(metadata_file, metadata)
    page = json.loads((pages / "estadistica" / "page.json").read_text(encoding="utf-8"))
    page.update(name="hipotesis", displayName="Hipótesis")
    report.write(pages / "hipotesis" / "page.json", page)
    heading = "#15304B"
    body = "#435A70"
    report.note("hipotesis", "encabezado", (20, 16, 1240, 88), [
        ("Preguntas de hipótesis", 25, heading, True),
        ("Variable de resultado: categoría alta (sí/no). Nivel de significancia: 5 %.", 12, body, False),
    ])
    report.visual("hipotesis", "resultados", "tableEx", (20, 120, 1240, 225), {"Values": [
        report.projection("Hipótesis", column["name"]) for column in hypotheses["columns"]
    ]}, "Resultados de las dos pruebas")
    report.note("hipotesis", "lectura", (20, 362, 1240, 350), [
        ("1. ¿Más de una cuarta parte tiene rendimiento alto?", 18, heading, True),
        ("H₀: la proporción alta es como máximo 25 %. H₁: la proporción alta supera el 25 %.", 14, body, False),
        ("Prueba binomial. El 25 % es un umbral de referencia elegido para el ejercicio.", 14, body, False),
        ("2. ¿El rendimiento alto es más frecuente en Under-7?", 18, heading, True),
        ("H₀: la proporción alta en Under-7 es igual o menor. H₁: es mayor que en Above-7.", 14, body, False),
        ("Prueba exacta de Fisher. La estimación es la diferencia entre proporciones en puntos porcentuales.", 14, body, False),
        ("Las pruebas son exploratorias. El CSV carece de notas exactas e identificadores de estudiante.", 13, body, False),
    ])


if __name__ == "__main__":
    main()
