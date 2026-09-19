"""
tools/enriquecer_tenants.py
===========================
Anade `direccion` y `barrio` a los catalogos de `tenants/*/proyectos.js`.

POR QUE EXISTE. El catalogo de cada tenant lo genera OTRO repo
(`plataforma/tools/generar_tenants.py`) y publica nombre, precio, area,
localidad, amenidades e imagenes — pero ni la direccion ni el barrio. La
tarjeta los necesita: con varias zonas marcadas en el mapa, "Suba" repetido
seis veces no le dice a nadie cual de sus zonas es cada proyecto, y el barrio
es justamente la pieza que lo resuelve.

El backend si los tiene, en `backend/Model/data_projects/proyectos_model.json`
(`direccion` en los 96, `barrio_nombre` en 83 — los 13 restantes son los que
no se pudieron ubicar en un sector catastral). Asi que se cruzan por nombre
normalizado. En la ultima corrida cruzaron TODOS los proyectos de los cinco
tenants, asi que el cruce por nombre es fiable aqui: ambos lados salen del
mismo scraping.

CUANDO VOLVER A CORRERLO: cada vez que se regeneren los `proyectos.js` desde
el otro repo, porque vuelven a salir sin estos dos campos. Es idempotente —
limpia lo que hubiera antes de escribir—, asi que se puede correr las veces
que haga falta.

    python tools/enriquecer_tenants.py              # informe, no escribe
    python tools/enriquecer_tenants.py --escribir   # aplica
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

# tools/ -> experiencia/ -> public/ -> frontend/ -> raiz del repo
DIR_EXPERIENCIA = Path(__file__).resolve().parent.parent
RAIZ = DIR_EXPERIENCIA.parent.parent.parent
MODELO = RAIZ / "backend" / "Model" / "data_projects" / "proyectos_model.json"
TENANTS = DIR_EXPERIENCIA / "tenants"

# `"name"` es unico por proyecto y el ancla mas estable del archivo: los campos
# nuevos se insertan justo detras.
RE_NAME = re.compile(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"')
RE_LIMPIAR = re.compile(r',"(?:direccion|barrio)":(?:"(?:[^"\\]|\\.)*"|null)')


def normalizar(texto: str) -> str:
    """Sin tildes, sin mayusculas y sin puntuacion: la llave del cruce."""
    plano = unicodedata.normalize("NFD", str(texto or ""))
    plano = plano.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", plano.lower()).strip()


def cargar_modelo() -> dict:
    datos = json.loads(MODELO.read_text(encoding="utf-8"))
    proyectos = datos["proyectos"] if isinstance(datos, dict) and "proyectos" in datos else datos
    return {normalizar(p.get("nombre_proyecto")): p for p in proyectos}


def main() -> int:
    if not MODELO.exists():
        print(f"no encuentro {MODELO}", file=sys.stderr)
        return 1

    escribir = "--escribir" in sys.argv
    por_nombre = cargar_modelo()
    print(f"modelo: {len(por_nombre)} proyectos")

    sin_cruce_total = 0
    for archivo in sorted(TENANTS.glob("*/proyectos.js")):
        texto = archivo.read_text(encoding="utf-8")
        nombres = RE_NAME.findall(texto)
        cruzan = [n for n in nombres if normalizar(n) in por_nombre]
        faltan = [n for n in nombres if normalizar(n) not in por_nombre]
        sin_cruce_total += len(faltan)
        con_barrio = sum(1 for n in cruzan if por_nombre[normalizar(n)].get("barrio_nombre"))
        print(f"  {archivo.parent.name:22} {len(nombres):3} proyectos | cruzan {len(cruzan):3} "
              f"| con barrio {con_barrio:3}")
        # Un nombre que no cruza no es fatal: ese proyecto se queda sin los dos
        # campos y la tarjeta simplemente no los pinta. Pero se reporta, que es
        # el contrato del repo con los datos que no encajan.
        if faltan:
            print(f"      sin cruce: {faltan[:3]}")
        if not escribir:
            continue

        def anadir(m: re.Match) -> str:
            proyecto = por_nombre.get(normalizar(m.group(1)))
            if not proyecto:
                return m.group(0)
            extra = ""
            if proyecto.get("direccion"):
                extra += ',"direccion":' + json.dumps(proyecto["direccion"], ensure_ascii=False)
            if proyecto.get("barrio_nombre"):
                extra += ',"barrio":' + json.dumps(proyecto["barrio_nombre"], ensure_ascii=False)
            return m.group(0) + extra

        limpio = RE_LIMPIAR.sub("", texto)          # idempotencia
        nuevo = RE_NAME.sub(anadir, limpio)
        archivo.write_text(nuevo, encoding="utf-8")
        print(f"      escrito ({len(nuevo) - len(texto):+d} bytes)")

    if not escribir:
        print("\n(informe; usa --escribir para aplicar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
