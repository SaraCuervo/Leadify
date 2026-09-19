"""
generar_historial.py
====================
Simula el historial de interacciones que alimenta el modo colaborativo del
modelo y lo escribe en `historial_simulado.json`.

Los perfiles NO son uniformes: se construyen sobre la distribución real de
compradores de vivienda de Camacol para Bogotá–Cundinamarca.

    Edad de los compradores          Perfiles dominantes
    ------------------------         -------------------------------------
    < 25 años ............ 10.0%     25–35: ingresos 2–4 SMMLV, solteros
    25–35 años ........... 36.6%     36–51: ingresos ~8 SMMLV, casados
    36–50 años ........... 30.5%
    > 50 años ............ 22.9%

Sobre esa base se condicionan salario, personas a cargo, tipo de vivienda y
habitaciones, y se le añade ruido para que la simulación no sea determinista.
La elección de proyecto pasa por el mismo `primer_filtro` del pipeline y luego
por un softmax sobre una utilidad que mezcla afinidad de perfil, cobertura de
zonas, cercanía, capacidad de pago y un atractivo latente por proyecto.

Uso:
    python generar_historial.py
    python generar_historial.py --n 8000 --semilla 42
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
from collections import Counter
from datetime import date, timedelta

from Model.catalogos import ZONAS_COMUNES, nombre_localidad, nombre_tipo_vivienda
from Model.modelo import (
    DISTANCIA_MAXIMA,
    PESOS_SCORE,
    RUTA_HISTORIAL,
    RUTA_MODELO,
    _cargar_proyectos,
    _escalar_vector,
    leer_info_user,
    primer_filtro,
)

from Model.rutas import RUTA_CLIENTES
INTERACCIONES_POR_CLIENTE = 8

N_REGISTROS = 4000
MIN_POR_PROYECTO = 30       # piso de cobertura: por debajo, el proyecto es invisible
FECHA_FIN = date(2026, 8, 13)
MESES_HISTORIA = 18

# ---------------------------------------------------------------------------
# Distribuciones demográficas (Camacol Bogotá–Cundinamarca)
# ---------------------------------------------------------------------------
# (edad_min, edad_max, participación)
BANDAS_EDAD = [
    (18, 24, 0.100),
    (25, 35, 0.366),
    (36, 50, 0.305),
    (51, 70, 0.229),
]

# Salario (código 1..4) condicionado a la banda de edad.
# Camacol: el grupo de 25–35 se concentra en 2–4 SMMLV; el de 36–51 alcanza ~8.
DIST_SALARIO = {
    0: [0.45, 0.40, 0.13, 0.02],   # < 25: primer empleo
    1: [0.18, 0.50, 0.26, 0.06],   # 25–35: núcleo 2–4 SMMLV
    2: [0.08, 0.30, 0.42, 0.20],   # 36–50: pico de capacidad de pago
    3: [0.10, 0.28, 0.38, 0.24],   # > 50
}

# Personas a cargo (1..4) condicionadas a la edad: solteros jóvenes, etapa
# familiar en la mediana edad, nido vacío después.
DIST_PERSONAS = {
    0: [0.60, 0.28, 0.09, 0.03],
    1: [0.38, 0.34, 0.19, 0.09],
    2: [0.14, 0.26, 0.32, 0.28],
    3: [0.30, 0.36, 0.22, 0.12],
}

# A mayor ingreso, menos probable que la búsqueda sea VIS.
PROB_VIS = {1: 0.95, 2: 0.82, 3: 0.45, 4: 0.12}

# Habitaciones buscadas según el tamaño del hogar.
DIST_HABITACIONES = {
    1: [0.55, 0.35, 0.10],
    2: [0.25, 0.50, 0.25],
    3: [0.08, 0.42, 0.50],
    4: [0.04, 0.26, 0.70],
}

# Afiliación a caja de compensación: más frecuente en rentas medias-bajas.
PROB_AFILIADO = {1: 0.88, 2: 0.80, 3: 0.62, 4: 0.40}

# Popularidad relativa de cada zona común al momento de marcarla como deseada.
POPULARIDAD_ZONAS = [
    0.55, 0.45, 0.35, 0.60, 0.30, 0.50, 0.25, 0.40, 0.55, 0.10,
    0.20, 0.25, 0.45, 0.25, 0.15, 0.70, 0.65, 0.45, 0.30, 0.35,
    0.20, 0.05, 0.15, 0.20, 0.10,
]

# Tipo de evento y su peso como señal de preferencia.
EVENTOS = [("vista", 0.2, 0.62), ("lead", 0.6, 0.28), ("compra", 1.0, 0.10)]

# Punto medio de cada rango salarial, en SMMLV, para evaluar capacidad de pago.
MEDIA_SMMLV = {1: 1.5, 2: 3.0, 3: 6.0, 4: 11.0}

# Pesos de la utilidad que decide la compra.
W_PERFIL, W_ZONAS, W_LOCALIDAD, W_PRECIO = 1.00, 0.55, 0.45, 0.90
TEMPERATURA = 0.22          # más baja = elecciones más marcadas


def _elegir(opciones, pesos, rng):
    return rng.choices(opciones, weights=pesos, k=1)[0]


def _banda_edad(rng):
    """Devuelve (indice_de_banda, edad) muestreando la distribución Camacol."""
    idx = _elegir(range(len(BANDAS_EDAD)), [b[2] for b in BANDAS_EDAD], rng)
    minimo, maximo, _ = BANDAS_EDAD[idx]
    return idx, rng.randint(minimo, maximo)


def perfil_usuario(rng, pesos_localidad):
    """Genera un usuario sintético coherente con las distribuciones reales."""
    banda, edad = _banda_edad(rng)
    salario = _elegir([1, 2, 3, 4], DIST_SALARIO[banda], rng)
    personas = _elegir([1, 2, 3, 4], DIST_PERSONAS[banda], rng)
    tipo = 1 if rng.random() < PROB_VIS[salario] else 0
    habitaciones = _elegir([1, 2, 3], DIST_HABITACIONES[personas], rng)
    localidad = _elegir(list(pesos_localidad), list(pesos_localidad.values()), rng)

    # Entre 3 y 7 zonas comunes, muestreadas por popularidad y sin repetir.
    objetivo = rng.randint(3, 7)
    zonas = set()
    while len(zonas) < objetivo:
        idx = _elegir(range(len(ZONAS_COMUNES)), POPULARIDAD_ZONAS, rng)
        zonas.add(idx)

    return {
        "salario": salario,
        "personas_a_cargo": personas,
        "edad": edad,
        "tipo_vivienda": tipo,
        "localidad": localidad,
        "numero_habitaciones": habitaciones,
        "zonas_comunes": sorted(zonas),
        "afiliado": rng.random() < PROB_AFILIADO[salario],
    }


def cargar_clientes(ruta=RUTA_CLIENTES):
    """Lee los clientes de `simulacion/` y los baja a la forma interna.

    Cada cliente viene en el contrato del formulario (`Localidad`, zonas
    comunes por nombre). Se traduce con el mismo `leer_info_user` que usa el
    pipeline en producción, no con un parser paralelo: así la simulación
    valida de paso que esos payloads son aceptables para el modelo, y un
    cambio en el contrato rompe aquí en vez de romper en el front.
    """
    if not os.path.exists(ruta):
        raise FileNotFoundError(
            f"No existe {ruta}. Ejecuta primero: python simulacion/generar_clientes.py"
        )
    with open(ruta, "r", encoding="utf-8") as archivo:
        datos = json.load(archivo)
    crudos = datos["clientes"] if isinstance(datos, dict) else datos

    clientes = []
    for crudo in crudos:
        modelo_usuario, segmentado, contacto = leer_info_user(crudo)
        clientes.append({
            "salario": modelo_usuario["salario"],
            "personas_a_cargo": modelo_usuario["personas_a_cargo"],
            "edad": modelo_usuario["edad"],
            "tipo_vivienda": segmentado["tipo_vivienda"],
            "localidad": segmentado["localidad"],
            "numero_habitaciones": segmentado["numero_habitaciones"],
            "zonas_comunes": segmentado["zonas_comunes"],
            "afiliado": contacto["afiliado"],
            "_arquetipo": crudo.get("_arquetipo"),
        })
    return clientes


def _afinidad_perfil(usuario, proyecto):
    """1 = perfil idéntico, 0 = lo más lejano posible en el espacio del modelo."""
    a = _escalar_vector(usuario["salario"], usuario["personas_a_cargo"], usuario["edad"])
    b = _escalar_vector(proyecto["salario_objetivo"], proyecto["personas_objetivo"],
                        proyecto["edad_objetivo"])
    distancia = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    return max(0.0, 1.0 - distancia / DISTANCIA_MAXIMA)


def _ajuste_precio(usuario, proyecto):
    """Penaliza los proyectos que exigen más ingreso del que declara el usuario."""
    campo = ("ingreso_requerido_smmlv_con_subsidio" if usuario["afiliado"]
             else "ingreso_requerido_smmlv")
    requerido = proyecto.get(campo, proyecto.get("ingreso_requerido_smmlv", 0))
    holgura = MEDIA_SMMLV[usuario["salario"]] - requerido
    if holgura >= 0:
        return 0.0
    return -min(1.0, -holgura / 4.0)      # a 4 SMMLV de déficit, penalización máxima


def utilidad(usuario, proyecto, atractivo):
    """Qué tan probable es que este usuario se incline por este proyecto."""
    return (W_PERFIL * _afinidad_perfil(usuario, proyecto)
            + W_ZONAS * proyecto.get("_cobertura_zonas", 0.0)
            + W_LOCALIDAD * max(0.0, 1 - 0.25 * proyecto.get("_distancia_localidad", 0))
            + W_PRECIO * _ajuste_precio(usuario, proyecto)
            + atractivo[proyecto["id_proyecto"]])


def elegir_proyecto(usuario, candidatos, atractivo, rng):
    """Softmax sobre la utilidad: preferencia clara pero no determinista."""
    utilidades = [utilidad(usuario, p, atractivo) for p in candidatos]
    techo = max(utilidades)
    pesos = [math.exp((u - techo) / TEMPERATURA) for u in utilidades]
    return _elegir(candidatos, pesos, rng)


def _registro(usuario, proyecto, rng):
    nombre, peso, _ = _elegir(EVENTOS, [e[2] for e in EVENTOS], rng)
    dias = rng.randint(0, MESES_HISTORIA * 30)
    return {
        # --- lo que consume el modelo ---
        "salario": usuario["salario"],
        "personas_a_cargo": usuario["personas_a_cargo"],
        "edad": usuario["edad"],
        "id_proyecto": proyecto["id_proyecto"],
        "interaccion": peso,
        # --- contexto, útil para inspeccionar la simulación ---
        "evento": nombre,
        "fecha": (FECHA_FIN - timedelta(days=dias)).isoformat(),
        "tipo_vivienda": nombre_tipo_vivienda(usuario["tipo_vivienda"]),
        "localidad_buscada": nombre_localidad(usuario["localidad"]),
        "numero_habitaciones": usuario["numero_habitaciones"],
        "afiliado": usuario["afiliado"],
        "nombre_proyecto": proyecto["nombre_proyecto"],
        "arquetipo": usuario.get("_arquetipo"),
    }


SEMILLA_ATRACTIVO = 20260813


def atractivo_latente(proyectos, semilla=SEMILLA_ATRACTIVO):
    """"Calidad percibida" de cada proyecto, invisible para el modelo.

    Es lo que las etiquetas de `prep.py` no capturan —la reputación del
    proyecto, lo bien que quedaron los renders, lo que dice la gente— y que
    solo el historial puede revelarle al recomendador. Se deriva de una
    semilla propia y fija para que el historial de entrenamiento y el conjunto
    de prueba compartan el mismo mundo: si cada uno inventara su atractivo, el
    componente colaborativo no tendría nada real que aprender y la evaluación
    mediría ruido.
    """
    rng = random.Random(semilla)
    return {p["id_proyecto"]: rng.uniform(-0.30, 0.30) for p in proyectos}


def _pesos_localidad(proyectos):
    """Las búsquedas se concentran donde hay oferta, pero ninguna localidad queda en cero."""
    stock = Counter(p["localidad_id"] for p in proyectos if p.get("localidad_id"))
    return {loc: 1.0 + 3.0 * stock.get(loc, 0) for loc in range(1, 21)}


def _usuario_afin_a(proyecto, rng):
    """Usuario construido a la medida de un proyecto, para rellenar cobertura."""
    ruido = lambda v, lo, hi: max(lo, min(hi, v + rng.choice([-1, 0, 0, 1])))
    return {
        "salario": ruido(proyecto["salario_objetivo"], 1, 4),
        "personas_a_cargo": ruido(proyecto["personas_objetivo"], 1, 4),
        "edad": max(18, min(70, proyecto["edad_objetivo"] + rng.randint(-4, 4))),
        "tipo_vivienda": proyecto["tipo_vivienda_cod"],
        "localidad": proyecto["localidad_id"],
        "numero_habitaciones": min(3, proyecto["habitaciones_max"] or 1),
        "zonas_comunes": sorted(rng.sample(proyecto["zonas_comunes_idx"],
                                           min(3, len(proyecto["zonas_comunes_idx"])))),
        "afiliado": rng.random() < 0.75,
    }


def generar(n=N_REGISTROS, semilla=None, ruta_modelo=RUTA_MODELO,
            ruta_salida=RUTA_HISTORIAL, min_por_proyecto=MIN_POR_PROYECTO, verbose=True,
            ruta_clientes=RUTA_CLIENTES, interacciones_por_cliente=INTERACCIONES_POR_CLIENTE):
    """Genera el historial simulado y lo escribe en disco.

    Dos modos, según de dónde salgan los usuarios:

    - **Arquetipos** (por defecto): lee `simulacion/clientes_simulados.json` y
      le hace vivir a cada cliente `interacciones_por_cliente` eventos. Con
      1.000 clientes y 8 eventos salen los 8.000 registros. Es el modo bueno
      para el componente colaborativo: los clientes se repiten entre eventos,
      así que hay clústeres reales de gente parecida que el modelo puede
      encontrar.

    - **Muestreo demográfico** (`ruta_clientes=None`): genera `n` usuarios
      independientes desde las distribuciones de Camacol. Cada registro es de
      una persona distinta, de modo que no hay a quién parecerse: sirve para
      contrastar, no para entrenar.
    """
    rng = random.Random(semilla)
    proyectos = _cargar_proyectos(ruta_modelo)
    pesos_localidad = _pesos_localidad(proyectos)

    atractivo = atractivo_latente(proyectos)

    historial = []
    if ruta_clientes:
        clientes = cargar_clientes(ruta_clientes)
        modo = f"arquetipos ({len(clientes)} clientes x {interacciones_por_cliente} eventos)"
        for usuario in clientes:
            candidatos = primer_filtro(usuario, ruta_modelo=ruta_modelo)
            if not candidatos:
                continue
            # Cada evento es un sorteo independiente sobre los mismos
            # candidatos: una persona mira varios proyectos y a veces vuelve
            # al mismo, que es justo la señal que el colaborativo aprovecha.
            for _ in range(interacciones_por_cliente):
                elegido = elegir_proyecto(usuario, candidatos, atractivo, rng)
                historial.append(_registro(usuario, elegido, rng))
    else:
        modo = f"muestreo demográfico ({n} usuarios independientes)"
        for _ in range(n):
            usuario = perfil_usuario(rng, pesos_localidad)
            candidatos = primer_filtro(usuario, ruta_modelo=ruta_modelo)
            if not candidatos:
                continue
            historial.append(
                _registro(usuario, elegir_proyecto(usuario, candidatos, atractivo, rng), rng)
            )

    # Piso de cobertura: sin un mínimo de interacciones un proyecto nunca
    # aparece por la vía colaborativa, y el muestreo realista concentra la
    # demanda en unos pocos.
    rellenados = 0
    cuenta = Counter(r["id_proyecto"] for r in historial)
    por_id = {p["id_proyecto"]: p for p in proyectos}
    for id_proyecto, proyecto in por_id.items():
        while cuenta[id_proyecto] < min_por_proyecto:
            historial.append(_registro(_usuario_afin_a(proyecto, rng), proyecto, rng))
            cuenta[id_proyecto] += 1
            rellenados += 1

    rng.shuffle(historial)

    salida = {
        "meta": {
            "generado_en": FECHA_FIN.isoformat(),
            "n_registros": len(historial),
            "modo": modo,
            "n_rellenados_por_cobertura": rellenados,
            "min_por_proyecto": min_por_proyecto,
            "n_proyectos": len(proyectos),
            "semilla": semilla,
            "fuente_demografica": (
                "Camacol Bogotá–Cundinamarca: 10% <25 años, 36.6% 25–35, "
                "30.5% 36–50, 22.9% >50. Perfiles 25–35 con 2–4 SMMLV y "
                "36–51 con ~8 SMMLV."
            ),
            "advertencia": "Datos sintéticos para demostración. No son transacciones reales.",
        },
        "historial": historial,
    }
    with open(ruta_salida, "w", encoding="utf-8") as archivo:
        json.dump(salida, archivo, ensure_ascii=False, indent=2)

    if verbose:
        _reporte(salida, ruta_salida)
    return salida


def _reporte(salida, ruta_salida):
    historial = salida["historial"]
    print(f"[historial] {len(historial)} registros -> {os.path.basename(ruta_salida)}")
    print(f"[historial] modo     : {salida['meta']['modo']}")
    print(f"[historial] rellenados por cobertura: {salida['meta']['n_rellenados_por_cobertura']}")
    edades = [r["edad"] for r in historial]
    bandas = Counter("<25" if e < 25 else "25-35" if e <= 35 else "36-50" if e <= 50 else ">50"
                     for e in edades)
    total = len(historial)
    print("[historial] edad     : " + "  ".join(
        f"{k}={v / total:.1%}" for k, v in sorted(bandas.items())))
    print(f"[historial] salario  : {dict(sorted(Counter(r['salario'] for r in historial).items()))}")
    print(f"[historial] personas : {dict(sorted(Counter(r['personas_a_cargo'] for r in historial).items()))}")
    print(f"[historial] evento   : {dict(Counter(r['evento'] for r in historial))}")
    print(f"[historial] vivienda : {dict(Counter(r['tipo_vivienda'] for r in historial))}")
    arquetipos = Counter(r["arquetipo"] for r in historial if r.get("arquetipo"))
    if arquetipos:
        print(f"[historial] arquetipos: {len(arquetipos)} | "
              + ", ".join(f"{k}={v}" for k, v in arquetipos.most_common(4)) + ", ...")
    cuenta = Counter(r["id_proyecto"] for r in historial)
    total_proyectos = salida["meta"].get("n_proyectos", len(cuenta))
    print(f"[historial] proyectos: {len(cuenta)}/{total_proyectos} con datos | "
          f"mín={min(cuenta.values())} máx={max(cuenta.values())} "
          f"media={sum(cuenta.values()) / len(cuenta):.0f}")


def main():
    parser = argparse.ArgumentParser(description="Genera el historial simulado de interacciones.")
    parser.add_argument("--clientes", default=RUTA_CLIENTES,
                        help="Clientes de simulacion/. Por defecto, los 1.000 de los arquetipos.")
    parser.add_argument("--interacciones", type=int, default=INTERACCIONES_POR_CLIENTE,
                        help="Eventos por cliente (1.000 x 8 = 8.000 registros).")
    parser.add_argument("--demografico", action="store_true",
                        help="Ignora los arquetipos y muestrea usuarios independientes.")
    parser.add_argument("--n", type=int, default=N_REGISTROS,
                        help="Usuarios a simular en modo --demografico.")
    parser.add_argument("--semilla", type=int, default=None, help="Semilla para reproducibilidad.")
    parser.add_argument("--modelo", default=RUTA_MODELO, help="Ruta de proyectos_model.json.")
    parser.add_argument("--salida", default=RUTA_HISTORIAL, help="Ruta del historial de salida.")
    parser.add_argument("--min-por-proyecto", type=int, default=MIN_POR_PROYECTO,
                        help="Interacciones mínimas garantizadas por proyecto.")
    args = parser.parse_args()
    generar(args.n, semilla=args.semilla, ruta_modelo=args.modelo,
            ruta_salida=args.salida, min_por_proyecto=args.min_por_proyecto,
            ruta_clientes=None if args.demografico else args.clientes,
            interacciones_por_cliente=args.interacciones)


if __name__ == "__main__":
    main()
