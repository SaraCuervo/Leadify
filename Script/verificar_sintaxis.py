# -*- coding: utf-8 -*-
"""Revisa que todos los archivos .py del repositorio compilen sin errores.

Es la comprobación más barata que existe y la que se salta más seguido: un
error de sintaxis (una indentación mal puesta, un paréntesis que falta) no se
nota hasta que alguien intenta CORRER justo ese archivo. Con un proyecto de
este tamaño —backend, scraping, simulación, scripts de verificación— es fácil
que un archivo que nadie ha tocado en semanas se rompa por un cambio en otro
lado y nadie lo note hasta mucho después.

No corre nada, no importa nada: usa `py_compile`, que solo lee el archivo y
comprueba que Python pueda entenderlo. Por eso es instantáneo y no necesita
ninguna librería instalada — a diferencia de `verificar_catalogo.py`, que sí
depende de que el paquete `Model` cargue completo.

Se corre desde la raíz del repositorio:

    python Script/verificar_sintaxis.py
"""
from __future__ import annotations

import os
import py_compile
import sys

SALTAR = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def main() -> int:
    raiz = os.getcwd()
    revisados = 0
    rotos: list[tuple[str, str]] = []

    for carpeta, subcarpetas, nombres in os.walk(raiz):
        subcarpetas[:] = [s for s in subcarpetas if s not in SALTAR]
        for nombre in nombres:
            if not nombre.endswith(".py"):
                continue
            ruta = os.path.join(carpeta, nombre)
            revisados += 1
            try:
                py_compile.compile(ruta, doraise=True)
            except py_compile.PyCompileError as e:
                rotos.append((os.path.relpath(ruta, raiz), str(e.exc_value)))

    print("%d archivos .py revisados" % revisados)
    if rotos:
        print("NO COMPILAN: %d" % len(rotos))
        for archivo, error in rotos:
            print("  %s -> %s" % (archivo, error))
        return 1
    print("Todos compilan sin errores de sintaxis.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
