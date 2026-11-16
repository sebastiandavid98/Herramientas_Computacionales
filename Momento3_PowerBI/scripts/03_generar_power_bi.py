"""Genera el proyecto editable de Power BI a partir del CSV original."""

import base64
import csv
import json
from pathlib import Path

from scipy.stats import f_oneway, kruskal, levene


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "datos" / "xAPI-Edu-Data.csv"
NAME = "Rendimiento"
MODEL = ROOT / f"{NAME}.SemanticModel"
REPORT = ROOT / f"{NAME}.Report"
DEFINITION = REPORT / "definition"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def m_table(columns, rows):
    contents = ", ".join("{" + ", ".join(json.dumps(item, ensure_ascii=False) for item in row) + "}" for row in rows)
    return "#table({" + ", ".join(json.dumps(column[0], ensure_ascii=False) for column in columns) + "}, {" + contents + "})"


def table(name, columns, source, measures=()):
    types = {"string": "type text", "int64": "Int64.Type", "double": "type number"}
    casts = ", ".join('{"' + column + '", ' + types[kind] + "}" for column, kind in columns)
    return {
        "name": name,
        "columns": [
            {
                "name": column, "sourceColumn": column, "dataType": kind, "summarizeBy": "none",
                **({"formatString": "0.00E+00"} if column.startswith("p ") else {}),
                **({"formatString": "0.000"} if column in ("F", "Eta cuadrado") else {}),
            }
            for column, kind in columns
        ],
        "measures": [{"name": label, "expression": dax, "formatString": fmt} for label, dax, fmt in measures],
        "partitions": [{
            "name": name, "mode": "import",
            "source": {"type": "m", "expression": f"Table.TransformColumnTypes(({source}), {{{casts}}})"},
        }],
    }


def anova(rows):
    result = []
    for factor, key in [
        ("Género", "gender"), ("Nivel educativo", "StageID"), ("Semestre", "Semester"),
        ("Asignatura", "Topic"), ("Rango de ausencias", "StudentAbsenceDays"),
        ("Encuesta familiar", "ParentAnsweringSurvey"),
    ]:
        groups = {}
        for row in rows:
            groups.setdefault(row[key], []).append({"L": 50, "M": 70, "H": 90}[row["Class"]])
        values = [score for scores in groups.values() for score in scores]
        mean = sum(values) / len(values)
        between = sum(len(scores) * (sum(scores) / len(scores) - mean) ** 2 for scores in groups.values())
        total = sum((score - mean) ** 2 for score in values)
        f, p = f_oneway(*groups.values())
        result.append([
            factor, len(groups), len(values), float(f), float(p), between / total,
            float(levene(*groups.values(), center="median").pvalue),
            float(kruskal(*groups.values()).pvalue),
        ])
    return result


