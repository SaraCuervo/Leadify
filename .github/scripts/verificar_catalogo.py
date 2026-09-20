# -*- coding: utf-8 -*-
"""Revisa que el catálogo etiquetado corresponda al código que lo genera.

`proyectos_model.json` se versiona —es lo que hace que `recomendar()` funcione
recién clonado, sin scrapear ni entrenar— pero lo produce `Model/prep.py` a
partir del catálogo crudo. Si alguien cambia los supuestos de crédito o el
etiquetado y no regenera el JSON, nada falla: el motor simplemente recomienda
con las reglas viejas. Esto lo detecta.

Se regenera en un archivo aparte y se compara, así que el versionado no se
toca. La comparación **ignora `meta.generado_en`**, que es la fecha de la
corrida y cambia siempre.

Se corre desde la raíz del repositorio:

    python .github/scripts/verificar_catalogo.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

BACKEND = os.path.join("Demo", "backend")
COMPROMETIDO = os.path.join(BACKEND, "Model", "data_projects", "proyectos_model.json")
VOLATILES = {"generado_en"}


def cargar(ruta: str) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def sin_volatiles(meta: dict) -> dict:
    return {k: v for k, v in meta.items() if k not in VOLATILES}


def main() -> int:
    if not os.path.isdir(BACKEND):
        print("Hay que correrlo desde la raíz del repositorio.")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        regenerado = os.path.join(os.path.abspath(tmp), "proyectos_model.json")
        print("Regenerando el catálogo con Model/prep.py...")
        corrida = subprocess.run(
            [sys.executable, os.path.join("Model", "prep.py"), "--salida", regenerado],
            cwd=BACKEND, capture_output=True, text=True,
        )
        if corrida.returncode != 0:
            print("prep.py falló:")
            print(corrida.stdout[-2000:])
            print(corrida.stderr[-2000:])
            return 1

        viejo = cargar(COMPROMETIDO)
        nuevo = cargar(regenerado)

    fallos = []

    if viejo.get("proyectos") != nuevo.get("proyectos"):
        v = {p.get("id_proyecto"): p for p in viejo.get("proyectos", [])}
        n = {p.get("id_proyecto"): p for p in nuevo.get("proyectos", [])}
        if set(v) != set(n):
            fallos.append("cambian los proyectos: %d versionados, %d regenerados"
                          % (len(v), len(n)))
        distintos = [i for i in sorted(set(v) & set(n)) if v[i] != n[i]]
        if distintos:
            fallos.append("%d proyectos difieren (ids: %s%s)"
                          % (len(distintos), distintos[:5],
                             "..." if len(distintos) > 5 else ""))
            ejemplo = distintos[0]
            campos = [c for c in set(v[ejemplo]) | set(n[ejemplo])
                      if v[ejemplo].get(c) != n[ejemplo].get(c)]
            fallos.append("  el %d difiere en: %s" % (ejemplo, sorted(campos)))

    if sin_volatiles(viejo.get("meta", {})) != sin_volatiles(nuevo.get("meta", {})):
        fallos.append("cambia la metadata (supuestos de crédito, conteos o avisos)")

    if fallos:
        print()
        print("El catálogo versionado NO corresponde al código que lo genera:")
        for f in fallos:
            print("  - %s" % f)
        print()
        print("Se arregla corriendo, desde Demo/backend/:  python Model/prep.py")
        return 1

    print("El catálogo versionado corresponde al código: %d proyectos."
          % len(nuevo.get("proyectos", [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
