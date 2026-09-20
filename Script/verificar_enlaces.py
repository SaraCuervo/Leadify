# -*- coding: utf-8 -*-
"""Revisa que todo enlace relativo de los .md apunte a algo que existe.

Un enlace roto en la documentación no rompe nada al correr, así que nadie se
entera hasta que alguien lo sigue. Por eso se comprueba solo: es el tipo de
error que solo una máquina encuentra a tiempo.

Se corre desde la raíz del repositorio:

    python Script/verificar_enlaces.py

Devuelve 0 si todos resuelven y 1 si alguno no.
"""
from __future__ import annotations

import os
import re
import sys
from urllib.parse import unquote

# [texto](destino) — se ignoran los que llevan protocolo y los anclajes.
PATRON = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
EXTERNOS = ("http://", "https://", "mailto:", "#")
SALTAR = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def main() -> int:
    raiz = os.getcwd()
    rotos: list[tuple[str, str, str]] = []
    revisados = 0
    archivos = 0

    for carpeta, subcarpetas, nombres in os.walk(raiz):
        subcarpetas[:] = [s for s in subcarpetas if s not in SALTAR]
        for nombre in nombres:
            if not nombre.endswith(".md"):
                continue
            ruta = os.path.join(carpeta, nombre)
            try:
                texto = open(ruta, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            archivos += 1
            for etiqueta, destino in PATRON.findall(texto):
                if destino.startswith(EXTERNOS):
                    continue
                revisados += 1
                limpio = unquote(destino.split("#")[0])
                if not limpio:
                    continue
                objetivo = os.path.normpath(os.path.join(carpeta, limpio))
                if not os.path.exists(objetivo):
                    rotos.append((os.path.relpath(ruta, raiz), destino, etiqueta[:40]))

    print("%d archivos .md · %d enlaces relativos" % (archivos, revisados))
    if rotos:
        print("ROTOS: %d" % len(rotos))
        for archivo, destino, etiqueta in rotos:
            print("  %s -> %s   [%s]" % (archivo, destino, etiqueta))
        return 1
    print("Todos resuelven.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
