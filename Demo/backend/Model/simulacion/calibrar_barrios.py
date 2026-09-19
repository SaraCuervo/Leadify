"""
Model/simulacion/calibrar_barrios.py
====================================
Calibra `RADIO_CERCANIA_KM` y el peso de `localidad` en el score, y mide qué
le hace al top el grafo de barrios.

Qué se mide y por qué: el grafo de barrios (Model/grafo_barrios.py) no
cambia QUÉ candidatos entran —eso lo decide el BFS de localidades— sino
cuánto pesa la cercanía real dentro de la localidad. El efecto que persigue
es geográfico: que lo que el usuario ve quede más cerca de donde dijo que
vive. Pero cada punto de score que se le da a la cercanía se le quita al
resto, y el reenfoque económico (§4.5 del CLAUDE.md) está calibrado para que
la plata decida. Este script pone los dos en la misma tabla:

    km top3 / km top18   distancia media, por el grafo de barrios, entre el
                         barrio del cliente y lo que se le recomienda
    precio top3          lo que la landing muestra primero; no debería subir
    recall@18            fidelidad al criterio del simulador; no debería caer
    pos. media           dónde cae el acierto

Los clientes simulados no traen barrio (el formulario lo agregó la v0.4), así
que a cada uno se le sortea un sector urbano de SU localidad. La fila
`sin barrio` es la v0.3 exacta y es la base de comparación.

Uso:
    python Model/simulacion/calibrar_barrios.py
    python Model/simulacion/calibrar_barrios.py --clientes 200 --radios 8 12 20 --pesos 0.08 0.15
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys

# Ejecutable por ruta o como módulo. Ver generar_clientes.py.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")))

import Model.modelo as M  # noqa: E402
from Model import grafo_barrios as gb  # noqa: E402
from Model.cota_minima import Cota_minimaBG  # noqa: E402
from Model.modelo import RUTA_HISTORIAL, RUTA_MODELO, _cargar_proyectos, modelo, primer_filtro  # noqa: E402
from Model.simulacion.evaluar import _clientes_de_prueba  # noqa: E402
from Model.simulacion.generar_historial import atractivo_latente, elegir_proyecto  # noqa: E402

VENTANA_VISIBLE = 3
TOP_N = 18
CLIENTES = 200
SEMILLA = 20261231

# Radios (km) a los que la cercanía llega a 0, y pesos de `localidad` cuando
# hay barrio (`PESO_LOCALIDAD_CON_BARRIO`). Lo que se le suma a `localidad`
# se le quita a `modelo`, igual que se hizo al calibrar `esfuerzo` (§4.3).
RADIOS_KM = (8.0, 12.0, 20.0, 30.0)
PESOS_LOCALIDAD = (0.08, 0.12, 0.16)


def _barrio_al_azar(localidad, rng):
    """Un sector urbano con centroide de la localidad, o None si no hay."""
    grafo = gb.cargar_grafo()
    candidatos = [codigo for codigo, _ in gb.barrios_de_localidad(localidad)
                  if codigo.startswith("0") and grafo["barrios"][codigo].get("centroide")]
    return rng.choice(candidatos) if candidatos else None


def _km(barrio, proyecto):
    """Km del proyecto al barrio; estimados por salto de localidad si no tiene."""
    km = gb.distancia_barrios(barrio, proyecto.get("barrio_id"))
    if km is None:
        km = M.KM_BASE_SIN_BARRIO + M.KM_POR_SALTO_LOCALIDAD * proyecto["_distancia_localidad"]
    return km


def _metricas(clientes, barrios, atractivo, rng, con_barrio, radio_km, peso_localidad,
              ruta_modelo, ruta_historial):
    """Corre el pipeline sobre todos los clientes con una configuración dada."""
    radio_original, peso_original = M.RADIO_CERCANIA_KM, M.PESO_LOCALIDAD_CON_BARRIO
    M.RADIO_CERCANIA_KM = radio_km
    M.PESO_LOCALIDAD_CON_BARRIO = peso_localidad

    km_visible, km_top, precios_visible = [], [], []
    aciertos = posiciones = evaluados = 0
    try:
        for usuario, barrio in zip(clientes, barrios):
            segmentado = dict(usuario, barrio=barrio if con_barrio else None)
            candidatos = primer_filtro(segmentado, ruta_modelo=ruta_modelo)
            if not candidatos:
                continue
            comprado = elegir_proyecto(usuario, candidatos, atractivo, rng)["id_proyecto"]
            evaluados += 1

            top = modelo(candidatos, usuario, ruta_historial=ruta_historial, top_n=TOP_N)
            top = Cota_minimaBG(top, usuario)
            top.sort(key=lambda p: (p.get("_prioridad_filtro", 0), p.get("_orden_cota", 0)))

            ids = [p["id_proyecto"] for p in top]
            if comprado in ids:
                aciertos += 1
                posiciones += ids.index(comprado) + 1

            visibles = top[:VENTANA_VISIBLE]
            # La distancia se mide SIEMPRE desde el barrio sorteado, también en
            # la fila sin barrio: es la misma pregunta con y sin el dato.
            km_visible += [_km(barrio, p) for p in visibles]
            km_top += [_km(barrio, p) for p in top]
            precios_visible += [p["precio_desde_cop"] for p in visibles if p.get("precio_desde_cop")]
    finally:
        M.RADIO_CERCANIA_KM = radio_original
        M.PESO_LOCALIDAD_CON_BARRIO = peso_original

    return {
        "con_barrio": con_barrio,
        "radio": radio_km,
        "peso": peso_localidad,
        "evaluados": evaluados,
        "recall": aciertos / evaluados if evaluados else 0.0,
        "posicion_media": posiciones / aciertos if aciertos else None,
        "km_visible": statistics.mean(km_visible) if km_visible else 0.0,
        "km_top": statistics.mean(km_top) if km_top else 0.0,
        "precio_visible": statistics.mean(precios_visible) if precios_visible else 0.0,
    }


def calibrar(cantidad=CLIENTES, semilla=SEMILLA, radios=RADIOS_KM, pesos=PESOS_LOCALIDAD,
             ruta_modelo=RUTA_MODELO, ruta_historial=RUTA_HISTORIAL):
    if not gb.hay_grafo_barrios():
        raise RuntimeError("No hay grafo de barrios. Ejecuta: python Model/grafo_barrios.py")
    proyectos = _cargar_proyectos(ruta_modelo)
    atractivo = atractivo_latente(proyectos)
    clientes = _clientes_de_prueba(cantidad, semilla, ruta_modelo)
    sorteo = random.Random(semilla)
    barrios = [_barrio_al_azar(u["localidad"], sorteo) for u in clientes]
    pares = [(u, b) for u, b in zip(clientes, barrios) if b]
    clientes, barrios = [u for u, _ in pares], [b for _, b in pares]

    filas = [_metricas(clientes, barrios, atractivo, random.Random(semilla), False,
                       M.RADIO_CERCANIA_KM, M.PESO_LOCALIDAD_CON_BARRIO, ruta_modelo, ruta_historial)]
    for peso in pesos:
        for radio in radios:
            # Un rng nuevo por corrida: la compra simulada tiene que ser la
            # misma en todas, o se compararía contra verdades distintas.
            filas.append(_metricas(clientes, barrios, atractivo, random.Random(semilla), True,
                                   radio, peso, ruta_modelo, ruta_historial))
    _reporte(filas)
    return filas


def _reporte(filas):
    base = filas[0]
    print()
    print("=" * 92)
    print(f" CALIBRACIÓN DEL GRAFO DE BARRIOS  ·  {base['evaluados']} clientes de prueba con barrio sorteado")
    print("=" * 92)
    print(f" {'config':>18} {'recall@18':>10} {'pos.media':>10} {'km top3':>9} {'km top18':>9} "
          f"{'precio top3':>14} {'vs base':>8}")
    print(" " + "-" * 90)
    for f in filas:
        nombre = "sin barrio (v0.3)" if not f["con_barrio"] else f"r={f['radio']:.0f}km w={f['peso']:.2f}"
        pos = f"{f['posicion_media']:.2f}" if f["posicion_media"] else "-"
        precio = f"{f['precio_visible']:,.0f}".replace(",", ".")
        delta = (f["precio_visible"] - base["precio_visible"]) / base["precio_visible"] * 100 \
            if base["precio_visible"] else 0.0
        print(f" {nombre:>18} {f['recall']:>9.1%} {pos:>10} {f['km_visible']:>9.2f} {f['km_top']:>9.2f} "
              f"{precio:>14} {delta:>+7.1f}%")
    print("=" * 92)
    print(" km top3/top18 : distancia media por el grafo de barrios entre el barrio del")
    print("                 cliente y lo recomendado. Es la métrica que este cambio persigue.")
    print(" precio top3   : no debería subir: la cercanía no puede comprarse con plata del comprador.")
    print(" recall@18     : el barrio no filtra; cambia el orden y, en el margen, quién entra al 18.")
    print(" w             : PESO_LOCALIDAD_CON_BARRIO; lo que sube se le quita a `modelo`. Sin barrio")
    print("                 rige PESOS_SCORE tal cual, por eso la base es la v0.3 exacta.")
    print()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clientes", type=int, default=CLIENTES)
    parser.add_argument("--semilla", type=int, default=SEMILLA)
    parser.add_argument("--radios", type=float, nargs="*", default=None,
                        help=f"Radios en km a probar. Por defecto: {RADIOS_KM}")
    parser.add_argument("--pesos", type=float, nargs="*", default=None,
                        help=f"Pesos de `localidad` a probar. Por defecto: {PESOS_LOCALIDAD}")
    args = parser.parse_args()
    calibrar(cantidad=args.clientes, semilla=args.semilla,
             radios=RADIOS_KM if args.radios is None else args.radios,
             pesos=PESOS_LOCALIDAD if args.pesos is None else args.pesos)


if __name__ == "__main__":
    main()
