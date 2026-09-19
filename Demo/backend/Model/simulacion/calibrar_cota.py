"""
Model/simulacion/calibrar_cota.py
=================================
Calibra `COTA_MINIMA_COP` y mide qué le hace al top el reenfoque económico.

Por qué hace falta un instrumento aparte de `evaluar.py`: el recall que mide
`evaluar.py` compara contra la compra que simula `generar_historial.utilidad`,
y esa utilidad trata el precio de forma **asimétrica y truncada** — solo
penaliza cuando el proyecto exige más ingreso del que el usuario declara
(`_ajuste_precio` devuelve 0.0 en cuanto hay holgura). Es decir: para esa
"verdad", entre un proyecto de 182 millones y uno de 262 que el comprador
puede pagar, da exactamente igual cuál se le muestre.

El reenfoque de esta versión dice justo lo contrario: entre dos que puede
pagar, el barato es mejor recomendación. Así que medirlo solo con el recall
mide el desacuerdo con un simulador que no comparte el objetivo, y castiga el
cambio por construcción. Este script mide las dos cosas a la vez:

    recall@N        cuánto se pierde de fidelidad al criterio anterior
    precio del top  cuánto ahorra el comprador en lo que efectivamente ve
    años de pago    cuánto antes termina de pagarlo
    inalcanzables   cuántas casillas se dejan de gastar en lo que no puede pagar

Uso:
    python Model/simulacion/calibrar_cota.py
    python Model/simulacion/calibrar_cota.py --clientes 200 --cotas 0 10 20 50
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

from Model.cota_minima import COTA_MINIMA_COP, Cota_minimaBG  # noqa: E402
from Model.modelo import RUTA_HISTORIAL, RUTA_MODELO, _cargar_proyectos, modelo, primer_filtro  # noqa: E402
from Model.simulacion.evaluar import _clientes_de_prueba  # noqa: E402
from Model.simulacion.generar_historial import atractivo_latente, elegir_proyecto  # noqa: E402

# Lo que el usuario ve primero en la landing es el Top 3 (ver LiveDemo.tsx), y
# es donde el precio tiene que notarse. El Top completo se mide aparte.
VENTANA_VISIBLE = 3
TOP_N = 18
CLIENTES = 200
SEMILLA = 20261231

# Cotas a probar, en millones de COP. El 0 es el caso degenerado —cualquier
# diferencia de precio invierte, el top queda ordenado por plata y el modelo
# deja de decidir— y está en la lista justamente para poder verlo.
COTAS_MILLONES = (None, 0, 5, 10, 20, 30, 50, 100)


def _metricas(clientes, atractivo, rng, cota_cop, ruta_modelo, ruta_historial):
    """Corre el pipeline sobre todos los clientes con una cota dada."""
    precios_visible, precios_top, anos_visible = [], [], []
    aciertos = posiciones = evaluados = 0
    inalcanzables_visible = 0

    for usuario in clientes:
        candidatos = primer_filtro(usuario, ruta_modelo=ruta_modelo)
        if not candidatos:
            continue
        comprado = elegir_proyecto(usuario, candidatos, atractivo, rng)["id_proyecto"]
        evaluados += 1

        top = modelo(candidatos, usuario, ruta_historial=ruta_historial, top_n=TOP_N)
        if cota_cop is not None:
            top = Cota_minimaBG(top, usuario, cota_cop=cota_cop)

        ids = [p["id_proyecto"] for p in top]
        if comprado in ids:
            aciertos += 1
            posiciones += ids.index(comprado) + 1

        visibles = top[:VENTANA_VISIBLE]
        precios_visible += [p["precio_desde_cop"] for p in visibles if p.get("precio_desde_cop")]
        precios_top += [p["precio_desde_cop"] for p in top if p.get("precio_desde_cop")]
        anos_visible += [p["_anos_de_pago"] for p in visibles if p.get("_anos_de_pago")]
        inalcanzables_visible += sum(1 for p in visibles if p.get("_alcanzable") is False)

    return {
        "cota": cota_cop,
        "evaluados": evaluados,
        "recall": aciertos / evaluados if evaluados else 0.0,
        "posicion_media": posiciones / aciertos if aciertos else None,
        "precio_visible": statistics.mean(precios_visible) if precios_visible else 0.0,
        "precio_top": statistics.mean(precios_top) if precios_top else 0.0,
        "anos_visible": statistics.mean(anos_visible) if anos_visible else None,
        "inalcanzables_visible": inalcanzables_visible / evaluados if evaluados else 0.0,
    }


def calibrar(cantidad=CLIENTES, semilla=SEMILLA, cotas_millones=COTAS_MILLONES,
             ruta_modelo=RUTA_MODELO, ruta_historial=RUTA_HISTORIAL):
    proyectos = _cargar_proyectos(ruta_modelo)
    atractivo = atractivo_latente(proyectos)
    clientes = _clientes_de_prueba(cantidad, semilla, ruta_modelo)

    filas = []
    for millones in cotas_millones:
        cota = None if millones is None else millones * 1_000_000
        # Un rng nuevo por corrida: la compra simulada tiene que ser la misma
        # en todas las cotas, o se estaría comparando contra verdades distintas.
        filas.append(_metricas(clientes, atractivo, random.Random(semilla), cota,
                               ruta_modelo, ruta_historial))

    _reporte(filas)
    return filas


def _reporte(filas):
    base = next((f for f in filas if f["cota"] is None), filas[0])
    print()
    print("=" * 86)
    print(f" CALIBRACIÓN DE Cota_minimaBG  ·  {base['evaluados']} clientes de prueba no vistos")
    print("=" * 86)
    print(f" {'cota':>10} {'recall@18':>10} {'pos.media':>10} "
          f"{'precio top3':>14} {'ahorro':>9} {'años top3':>10} {'inalc.':>7}")
    print(" " + "-" * 84)
    for f in filas:
        cota = "sin cota" if f["cota"] is None else f"{f['cota'] // 1_000_000}M"
        ahorro = (base["precio_visible"] - f["precio_visible"]) / base["precio_visible"] * 100 \
            if base["precio_visible"] else 0.0
        precio = f"{f['precio_visible']:,.0f}".replace(",", ".")
        anos = f"{f['anos_visible']:.1f}" if f["anos_visible"] else "-"
        pos = f"{f['posicion_media']:.2f}" if f["posicion_media"] else "-"
        print(f" {cota:>10} {f['recall']:>9.1%} {pos:>10} {precio:>14} "
              f"{ahorro:>8.1f}% {anos:>10} {f['inalcanzables_visible']:>6.2f}")
    print("=" * 86)
    print(" recall@18 : la cota REORDENA, no selecciona -> tiene que salir plano.")
    print("             Si se mueve, algo está eliminando candidatos y es un bug.")
    print(" ahorro    : cuánto más barato es, en promedio, lo que el usuario ve")
    print("             primero. Es la métrica que este cambio persigue.")
    print(" inalc.    : proyectos por usuario, en el Top 3, que no puede pagar.")
    print()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clientes", type=int, default=CLIENTES)
    parser.add_argument("--semilla", type=int, default=SEMILLA)
    parser.add_argument("--cotas", type=int, nargs="*", default=None,
                        help="Cotas a probar, en millones de COP. "
                             f"Por defecto: {COTAS_MILLONES}")
    args = parser.parse_args()
    cotas = COTAS_MILLONES if args.cotas is None else [None] + list(args.cotas)
    calibrar(cantidad=args.clientes, semilla=args.semilla, cotas_millones=cotas)


if __name__ == "__main__":
    main()
