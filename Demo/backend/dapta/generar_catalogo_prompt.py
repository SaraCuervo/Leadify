"""Genera dapta/catalogo-proyectos.md a partir de proyectos_bogota.json.

Uso:
    python3 dapta/generar_catalogo_prompt.py > dapta/catalogo-proyectos.md

El resultado se pega dentro del prompt del agente de voz "Manuela" en Dapta,
como contexto de referencia para cuando el lead pregunta por otras zonas o
proyectos distintos al que ya trae en las variables de la llamada.
"""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "proyectos_bogota.json"


def cop_millones(valor: float) -> str:
    return f"${valor / 1_000_000:.1f}M".replace(".0M", "M")


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    proyectos = data["proyectos"]

    por_localidad: dict[str, list[dict]] = defaultdict(list)
    for p in proyectos:
        por_localidad[p["localidad_nombre"]].append(p)

    print(f"# Catálogo de proyectos ({len(proyectos)} proyectos, Bogotá)")
    print()
    print(
        "Referencia rápida por localidad. Úsalo SOLO si el lead pregunta por "
        "otra zona, otro proyecto o quiere comparar — el proyecto principal "
        "de esta llamada ya viene en {{proyecto_recomendado}} y las demás "
        "variables. No leas esta lista en voz alta ni la recites completa; "
        "menciona 1-2 opciones relevantes si preguntan."
    )
    print()

    for localidad in sorted(por_localidad):
        items = sorted(por_localidad[localidad], key=lambda p: p["precio_desde_cop"])
        print(f"## {localidad}")
        for p in items:
            zonas = p.get("zonas_comunes") or []
            zonas_txt = ", ".join(zonas[:6]) + (" y más" if len(zonas) > 6 else "")
            subsidio = "con subsidio caja" if p.get("aplica_subsidio_caja") else "sin subsidio caja"
            print(
                f"- **{p['nombre_proyecto']}** ({p['constructora']}, "
                f"{p['tipo_vivienda_publicado']}) — desde {cop_millones(p['precio_desde_cop'])}, "
                f"{p['area_desde_m2']:.0f}m²+, {subsidio}. Zonas: {zonas_txt or 'sin datos'}."
            )
        print()


if __name__ == "__main__":
    main()
