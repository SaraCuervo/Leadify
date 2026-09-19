"""
prep.py
=======
Etapa de preparación de datos del recomendador.

Lee `proyectos_seed.json` (datos crudos scrapeados de las fichas de proyecto),
normaliza los campos categóricos y **etiqueta** cada proyecto con el perfil de
comprador al que apunta, de modo que quede en el mismo espacio de features que
el `usuario_modelo` que consume el modelo de Nearest Neighbors:

    perfil_vector = [salario_objetivo, personas_objetivo, edad_objetivo]

El resultado se escribe en `proyectos_model.json`.

Uso:
    python prep.py
    python prep.py --seed otros_datos.json --salida otro_modelo.json
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone

# Ejecutable por ruta (`python Model/prep.py`) o como módulo
# (`python -m Model.prep`): en el primer caso Python pone en el path esta
# carpeta y no `backend/`, así que el paquete `Model` no se encontraría.
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Model.catalogos import (
    LOCALIDADES_BOGOTA,
    ZONAS_COMUNES,
    codigo_tipo_vivienda,
    indice_localidad,
    mapear_zonas,
    nombre_localidad,
    nombre_tipo_vivienda,
    nombres_zonas,
    vector_zonas,
)

# El catálogo por defecto es el que produce `scraping/scraper_projects.py`. Se
# mantiene el seed manual como respaldo para poder correr prep sin haber
# scrapeado. Las dos rutas viven en `Model/rutas.py`.
from Model.rutas import RUTA_CATALOGO, RUTA_MODELO, RUTA_SEED_MANUAL

RUTA_SEED = RUTA_CATALOGO if os.path.exists(RUTA_CATALOGO) else RUTA_SEED_MANUAL

# ---------------------------------------------------------------------------
# Supuestos económicos usados para etiquetar el salario objetivo.
# Están centralizados aquí porque son los parámetros que más se revisan.
#
# Hasta la v0.2 estos supuestos eran UNO SOLO para todo el catálogo: 30% de
# cuota inicial, 240 meses y una cuota tope del 30% del ingreso, tanto para
# una VIS de 200 millones como para una No VIS de 800. Eso no es como se
# financia vivienda en Colombia, y el sesgo no era neutro: le exigía a la VIS
# un ingreso que la banca no le exige, y con eso empujaba a los compradores de
# menor ingreso fuera de los proyectos que sí están hechos para ellos.
#
# Ahora el crédito se simula por SEGMENTO, con los parámetros de mercado 2026:
#
#   | Parámetro       |   VIS |  No VIS | de dónde sale
#   |-----------------|------:|--------:|------------------------------------
#   | Cuota inicial   |   10% |     30% | la banca financia hasta 90% VIS,
#   |                 |       |         | hasta 70-80% No VIS
#   | Plazo máximo    | 360 m |   240 m | tarifario BBVA vigente marzo 2026
#   | Tasa E.A.       | 12,5% |   13,5% | VIS 10,9-15,9% / No VIS 11,5-17%,
#   |                 |       |         | mercado ~13% promedio
#   | Cuota / ingreso |   40% |     30% | Decreto 257 de 2021: el límite
#   |                 |       |         | regulatorio de la primera cuota
#   |                 |       |         | subió a 40% para VIS
#
# El 40% de la VIS es el cambio con más efecto: es una norma pensada
# exactamente para que hogares de bajos ingresos que quedaban excluidos de la
# financiación puedan acceder, y el modelo no la estaba reflejando.
# ---------------------------------------------------------------------------
SMMLV = 2_000_000          # Salario mínimo vigente 2026 (COP). Actualizar cada año.
SUBSIDIO_SMMLV = 30        # Subsidio de vivienda aplicable a VIS con caja

# Índice: el mismo código de `tipo_vivienda` del contrato (0 = No VIS, 1 = VIS).
PARAMETROS_CREDITO = {
    1: {  # VIS
        "nombre": "VIS",
        "cuota_inicial": 0.10,
        "plazo_meses": 360,
        "tasa_ea": 0.125,
        "cuota_ingreso_max": 0.40,
    },
    0: {  # No VIS
        "nombre": "No VIS",
        "cuota_inicial": 0.30,
        "plazo_meses": 240,
        "tasa_ea": 0.135,
        "cuota_ingreso_max": 0.30,
    },
}


def parametros_credito(tipo_cod):
    """Los supuestos de crédito del segmento. Por defecto, los de No VIS.

    No VIS es el default deliberado: es el escenario más exigente de los dos,
    así que un proyecto sin tipo declarado no se abarata por accidente.
    """
    return PARAMETROS_CREDITO.get(1 if tipo_cod == 1 else 0)


def tasa_mensual(tasa_ea):
    """Tasa efectiva anual -> tasa efectiva mensual equivalente.

    Es la conversión correcta ((1+i)^(1/12) - 1), no la división entre 12: a
    13,5% E.A. la diferencia entre las dos son ~7 puntos básicos mensuales,
    que sobre 240 cuotas se convierten en millones.
    """
    return (1.0 + tasa_ea) ** (1.0 / 12.0) - 1.0

# Rangos de salario declarados en el formulario del usuario.
#   1: hasta 2 SMMLV | 2: de 2 a 4 | 3: de 4 a 8 | 4: más de 8
TOPES_SALARIO_SMMLV = [2, 4, 8]

# ---------------------------------------------------------------------------
# Perfiles de amenidades (por índice de ZONAS_COMUNES).
# Sirven como etiquetas cualitativas del proyecto y alimentan la estimación de
# la edad objetivo.
# ---------------------------------------------------------------------------
PERFILES_AMENIDADES = {
    "familiar": {5, 18, 17, 8, 3, 19, 4, 6},
    "joven_profesional": {12, 13, 10, 14, 11, 15, 7, 0},
    "bienestar": {1, 24, 9, 20, 22, 21, 7, 15},
    "practico": {16, 2, 23, 6, 0},
}


# ---------------------------------------------------------------------------
# Utilidades numéricas
# ---------------------------------------------------------------------------
def _percentil(valores_ordenados, fraccion):
    """Percentil por interpolación lineal (evita depender de numpy aquí)."""
    if not valores_ordenados:
        return 0.0
    if len(valores_ordenados) == 1:
        return float(valores_ordenados[0])
    posicion = fraccion * (len(valores_ordenados) - 1)
    inferior = int(posicion)
    superior = min(inferior + 1, len(valores_ordenados) - 1)
    peso = posicion - inferior
    return valores_ordenados[inferior] * (1 - peso) + valores_ordenados[superior] * peso


def _acotar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


# ---------------------------------------------------------------------------
# Etiquetado económico
# ---------------------------------------------------------------------------
def cuota_mensual(monto_financiado, tipo_cod=0, plazo_meses=None):
    """Cuota fija de un crédito de anualidad vencida, según el segmento.

    `tipo_cod` elige los supuestos (VIS o No VIS); `plazo_meses` permite pedir
    un plazo distinto al máximo del segmento, que es lo que necesita el
    simulador de esfuerzo de `cota_minima.py`.
    """
    monto_financiado = float(monto_financiado or 0)
    if monto_financiado <= 0:
        return 0.0
    parametros = parametros_credito(tipo_cod)
    plazo = int(plazo_meses or parametros["plazo_meses"])
    i = tasa_mensual(parametros["tasa_ea"])
    factor = (1 + i) ** -plazo
    return monto_financiado * i / (1 - factor)


def monto_financiado(precio, tipo_cod=0, aplica_subsidio=False):
    """Lo que efectivamente presta el banco: precio - cuota inicial - subsidio.

    El subsidio se descuenta ANTES de la cuota inicial porque es un aporte al
    precio, no al crédito: es plata que el hogar no tiene que financiar ni
    poner de su bolsillo.
    """
    precio_efectivo = float(precio or 0)
    if aplica_subsidio:
        precio_efectivo = max(0.0, precio_efectivo - SUBSIDIO_SMMLV * SMMLV)
    parametros = parametros_credito(tipo_cod)
    return precio_efectivo * (1 - parametros["cuota_inicial"])


def ingreso_requerido_smmlv(precio, aplica_subsidio=False, tipo_cod=0):
    """Ingreso familiar necesario, en SMMLV, para comprar el proyecto.

    Se descuenta el subsidio y la cuota inicial del segmento, se calcula la
    cuota del crédito a su plazo y tasa, y se exige que esa cuota no supere el
    tope regulatorio de cuota/ingreso de ese segmento (40% VIS, 30% No VIS).
    """
    parametros = parametros_credito(tipo_cod)
    financiado = monto_financiado(precio, tipo_cod, aplica_subsidio)
    ingreso = cuota_mensual(financiado, tipo_cod) / parametros["cuota_ingreso_max"]
    return ingreso / SMMLV


def rango_salario(ingreso_smmlv):
    """Traduce un ingreso en SMMLV al código 1..4 del formulario."""
    for codigo, tope in enumerate(TOPES_SALARIO_SMMLV, start=1):
        if ingreso_smmlv <= tope:
            return codigo
    return 4


# ---------------------------------------------------------------------------
# Etiquetado de habitaciones / capacidad
# ---------------------------------------------------------------------------
def codificar_habitaciones(habitaciones):
    """Devuelve (min, max, codigo 1..3) donde 3 significa '3 o más'.

    Acepta la lista de tipologías del seed manual y también el entero único
    del catálogo scrapeado, que ya viene codificado 1..3.
    """
    if isinstance(habitaciones, (int, float)) and not isinstance(habitaciones, bool):
        habitaciones = [habitaciones]
    valores = [int(h) for h in (habitaciones or []) if isinstance(h, (int, float))]
    if not valores:
        return None, None, 1
    return min(valores), max(valores), _acotar(max(valores), 1, 3)


def personas_objetivo(codigo_habitaciones, area_m2):
    """Tamaño de hogar al que apunta el inmueble (1..4, donde 4 es '4 o más').

    Parte del número de habitaciones y ajusta por área: un 2 habitaciones de
    60 m² alberga cómodamente a un hogar más grande que uno de 40 m².
    """
    base = {1: 1, 2: 2, 3: 4}.get(codigo_habitaciones, 2)
    area = float(area_m2 or 0)
    if area >= 55 and base < 4:
        base += 1
    elif 0 < area < 32 and base > 1:
        base -= 1
    return _acotar(base, 1, 4)


# ---------------------------------------------------------------------------
# Etiquetado de perfil de amenidades y edad
# ---------------------------------------------------------------------------
def perfil_amenidades(indices_zonas):
    """Cobertura [0..1] de cada perfil cualitativo según las zonas comunes."""
    presentes = set(indices_zonas)
    return {
        nombre: round(len(presentes & conjunto) / len(conjunto), 4)
        for nombre, conjunto in PERFILES_AMENIDADES.items()
    }


def edad_objetivo(personas, perfiles, salario_obj, codigo_habitaciones, area_m2):
    """Edad estimada del comprador tipo.

    Heurística explícita y auditable (no hay histórico todavía para aprenderla):
      - la etapa familiar es el factor dominante: más habitaciones y más
        personas a cargo desplazan la edad hacia arriba;
      - amenidades de perfil joven (coworking, sala VIP, zona cool) la bajan;
      - amenidades de bienestar (sauna, spa, pista de trote) la suben;
      - mayor poder adquisitivo correlaciona con mayor edad.
    """
    edad = 30.0
    edad += 4.0 * (personas - 1)
    edad -= 6.0 * perfiles["joven_profesional"]
    edad += 5.0 * perfiles["bienestar"]
    edad += 1.5 * (salario_obj - 2)
    if codigo_habitaciones == 1 and float(area_m2 or 0) < 35:
        edad -= 2.0          # aparta-estudio: típicamente primer comprador
    return int(round(_acotar(edad, 25, 55)))


# ---------------------------------------------------------------------------
# Transformación de un proyecto
# ---------------------------------------------------------------------------
# El seed original y el catálogo que produce `scraper_projects.py` nombran los
# mismos datos distinto: el seed viene del volcado manual y el catálogo sigue
# el contrato del formulario. En vez de duplicar campos en el JSON, prep lee
# cualquiera de los dos nombres.
_ALIAS_CAMPOS = {
    "localidad": ("localidad", "Localidad"),
    "amenidades_entorno": ("amenidades_entorno", "zonas_comunes"),
    "area_construida_m2": ("area_construida_m2", "area_desde_m2"),
    "habitaciones_ofrecidas": ("habitaciones_ofrecidas", "numero_habitaciones"),
    "url_ficha": ("url_ficha", "link_proyecto"),
}


def _campo(crudo, nombre):
    """Valor del campo `nombre`, aceptando los alias del catálogo scrapeado."""
    for llave in _ALIAS_CAMPOS.get(nombre, (nombre,)):
        valor = crudo.get(llave)
        if valor not in (None, "", []):
            return valor
    return None


def preparar_proyecto(crudo, avisos):
    """Convierte un registro crudo del seed en un registro etiquetado."""
    id_proyecto = crudo.get("id_proyecto")

    tipo_cod = codigo_tipo_vivienda(crudo.get("tipo_vivienda"))
    if tipo_cod is None:
        avisos["tipo_vivienda_desconocido"].append(
            f"{id_proyecto}: {crudo.get('tipo_vivienda')!r}"
        )

    localidad_id = indice_localidad(_campo(crudo, "localidad"))
    if localidad_id is None:
        avisos["localidad_desconocida"].append(
            f"{id_proyecto}: {_campo(crudo, 'localidad')!r}"
        )

    zonas_idx, zonas_desconocidas = mapear_zonas(_campo(crudo, "amenidades_entorno"))
    for zona in zonas_desconocidas:
        avisos["amenidad_desconocida"].append(f"{id_proyecto}: {zona!r}")

    hab_min, hab_max, hab_cod = codificar_habitaciones(_campo(crudo, "habitaciones_ofrecidas"))
    area = float(_campo(crudo, "area_construida_m2") or 0)
    precio = float(crudo.get("precio_desde_cop") or 0)
    aplica_subsidio = bool(crudo.get("aplica_subsidio_caja"))

    # El crédito se simula con los supuestos del SEGMENTO del proyecto: una
    # VIS y una No VIS no se financian igual, y tratarlas igual era lo que le
    # exigía a la VIS un ingreso que la banca no le exige.
    ingreso_smmlv = ingreso_requerido_smmlv(precio, aplica_subsidio=False,
                                            tipo_cod=tipo_cod)
    ingreso_smmlv_sub = ingreso_requerido_smmlv(
        precio, aplica_subsidio=aplica_subsidio and tipo_cod == 1, tipo_cod=tipo_cod
    )
    salario_obj = rango_salario(ingreso_smmlv)
    salario_obj_sub = rango_salario(ingreso_smmlv_sub)

    personas_obj = personas_objetivo(hab_cod, area)
    perfiles = perfil_amenidades(zonas_idx)
    edad_obj = edad_objetivo(personas_obj, perfiles, salario_obj, hab_cod, area)
    perfil_dominante = max(perfiles, key=perfiles.get) if any(perfiles.values()) else None

    return {
        # --- identificación y datos de presentación ---
        "id_proyecto": id_proyecto,
        "nombre_proyecto": crudo.get("nombre_proyecto"),
        "direccion": crudo.get("direccion"),
        "url_ficha": _campo(crudo, "url_ficha"),
        # Los proyectos que publican dos constructoras traen la segunda ficha.
        # Viaja hasta la respuesta del front, porque el precio difiere entre
        # las dos y el usuario debe poder ver ambas.
        "constructoras": crudo.get("constructoras") or [],
        "links_alternos": crudo.get("links_alternos") or [],
        "precio_desde_cop": precio,
        "area_construida_m2": area,
        "aplica_subsidio_caja": aplica_subsidio,
        "direccion_es_aproximada": bool(crudo.get("_direccion_es_aproximada")),

        # --- claves del filtro duro ---
        "tipo_vivienda": nombre_tipo_vivienda(tipo_cod),
        "tipo_vivienda_cod": tipo_cod,
        "localidad": nombre_localidad(localidad_id) or crudo.get("localidad"),
        "localidad_id": localidad_id,
        # El barrio (sector catastral) lo resuelve el scraper y aquí solo se
        # conserva: es el nodo del proyecto en el grafo fino (grafo_barrios).
        # Null cuando ni la dirección ni la coordenada lo ubican; el modelo
        # entonces usa solo la localidad, como hasta la v0.3.
        "barrio_id": crudo.get("barrio_id"),
        "barrio_nombre": crudo.get("barrio_nombre"),
        "barrio_confianza": crudo.get("_barrio_confianza"),
        "zonas_comunes": nombres_zonas(zonas_idx),
        "zonas_comunes_idx": zonas_idx,
        "zonas_comunes_vector": vector_zonas(zonas_idx),
        "n_zonas_comunes": len(zonas_idx),

        # --- etiquetas derivadas ---
        "habitaciones_min": hab_min,
        "habitaciones_max": hab_max,
        "habitaciones_cod": hab_cod,
        "precio_por_m2": round(precio / area, 2) if area else None,
        "ingreso_requerido_smmlv": round(ingreso_smmlv, 2),
        "ingreso_requerido_cop": round(ingreso_smmlv * SMMLV),
        "cuota_mensual_estimada_cop": round(
            cuota_mensual(monto_financiado(precio, tipo_cod), tipo_cod)
        ),
        # Los supuestos con los que se calculó, para que el número sea
        # auditable sin tener que reconstruirlo: es lo que Manuela le dice al
        # comprador por teléfono.
        "credito": {
            "cuota_inicial_pct": parametros_credito(tipo_cod)["cuota_inicial"],
            "plazo_meses": parametros_credito(tipo_cod)["plazo_meses"],
            "tasa_ea": parametros_credito(tipo_cod)["tasa_ea"],
            "cuota_ingreso_max": parametros_credito(tipo_cod)["cuota_ingreso_max"],
            "monto_financiado_cop": round(monto_financiado(precio, tipo_cod)),
        },
        "ingreso_requerido_smmlv_con_subsidio": round(ingreso_smmlv_sub, 2),
        "salario_objetivo_con_subsidio": salario_obj_sub,
        "perfil_amenidades": perfiles,
        "perfil_dominante": perfil_dominante,

        # --- espacio de features del modelo ---
        "salario_objetivo": salario_obj,
        "personas_objetivo": personas_obj,
        "edad_objetivo": edad_obj,
        "perfil_vector": [salario_obj, personas_obj, edad_obj],
    }


def etiquetar_segmento_precio(proyectos):
    """Añade `segmento_precio` usando terciles del precio por m² del dataset."""
    valores = sorted(p["precio_por_m2"] for p in proyectos if p["precio_por_m2"])
    corte_bajo = _percentil(valores, 1 / 3)
    corte_alto = _percentil(valores, 2 / 3)
    for proyecto in proyectos:
        valor = proyecto["precio_por_m2"]
        if not valor:
            proyecto["segmento_precio"] = None
        elif valor <= corte_bajo:
            proyecto["segmento_precio"] = "economico"
        elif valor <= corte_alto:
            proyecto["segmento_precio"] = "medio"
        else:
            proyecto["segmento_precio"] = "alto"
    return {"tercil_bajo": round(corte_bajo, 2), "tercil_alto": round(corte_alto, 2)}


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------
def preparar(ruta_seed=RUTA_SEED, ruta_salida=RUTA_MODELO, verbose=True):
    """Lee el seed, etiqueta todos los proyectos y escribe `proyectos_model.json`."""
    with open(ruta_seed, "r", encoding="utf-8") as archivo:
        crudos = json.load(archivo)
    if isinstance(crudos, dict):
        crudos = crudos.get("proyectos", [])

    avisos = {
        "tipo_vivienda_desconocido": [],
        "localidad_desconocida": [],
        "amenidad_desconocida": [],
    }
    proyectos = [preparar_proyecto(crudo, avisos) for crudo in crudos]
    cortes_precio = etiquetar_segmento_precio(proyectos)

    salida = {
        "meta": {
            "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fuente": os.path.basename(ruta_seed),
            "n_proyectos": len(proyectos),
            "smmlv": SMMLV,
            # Los supuestos quedan en el JSON por segmento: son la explicación
            # de por qué un proyecto pide el ingreso que pide, y cambian cada
            # vez que se mueve el mercado.
            "supuestos_credito": {
                parametros["nombre"]: {k: v for k, v in parametros.items() if k != "nombre"}
                for parametros in PARAMETROS_CREDITO.values()
            },
            "subsidio_smmlv": SUBSIDIO_SMMLV,
            "cortes_precio_m2": cortes_precio,
            "features_modelo": ["salario_objetivo", "personas_objetivo", "edad_objetivo"],
            "localidades_bogota": LOCALIDADES_BOGOTA,
            "zonas_comunes": ZONAS_COMUNES,
            "avisos": {k: v for k, v in avisos.items() if v},
        },
        "proyectos": proyectos,
    }

    with open(ruta_salida, "w", encoding="utf-8") as archivo:
        json.dump(salida, archivo, ensure_ascii=False, indent=2)

    if verbose:
        _reporte(salida, ruta_salida)
    return salida


def _reporte(salida, ruta_salida):
    proyectos = salida["proyectos"]
    print(f"[prep] {len(proyectos)} proyectos -> {os.path.basename(ruta_salida)}")
    print(f"[prep] tipo_vivienda   : {dict(Counter(p['tipo_vivienda'] for p in proyectos))}")
    print(f"[prep] localidades     : {len({p['localidad_id'] for p in proyectos})} de 20 con oferta")
    con_barrio = sum(1 for p in proyectos if p["barrio_id"])
    print(f"[prep] barrio resuelto : {con_barrio} de {len(proyectos)} "
          f"({len({p['barrio_id'] for p in proyectos if p['barrio_id']})} barrios distintos)")
    print(f"[prep] salario_objetivo: {dict(sorted(Counter(p['salario_objetivo'] for p in proyectos).items()))}")
    print(f"[prep] personas_objetivo: {dict(sorted(Counter(p['personas_objetivo'] for p in proyectos).items()))}")
    edades = [p["edad_objetivo"] for p in proyectos]
    print(f"[prep] edad_objetivo   : min={min(edades)} max={max(edades)} media={sum(edades)/len(edades):.1f}")
    print(f"[prep] perfil_dominante: {dict(Counter(p['perfil_dominante'] for p in proyectos))}")
    for clave, mensajes in salida["meta"]["avisos"].items():
        print(f"[prep] AVISO {clave}: {mensajes}")


def main():
    parser = argparse.ArgumentParser(description="Prepara y etiqueta los proyectos para el modelo.")
    parser.add_argument("--seed", default=RUTA_SEED, help="Ruta del JSON crudo de entrada.")
    parser.add_argument("--salida", default=RUTA_MODELO, help="Ruta del JSON etiquetado de salida.")
    args = parser.parse_args()
    preparar(args.seed, args.salida)


if __name__ == "__main__":
    main()