def build_model():
    with RAW.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 480
    assert all(set(row.values()).isdisjoint({"", None}) for row in rows)

    lookup = {
        "Nivel": ("Nivel educativo", "StageID", {"lowerlevel": "Primaria", "MiddleSchool": "Secundaria", "HighSchool": "Bachillerato"}),
        "Semestre": ("Semestre", "Semester", {"F": "1", "S": "2"}),
        "Género": ("Género", "gender", {"F": "Femenino", "M": "Masculino"}),
        "Ausencias": ("Rango de ausencias", "StudentAbsenceDays", {"Under-7": "Under-7", "Above-7": "Above-7"}),
        "Clase": ("Clase de rendimiento", "Class", {"L": "Bajo", "M": "Medio", "H": "Alto"}),
        "Asignatura": ("Asignatura", "Topic", {r["Topic"]: r["Topic"] for r in rows}),
        "Grado": ("Grado escolar", "GradeID", {r["GradeID"]: r["GradeID"] for r in rows}),
    }
    dimensions = []
    relationships = []
    renames = []
    for dim, (label, key, mapping) in lookup.items():
        assert {r[key] for r in rows} <= mapping.keys()
        columns = [("Código", "string"), (label, "string")]
        dimension = table(dim, columns, m_table(columns, sorted(mapping.items())))
        dimension["columns"][0]["isHidden"] = True
        dimensions.append(dimension)
        foreign = "Clave " + dim
        renames.append((key, foreign))
        relationships.append({
            "name": f"Rendimiento_{key}", "fromTable": "Registros", "fromColumn": foreign,
            "toTable": dim, "toColumn": "Código",
        })
    numeric = [
        ("raisedhands", "Manos levantadas"), ("VisITedResources", "Recursos visitados"),
        ("AnnouncementsView", "Anuncios vistos"), ("Discussion", "Discusiones"),
    ]
    renames.extend(numeric + [("ParentAnsweringSurvey", "Encuesta familiar")])
    columns = [(column, "int64" if (original, column) in numeric else "string") for original, column in renames]
    columns.extend([("ID de registro", "int64"), ("Puntaje codificado", "int64"), ("Riesgo", "int64")])
    encoded = base64.b64encode(RAW.read_bytes()).decode("ascii")
    rename_m = ", ".join('{"' + source + '", "' + target + '"}' for source, target in renames)
    selected_m = ", ".join(json.dumps(col, ensure_ascii=False) for col, _ in columns[:-3])
    source = f'''
let
    Fuente = Csv.Document(Binary.FromText("{encoded}", BinaryEncoding.Base64), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Encabezados = Table.PromoteHeaders(Fuente, [PromoteAllScalars=true]),
    Renombradas = Table.RenameColumns(Encabezados, {{{rename_m}}}),
    Seleccionadas = Table.SelectColumns(Renombradas, {{{selected_m}}}),
    Limpias = Table.TransformColumns(Seleccionadas, List.Transform(Table.ColumnNames(Seleccionadas), each {{_, Text.Trim, type text}})),
    Identificadas = Table.AddIndexColumn(Limpias, "ID de registro", 1, 1, Int64.Type),
    Puntaje = Table.AddColumn(Identificadas, "Puntaje codificado", each if [Clave Clase] = "H" then 90 else if [Clave Clase] = "M" then 70 else if [Clave Clase] = "L" then 50 else error "Clase desconocida", Int64.Type),
    Riesgo = Table.AddColumn(Puntaje, "Riesgo", each if [Clave Clase] = "L" and [Clave Ausencias] = "Above-7" then 1 else 0, Int64.Type)
in
    Riesgo'''
    measures = [
        ("Observaciones", "COUNTROWS('Registros')", "#,0"),
        ("Índice medio", "AVERAGE('Registros'[Puntaje codificado])", "0.0"),
        ("Rendimiento bajo", 'CALCULATE([Observaciones], KEEPFILTERS(\'Clase\'[Clase de rendimiento] = "Bajo"))', "#,0"),
        ("% rendimiento bajo", "DIVIDE([Rendimiento bajo], [Observaciones], 0)", "0.0%"),
        ("Bajo en top 10", """VAR Materia = SELECTEDVALUE('Asignatura'[Asignatura])
VAR Primeras = TOPN(10, ALLSELECTED('Asignatura'[Asignatura]), [Rendimiento bajo], DESC, 'Asignatura'[Asignatura], ASC)
RETURN IF(CONTAINS(Primeras, 'Asignatura'[Asignatura], Materia), COALESCE([Rendimiento bajo], 0))""", "#,0"),
        ("Rendimiento alto", 'CALCULATE([Observaciones], KEEPFILTERS(\'Clase\'[Clase de rendimiento] = "Alto"))', "#,0"),
        ("% rendimiento alto", "DIVIDE([Rendimiento alto], [Observaciones], 0)", "0.0%"),
        ("% riesgo académico", "DIVIDE(SUM('Registros'[Riesgo]), [Observaciones])", "0.0%"),
    ]
    measures.extend((f"Media de {name.lower()}", f"AVERAGE('Registros'[{name}])", "0.0") for _, name in numeric)
    fact = table("Registros", columns, source, measures)
    for column in fact["columns"]:
        if column["name"].startswith("Clave ") or column["name"] in ("Puntaje codificado", "Riesgo"):
            column["isHidden"] = True
    anova_cols = [
        ("Factor", "string"), ("Grupos", "int64"), ("N", "int64"), ("F", "double"),
        ("p ANOVA", "double"), ("Eta cuadrado", "double"), ("p Levene", "double"),
        ("p Kruskal", "double"),
    ]
    validation = table("ANOVA", anova_cols, m_table(anova_cols, anova(rows)))
    write(MODEL / "model.bim", {
        "name": NAME, "compatibilityLevel": 1600,
        "model": {
            "culture": "es-CO", "sourceQueryCulture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "tables": [fact, *dimensions, validation], "relationships": relationships,
        },
    })
    write(MODEL / "definition.pbism", {
        "$schema": SCHEMA + "semanticModel/definitionProperties/1.0.0/schema.json", "version": "4.0",
    })


def projection(table, field, measure=False):
    return {
        "field": {
            "Measure" if measure else "Column": {
                "Expression": {"SourceRef": {"Entity": table}}, "Property": field,
            },
        },
        "queryRef": f"{table}.{field}",
        "nativeQueryRef": field,
    }


def literal(value):
    return {"expr": {"Literal": {"Value": value}}}


def formatting(**props):
    return [{"properties": {key: literal(value) for key, value in props.items()}}]


