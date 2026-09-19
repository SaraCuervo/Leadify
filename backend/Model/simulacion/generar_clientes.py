"""
simulacion/generar_clientes.py
==============================
Convierte los 10 arquetipos en 1.000 clientes simulados: 100 variaciones de
cada uno.

Cada cliente sale con **exactamente el mismo contrato JSON que manda el front**
(las 15 llaves del formulario), así que sirve para dos cosas a la vez:

1. Alimentar `generar_historial.py`, que le hace elegir proyectos y produce el
   historial de interacciones con el que entrena el modo colaborativo.
2. Servir de banco de pruebas: cualquiera de estos clientes se le puede pasar
   tal cual a `main.recomendar()`.

Uso:
    python simulacion/generar_clientes.py
    python simulacion/generar_clientes.py --variaciones 100 --semilla 42
    python simulacion/generar_clientes.py --salida otros_clientes.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter

# Funciona igual ejecutado por ruta (`python Model/simulacion/generar_clientes.py`)
# que como módulo (`python -m Model.simulacion.generar_clientes`): en el primer
# caso Python pone en el path esta carpeta y no `backend/`, así que el paquete
# `Model` no se encontraría.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")))

from Model.catalogos import ZONAS_COMUNES, nombre_localidad, nombre_tipo_vivienda  # noqa: E402

from Model.simulacion.arquetipos import ARQUETIPOS, validar  # noqa: E402

from Model.rutas import RUTA_CLIENTES as RUTA_SALIDA
VARIACIONES = 100

# Cuánto se deja derivar cada variación de su arquetipo. Sin esta deriva las
# 100 variaciones serían 100 copias con ruido cosmético, el modelo colaborativo
# vería 10 puntos en vez de 1.000 y el K de vecinos dejaría de significar algo.
PROB_LOCALIDAD_FUERA = 0.12    # busca en una localidad que su arquetipo no lista
PROB_SALTO_SALARIO = 0.15      # se corre un tramo de ingreso
PROB_SALTO_PERSONAS = 0.15     # cambia el tamaño del hogar
PROB_OLVIDA_NUCLEO = 0.20      # no marca una de sus amenidades características
ZONAS_OPCIONALES_MIN = 1
ZONAS_OPCIONALES_MAX = 4


def _elegir_pesos(pesos, rng):
    """Muestrea una llave de un dict {valor: peso}."""
    valores = list(pesos)
    return rng.choices(valores, weights=[pesos[v] for v in valores], k=1)[0]


def _acotar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def _zonas_del_cliente(arquetipo, rng):
    """Amenidades que marca esta variación.

    El núcleo del arquetipo casi siempre entra —es lo que lo define— y encima
    se le suman entre 1 y 4 opcionales. Que a veces olvide una del núcleo es
    deliberado: en el formulario real nadie marca siempre lo mismo, y si el
    núcleo fuera obligatorio las variaciones se volverían indistinguibles.
    """
    zonas = {z for z in arquetipo["zonas_nucleo"] if rng.random() > PROB_OLVIDA_NUCLEO}
    opcionales = list(arquetipo["zonas_opcionales"])
    rng.shuffle(opcionales)
    zonas.update(opcionales[:rng.randint(ZONAS_OPCIONALES_MIN, ZONAS_OPCIONALES_MAX)])
    if not zonas:                       # nunca se manda una lista vacía
        zonas.add(rng.choice(arquetipo["zonas_nucleo"]))
    return sorted(zonas)


def _localidad_del_cliente(arquetipo, rng):
    if rng.random() < PROB_LOCALIDAD_FUERA:
        return rng.randint(1, 20)
    return _elegir_pesos(arquetipo["localidades"], rng)


def cliente_desde_arquetipo(arquetipo, numero, rng):
    """Una variación del arquetipo, en el formato del formulario del front."""
    edad_min, edad_max = arquetipo["edad"]
    edad = rng.randint(edad_min, edad_max)

    salario = _elegir_pesos(arquetipo["salario"], rng)
    if rng.random() < PROB_SALTO_SALARIO:
        salario = _acotar(salario + rng.choice([-1, 1]), 1, 4)

    personas = _elegir_pesos(arquetipo["personas_a_cargo"], rng)
    if rng.random() < PROB_SALTO_PERSONAS:
        personas = _acotar(personas + rng.choice([-1, 1]), 1, 4)

    habitaciones = _elegir_pesos(arquetipo["habitaciones"], rng)
    # Coherencia interna: un hogar de 4 no busca un aparta-estudio. Se corrige
    # al alza en vez de descartar la variación, para no sesgar el muestreo.
    if personas >= 3 and habitaciones == 1:
        habitaciones = 2

    tipo_vivienda = 1 if rng.random() < arquetipo["prob_vis"] else 0
    afiliado = 1 if rng.random() < arquetipo["prob_afiliado"] else 0
    localidad = _localidad_del_cliente(arquetipo, rng)
    zonas = _zonas_del_cliente(arquetipo, rng)

    # Identidad sintética y evidente. No se generan nombres verosímiles a
    # propósito: estos registros van a un JSON que se comparte, y no deben
    # poder confundirse con personas reales.
    etiqueta = f"{arquetipo['id']}-{numero:03d}"

    return {
        # --- contrato del formulario (las 15 llaves, en orden) ---
        "id_proyecto": None,
        "nombres": f"Cliente {numero:03d}",
        "apellidos": f"Simulado ({arquetipo['nombre']})",
        "correo": f"{etiqueta}@ejemplo.local",
        "telefono": 3000000000 + rng.randint(0, 99_999_999),
        "afiliado": afiliado,
        "tipo_vivienda": tipo_vivienda,
        "salario": salario,
        "personas_a_cargo": personas,
        "edad": edad,
        "Localidad": localidad,
        "numero_habitaciones": habitaciones,
        "piso": _elegir_pesos(arquetipo["piso"], rng),
        "zonas_comunes": [ZONAS_COMUNES[i] for i in zonas],
        "link_proyecto": None,

        # --- trazabilidad de la simulación ---
        "_arquetipo": arquetipo["id"],
        "_arquetipo_nombre": arquetipo["nombre"],
        "_variacion": numero,
        "_localidad_nombre": nombre_localidad(localidad),
        "_tipo_vivienda_nombre": nombre_tipo_vivienda(tipo_vivienda),
        "_zonas_comunes_idx": zonas,
    }


def generar(variaciones=VARIACIONES, semilla=None, ruta_salida=RUTA_SALIDA, verbose=True):
    """Genera `variaciones` clientes por arquetipo y los escribe en disco."""
    validar()
    rng = random.Random(semilla)

    clientes = []
    for arquetipo in ARQUETIPOS:
        for numero in range(1, variaciones + 1):
            clientes.append(cliente_desde_arquetipo(arquetipo, numero, rng))

    salida = {
        "meta": {
            "n_arquetipos": len(ARQUETIPOS),
            "variaciones_por_arquetipo": variaciones,
            "n_clientes": len(clientes),
            "semilla": semilla,
            "arquetipos": [
                {"id": a["id"], "nombre": a["nombre"], "descripcion": a["descripcion"]}
                for a in ARQUETIPOS
            ],
            "advertencia": (
                "Clientes sintéticos para entrenar y probar el recomendador. "
                "No corresponden a personas reales."
            ),
        },
        "clientes": clientes,
    }

    os.makedirs(os.path.dirname(ruta_salida) or ".", exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8") as archivo:
        json.dump(salida, archivo, ensure_ascii=False, indent=2)

    if verbose:
        _reporte(salida, ruta_salida)
    return salida


def _reporte(salida, ruta_salida):
    clientes = salida["clientes"]
    print(f"[clientes] {len(clientes)} clientes -> {os.path.relpath(ruta_salida)}")
    print(f"[clientes] {salida['meta']['n_arquetipos']} arquetipos x "
          f"{salida['meta']['variaciones_por_arquetipo']} variaciones")
    print(f"[clientes] salario  : {dict(sorted(Counter(c['salario'] for c in clientes).items()))}")
    print(f"[clientes] personas : {dict(sorted(Counter(c['personas_a_cargo'] for c in clientes).items()))}")
    print(f"[clientes] habitac. : {dict(sorted(Counter(c['numero_habitaciones'] for c in clientes).items()))}")
    print(f"[clientes] vivienda : {dict(Counter(c['_tipo_vivienda_nombre'] for c in clientes))}")
    print(f"[clientes] afiliados: {sum(c['afiliado'] for c in clientes)} de {len(clientes)}")
    edades = [c["edad"] for c in clientes]
    bandas = Counter("<25" if e < 25 else "25-35" if e <= 35 else "36-50" if e <= 50 else ">50"
                     for e in edades)
    total = len(clientes)
    print("[clientes] edad     : " + "  ".join(
        f"{k}={v / total:.1%}" for k, v in sorted(bandas.items())))
    localidades = Counter(c["_localidad_nombre"] for c in clientes)
    print(f"[clientes] localidad: {len(localidades)}/20 con demanda | "
          f"top {', '.join(f'{k} {v}' for k, v in localidades.most_common(5))}")


def main():
    parser = argparse.ArgumentParser(
        description="Genera los clientes simulados a partir de los 10 arquetipos."
    )
    parser.add_argument("--variaciones", type=int, default=VARIACIONES,
                        help="Variaciones por arquetipo (por defecto 100).")
    parser.add_argument("--semilla", type=int, default=None,
                        help="Semilla para reproducibilidad.")
    parser.add_argument("--salida", default=RUTA_SALIDA, help="Ruta del JSON de salida.")
    args = parser.parse_args()
    generar(variaciones=args.variaciones, semilla=args.semilla, ruta_salida=args.salida)


if __name__ == "__main__":
    main()