def color(value):
    return {"solid": {"color": literal(f"'{value}'")}}


def visual(page, name, kind, box, roles=None, title=None, sort=None, objects=None):
    x, y, width, height = box
    config = {"visualType": kind, "drillFilterOtherVisuals": True}
    if roles:
        config["query"] = {"queryState": {role: {"projections": items} for role, items in roles.items()}}
        if sort:
            config["query"]["sortDefinition"] = {
                "sort": [{"field": sort[0]["field"], "direction": sort[1]}],
                "isDefaultSort": False,
            }
    container = {"background": [{"properties": {"show": literal("true"), "color": color("#FFFFFF"), "transparency": literal("0D")}}]}
    if title:
        container["title"] = formatting(show="true", text=f"'{title}'", fontSize="13D")
        container["title"][0]["properties"]["fontColor"] = color("#152C43")
    config["visualContainerObjects"] = container
    if objects:
        config["objects"] = objects
    write(DEFINITION / "pages" / page / "visuals" / name / "visual.json", {
        "$schema": SCHEMA + "report/definition/visualContainer/2.0.0/schema.json",
        "name": name, "position": {"x": x, "y": y, "width": width, "height": height, "z": y * 100 + x},
        "visual": config,
    })


def note(page, name, box, lines):
    paragraphs = [
        {"textRuns": [{"value": line, "textStyle": {
            "fontFamily": "Segoe UI", "fontSize": f"{size}pt", "color": shade,
            **({"fontWeight": "bold"} if weight else {}),
        }}]}
        for line, size, shade, weight in lines
    ]
    visual(page, name, "textbox", box, objects={"general": [{"properties": {"paragraphs": paragraphs}}]})


def measure(name):
    return projection("Registros", name, True)


def chart(page, name, title, box, category, values, kind="clusteredColumnChart", series=None, sort=None):
    roles = {"Category": [projection(*category)], "Y": [measure(value) for value in values]}
    if series:
        roles["Series"] = [projection(*series)]
    visual(page, name, kind, box, roles, title, sort=sort)


def build_report():
    pages = {
        "panorama": "Panorama", "materias": "Asignaturas", "factores": "Asistencia y participación",
        "estadistica": "ANOVA y alcance",
    }
    write(ROOT / f"{NAME}.pbip", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": REPORT.name}}],
    })
    write(REPORT / "definition.pbir", {
        "$schema": SCHEMA + "report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": "../" + MODEL.name}},
    })
    write(DEFINITION / "version.json", {
        "$schema": SCHEMA + "report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0",
    })
    write(DEFINITION / "report.json", {
        "$schema": SCHEMA + "report/definition/report/1.0.0/schema.json",
        "layoutOptimization": "None",
        "themeCollection": {"baseTheme": {
            "name": "CY24SU10", "reportVersionAtImport": "5.61", "type": "SharedResources",
        }},
        "resourcePackages": [{
            "name": "SharedResources", "type": "SharedResources",
            "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}],
        }],
    })
    write(DEFINITION / "pages" / "pages.json", {
        "$schema": SCHEMA + "report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": list(pages), "activePageName": "panorama",
    })
    for page, label in pages.items():
        write(DEFINITION / "pages" / page / "page.json", {
            "$schema": SCHEMA + "report/definition/page/1.0.0/schema.json",
            "name": page, "displayName": label, "displayOption": "FitToPage", "width": 1280, "height": 760,
            "objects": {"background": [{"properties": {"color": color("#EDF3F8"), "transparency": literal("0D")}}]},
        })
    titles = [
        ("Rendimiento académico", "xAPI-Edu-Data · 480 observaciones escolares · Índice de clase L=50, M=70, H=90"),
        ("Rendimiento por asignatura", "El índice resume las clases registradas. La categoría baja se presenta por conteo y proporción."),
        ("Asistencia, participación y desempeño alto", "Las asociaciones describen esta muestra. Los IDs corresponden a filas del CSV."),
        ("Validación estadística y alcance", "Pruebas exploratorias sobre los 480 registros del CSV original."),
    ]
    for page, (title, subtitle) in zip(pages, titles):
        note(page, "encabezado", (20, 16, 1240, 90), [
            (title, 25, "#15304B", True), (subtitle, 12, "#435A70", False),
        ])

    for i, metric in enumerate(["Observaciones", "Índice medio", "% rendimiento alto", "% riesgo académico"]):
        visual("panorama", f"kpi{i}", "card", (20 + i * 312, 119, 300, 105), {"Values": [measure(metric)]})
    for i, (name, label, dim, field) in enumerate([
        ("semestre", "Comparación entre semestres", "Semestre", "Semestre"),
        ("genero", "Índice medio por género", "Género", "Género"),
        ("nivel", "Índice medio por nivel escolar", "Nivel", "Nivel educativo"),
        ("grado", "Índice medio por grado escolar", "Grado", "Grado escolar"),
    ]):
        category = projection(dim, field)
        chart("panorama", name, label, (20 + i % 2 * 628, 237 + i // 2 * 223, 612, 210),
              (dim, field), ["Índice medio"], sort=(category, "Ascending"))
    note("panorama", "riesgo", (20, 696, 1240, 48), [
        ("Riesgo académico = categoría baja y rango de ausencias Above-7. Los dos semestres carecen de año.", 12, "#435A70", False),
    ])

    chart("materias", "indice", "Índice por asignatura y semestre", (20, 119, 738, 600),
          ("Asignatura", "Asignatura"), ["Índice medio"], "clusteredBarChart", ("Semestre", "Semestre"),
          (projection("Asignatura", "Asignatura"), "Ascending"))
    top = projection("Asignatura", "Asignatura")
    top_measure = measure("Bajo en top 10")
    visual("materias", "ranking", "clusteredBarChart", (774, 119, 486, 360),
           {"Category": [top], "Y": [top_measure]},
           "Top 10 por registros de rendimiento bajo", sort=(top_measure, "Descending"))
    chart("materias", "tasas", "Proporción de rendimiento bajo por asignatura", (774, 492, 486, 227),
          ("Asignatura", "Asignatura"), ["% rendimiento bajo"], sort=(measure("% rendimiento bajo"), "Descending"))

    chart("factores", "ausencias", "Índice por rango de ausencias", (20, 119, 380, 250),
          ("Ausencias", "Rango de ausencias"), ["Índice medio"])
    chart("factores", "participacion", "Participación media por categoría de rendimiento", (416, 119, 844, 250),
          ("Clase", "Clase de rendimiento"), ["Media de manos levantadas", "Media de recursos visitados", "Media de anuncios vistos", "Media de discusiones"])
    chart("factores", "familia", "Índice según respuesta a la encuesta familiar", (20, 384, 380, 340),
          ("Registros", "Encuesta familiar"), ["Índice medio"])
    visual("factores", "clase", "slicer", (416, 384, 844, 65),
           {"Values": [{**projection("Clase", "Clase de rendimiento"), "active": True}]},
           "Filtrar el detalle por clase", objects={"data": formatting(mode="'Dropdown'")})
    visual("factores", "detalle", "tableEx", (416, 460, 844, 264), {"Values": [
        projection("Registros", "ID de registro"), projection("Asignatura", "Asignatura"),
        projection("Clase", "Clase de rendimiento"), projection("Grado", "Grado escolar"),
        projection("Ausencias", "Rango de ausencias"), projection("Registros", "Recursos visitados"),
    ]}, "Detalle de observaciones · elige Alto para identificar desempeño sobresaliente")

    visual("estadistica", "pruebas", "tableEx", (20, 119, 1240, 291), {"Values": [
        projection("ANOVA", name) for name in ["Factor", "Grupos", "N", "F", "p ANOVA", "Eta cuadrado", "p Levene", "p Kruskal"]
    ]}, "ANOVA de un factor, homogeneidad de varianzas y contraste por rangos")
    note("estadistica", "interpretacion", (20, 424, 1240, 132), [
        ("Cómo leer las pruebas", 16, "#15304B", True),
        ("F y p ANOVA comparan el índice medio. Eta cuadrado estima la proporción de variación asociada al factor.", 12, "#435A70", False),
        ("p Levene menor a 0,05 sugiere varianzas diferentes. Kruskal–Wallis contrasta los grupos mediante rangos.", 12, "#435A70", False),
        ("El índice usa tres valores ordinales. Las pruebas son exploratorias y la independencia por estudiante no es verificable.", 12, "#435A70", False),
    ])
    note("estadistica", "alcance", (20, 571, 1240, 153), [
        ("Cobertura de la fuente", 16, "#15304B", True),
        ("Sin notas individuales ni estado de aprobación. Se muestran el índice codificado y el porcentaje de rendimiento bajo.", 12, "#435A70", False),
        ("Sin facultad, programa universitario ni fecha de ingreso. Las comparaciones usan niveles y grados escolares.", 12, "#435A70", False),
        ("Sin registros de matrícula o retiro. El riesgo combina categoría baja y Above-7; no estima la deserción.", 12, "#435A70", False),
        ("Fuente abierta: Kaggle · Aljarah · Students’ Academic Performance Dataset (xAPI-Edu-Data).", 12, "#435A70", False),
    ])


if __name__ == "__main__":
    build_model()
    build_report()
