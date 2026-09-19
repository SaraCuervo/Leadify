"""
modelo.py
=========
Motor de recomendación de proyectos inmobiliarios.

Pipeline:

    leer_info_user(path)  ->  usuario_modelo / usuario_segmentado / contacto
              |
    primer_filtro(usuario_segmentado)  ->  proyectos_preseleccionados
              |                            (filtro duro + expansión por grafo)
    modelo(preseleccionados, usuario_modelo)  ->  proyectos_seleccionados
              |                                   (Nearest Neighbors, top N)
    post_arreglos(seleccionados)  ->  proyectos_listos_llamativos
                                      (normalización comercial del score)

Requiere `proyectos_model.json`, generado por `prep.py`.
"""

from __future__ import annotations

import json
import os

import numpy as np
from sklearn.neighbors import NearestNeighbors

from Model.catalogos import (
    LOCALIDADES_BOGOTA,
    ZONAS_COMUNES,
    codigo_tipo_vivienda,
    indice_localidad,
    localidades_por_distancia,
    mapear_zonas,
    nombre_localidad,
    nombre_tipo_vivienda,
    nombres_zonas,
)

# El grafo de barrios afina la cercanía DENTRO de la localidad. La admisión
# (el BFS de `primer_filtro`) sigue siendo por localidades: el barrio solo
# cambia cuánto pesa la distancia en el score y el orden de los candidatos.
from Model.grafo_barrios import (
    distancia_barrios,
    indice_barrio,
    localidad_de_barrio,
    nombre_barrio,
)

# `cota_minima` aporta el cálculo del esfuerzo de pago. La dependencia va en
# un solo sentido: ese módulo no importa este.
from Model.cota_minima import evaluar_esfuerzo

# Las rutas salen de `Model/rutas.py`, que es el único sitio que sabe dónde
# vive cada archivo del backend.
from Model.rutas import RUTA_HISTORIAL, RUTA_LLAMATIVOS, RUTA_MODELO, asegurar_salidas

# ---------------------------------------------------------------------------
# Parámetros del filtro duro
# ---------------------------------------------------------------------------
# Candidatos mínimos que el filtro duro le entrega al modelo. Tiene que ser
# holgadamente mayor que `TOP_N`: si fueran iguales, el Nearest Neighbors no
# elegiría nada —devolvería el filtro entero— y el score dejaría de ordenar.
# Se mantiene la proporción de siempre (~1,7x el tamaño del top).
MINIMO_PRESELECCIONADOS = 30

# Escalera de relajación: cada paso suelta una restricción, de la menos a la
# más costosa para el usuario. El tipo de vivienda nunca entra aquí (VIS y
# No VIS son categorías legales distintas) y las habitaciones se sueltan de
# últimas, porque son el requisito más duro de la búsqueda.
#   (exige_zonas, exige_habitaciones, nivel_de_relajacion)
PASOS_RELAJACION = (
    (True,  True,  0),   # criterio completo
    (False, True,  2),   # se admite que no coincida ninguna zona común
    (False, False, 3),   # último recurso: menos habitaciones de las pedidas
)

# ---------------------------------------------------------------------------
# Parámetros del modelo
# ---------------------------------------------------------------------------
# Cuántas recomendaciones se devuelven. Sube junto con
# `MINIMO_PRESELECCIONADOS`, que tiene que seguir siendo mayor.
TOP_N = 18

# Vecinos consultados en el histórico. `None` = automático.
#
# Lo que hay que consultar no son REGISTROS sino PERFILES DISTINTOS: el
# histórico repite a la misma persona en cada evento que vive, y el vector del
# modelo son solo tres features (salario, personas, edad), así que muchos
# clientes distintos colapsan además en el mismo punto. En el historial actual
# hay 8.710 registros sobre 453 perfiles distintos: 19 registros por perfil.
# Un K fijo de 200 consultaba ~10 perfiles y se quedaba corto.
#
# Por eso K se calcula como PERFILES_A_CONSULTAR x (registros por perfil), que
# se mide del propio historial y se reajusta solo si cambia la simulación.
# Medido sobre 600 clientes de prueba no vistos (simulacion/evaluar.py):
#
#     K=200 -> 68.8%   K=450 -> 75.5%   K=600 -> 77.3%   K=900 -> 76.5%
#
# El óptimo es un plateau ancho entre 520 y 820; 30 perfiles cae en el centro.
# Por debajo el vecindario es demasiado pequeño para promediar, y por encima
# la personalización se diluye hasta degenerar en popularidad global.
K_VECINOS = None
K_VECINOS_MIN, K_VECINOS_MAX = 15, 1500
PERFILES_A_CONSULTAR = 30

# Rangos fijos para escalar cada feature a [0, 1]. Se usan rangos de dominio en
# lugar de ajustar un scaler sobre los candidatos: con 10 candidatos un scaler
# empírico sería inestable y cambiaría de escala en cada consulta.
RANGOS_FEATURES = {
    "salario": (1, 4),
    "personas_a_cargo": (1, 4),
    "edad": (18, 75),
}

# Importancia relativa de cada feature dentro de la distancia.
# La capacidad de pago manda en una compra de vivienda.
PESOS_FEATURES = {
    "salario": 0.50,
    "personas_a_cargo": 0.30,
    "edad": 0.20,
}

# Distancia euclidiana máxima posible en el espacio escalado y ponderado.
DISTANCIA_MAXIMA = float(np.sqrt(sum(p ** 2 for p in PESOS_FEATURES.values())))

# Mezcla del score final.
#
# Hasta la v0.2 era {modelo: 0.70, zonas: 0.20, localidad: 0.10}: el parecido
# demográfico decidía y lo demás desempataba. El problema es que el parecido
# demográfico es un PROXY del dinero —el salario objetivo del proyecto contra
# el tramo del usuario—, y un proxy grueso: dos proyectos etiquetados en el
# mismo tramo de salario pueden diferir en 80 millones, y el modelo los veía
# iguales.
#
# `esfuerzo` mide lo que el proxy no: cuántos años tardaría ESTA persona en
# pagar ESE proyecto (`cota_minima.anos_de_pago`). Entra con el peso más alto
# después del modelo, y como el salario ya pesa 0.50 dentro de las features
# del modelo, la plata termina explicando cerca de la mitad del score. Ese es
# el reenfoque: el dinero pasa de desempatar a decidir.
#
# `localidad` baja de 0.10 a 0.08 porque es la concesión que la cota de precio
# está autorizada a comprar (ver `Cota_minimaBG`); `zonas` baja de 0.20 a 0.17
# porque las amenidades son preferencia, no viabilidad.
#
# El peso de `esfuerzo` está calibrado, no elegido. Medido sobre 400 clientes
# de prueba no vistos, con la cota de precio ya activa:
#
#   esfuerzo | modelo | recall@18 | precio Top 3 | ahorro | ahorro por punto
#            |        |           |              |        | de recall cedido
#   ---------|--------|-----------|--------------|--------|------------------
#     0.00   |  0.75  |   75,0%   | 292.369.897  |   0 %  |        —
#     0.15   |  0.60  |   73,2%   | 283.807.688  | 2,9 %  |     1,6 %
#     0.20   |  0.55  |   72,5%   | 281.766.874  | 3,6 %  |     1,0 %
#     0.25   |  0.50  |   72,0%   | 280.688.197  | 4,0 %  |     0,9 %  <- elegido
#     0.35   |  0.40  |   70,5%   | 278.605.293  | 4,7 %  |     0,5 %
#
# 0.25 se queda con el 85% del ahorro que este componente puede aportar; de ahí
# en adelante cada punto de recall cedido compra la mitad de ahorro que al
# principio. El grueso del efecto económico no lo hace este peso sino la cota
# (-15,6% de precio), y por eso subirlo más solo cuesta.
#
# Con esto la plata explica cerca de la mitad del score sin la cota:
# `esfuerzo` 0.25 + `salario`, que pesa 0.50 dentro de las features del modelo
# (0.50 x 0.50 = 0.25 efectivo). Con la cota encima, decide el orden entero.
PESOS_SCORE = {"modelo": 0.50, "esfuerzo": 0.25, "zonas": 0.17, "localidad": 0.08}

# --- Cercanía: del salto de localidad al kilómetro ---------------------------
# Hasta la v0.3 `score_localidad = max(0, 1 - 0.25 * saltos_de_localidad)`:
# misma localidad 1.0, vecina 0.75, a dos saltos 0.5, a cuatro 0. Con eso un
# usuario que pide Suba ve a distancia 0 tanto La Colina como Lisboa, que
# están a 8 km, y el score no puede distinguir el que le queda al lado del
# que le queda cruzando la localidad entera.
#
# Con el grafo de barrios (Model/grafo_barrios.py) la distancia se mide en
# kilómetros por el grafo de vecindad y el score decae linealmente hasta 0 en
# `RADIO_CERCANIA_KM`. Para situar el número: sobre 20.000 pares de sectores
# urbanos al azar, la mediana de distancia por salto de localidad es 3,1 km
# (misma), 6,8 (vecina), 10,3 (dos saltos), 14,3 (tres) y 19,3 (cuatro). Con
# 12 km la localidad vecina puntúa ~0,43 y a dos saltos ya casi nada; DENTRO
# de Suba los 27 proyectos con barrio se reparten entre 1,3 y 13,5 km, es
# decir entre 0,89 y 0, que es la separación que antes no existía.
#
# Radio y peso están calibrados juntos (simulacion/calibrar_barrios.py):
# 300 clientes de prueba no vistos, cada uno con un barrio sorteado de su
# localidad, midiendo a cuántos km del barrio queda lo recomendado.
#
#      config          recall@18  pos.media  km top3  km top18  precio top3
#      sin barrio (v0.3)  71,2%      7,95      9,51    10,51    299.273.417
#      r=20 w=0,08        73,6%      7,30      9,34    10,23    -0,4%
#      r=12 w=0,08        74,2%      7,41      9,28    10,28    -0,3%
#      r=12 w=0,12        73,2%      7,29      8,96     9,97    -0,5%   <- elegido
#      r=12 w=0,16        72,2%      7,22      8,53     9,70    -0,6%
#      r=8  w=0,16        70,9%      7,08      8,91    10,05    -0,4%
#
# El barrio no le cuesta nada al reenfoque económico: el precio del Top 3 no
# sube en ninguna fila y el recall sube en todas menos la última. Lo único que
# se intercambia es peso del modelo demográfico por cercanía, y 12 km / 0,12
# es el punto donde el Top 3 se acerca un 6% sin perder recall frente a la
# base. Subir a 0,16 acerca un 10% pero empieza a costar recall.
RADIO_CERCANIA_KM = 12.0

# Lo que puntúa un proyecto que está JUSTO en el borde del radio, y con ello
# el tamaño de la cola que hay más allá.
#
# EL PROBLEMA QUE RESUELVE. El decaimiento era `max(0, 1 - km/12)`, que se
# queda pegado en 0 a partir de los 12 km. Medido sobre el propio grafo, el
# 52% de los pares de sectores urbanos supera esa distancia (la mediana de
# todos los pares es 12,43 km), así que más de la mitad del mapa puntuaba
# exactamente igual: cero.
#
# Dentro de una misma localidad eso da igual —el p90 es 8,1 km y casi nada
# satura—, pero se vuelve grave justo en el caso para el que existe la
# expansión por el grafo: el usuario de una localidad SIN oferta. Suba
# concentra 31 de los 96 proyectos, y desde las cuatro localidades sin oferta
# queda fuera del radio en todas:
#
#      Antonio Nariño -> Suba 12,7 km      Rafael Uribe   -> Suba 13,2 km
#      Tunjuelito     -> Suba 15,7 km      Ciudad Bolívar -> Suba 21,8 km
#
# Con el corte en 12, esos 31 proyectos empataban a 0 y la cercanía dejaba de
# ordenar precisamente donde más falta hace. Con la cola, 13,2 km puntúa
# 0,073 y 21,8 km puntúa 0,044: sigue habiendo un orden.
#
# POR QUÉ 0,08 Y NO UNA CURVA CUALQUIERA. La tabla de calibración de arriba
# (r=12, w=0,12) se midió con la recta, y el rango 0-12 km es donde cae la
# enorme mayoría de los candidatos reales. Así que la recta se conserva ahí y
# solo se comprime un 8% para dejarle sitio a la cola: a 6 km se pasa de 0,50
# a 0,54, una diferencia que el peso de 0,12 vuelve despreciable. Una curva
# como `1/(1+km/6)` habría arreglado la saturación igual, pero aplastando el
# tramo cercano (0,67 a 3 km en vez de 0,81) y dejando la calibración sin
# valor. El objetivo era quitar el suelo, no volver a calibrar.
FRACCION_BORDE_CERCANIA = 0.08

# Peso de `localidad` cuando el usuario SÍ dio barrio. Sin barrio la cercanía
# es un dato grueso (¿misma localidad o vecina?) y pesa lo de siempre, 0,08,
# para que un formulario sin barrio dé exactamente lo de la v0.3 y las tablas
# de calibración de §4.3-4.5 sigan valiendo. Con barrio es una medida en km, y
# un dato más fino merece más peso. Lo que sube aquí se le quita a `modelo`.
PESO_LOCALIDAD_CON_BARRIO = 0.12

# Cuando el usuario sí dio barrio pero el proyecto no tiene (13 de 96 no se
# pudieron ubicar), no se le regala el 1.0 de "misma localidad": se le asume
# la distancia TÍPICA para su salto de localidad, que es lo que se mide de
# arriba (3,1 km + 3,7 km por salto). Es el mismo criterio que
# `COBERTURA_ZONAS_SIN_DATO`: lo que no se sabe vale lo esperado, no lo mejor.
KM_BASE_SIN_BARRIO = 3.1
KM_POR_SALTO_LOCALIDAD = 3.7

# --- Datos que la fuente no publica ---------------------------------------
# No todas las constructoras publican habitaciones ni zonas comunes. Un dato
# ausente NO es un incumplimiento: tratarlo como tal dejaba 7 de los 102
# proyectos del catálogo fuera de cualquier recomendación posible. Se admiten
# y se les descuenta, para que no le ganen a una ficha completa que sí
# demostró cumplir.
COBERTURA_ZONAS_SIN_DATO = 0.35   # "no sé", deliberadamente por debajo de un match parcial
PENALIZACION_DATO_INCOMPLETO = 0.05   # por cada campo que falta

# Peso del componente colaborativo cuando existe histórico. El resto lo aporta
# el componente de contenido, que cubre los proyectos sin interacciones (frío).
# Medido sobre 600 clientes no vistos: 0.4 y 0.5 empatan en 77.7% y de ahí
# hacia arriba baja de forma sostenida (0.6 -> 77.3%, 0.9 -> 75.7%). El
# colaborativo aporta, pero no debe tapar al de contenido: es el que sostiene
# a los proyectos con pocas interacciones.
ALPHA_HISTORIAL = 0.50

# ---------------------------------------------------------------------------
# Parámetros del gancho comercial (post_arreglos)
# ---------------------------------------------------------------------------
# El líder muestra su propio score como porcentaje. Si ese score sale por
# debajo de este mínimo se eleva hasta él: quien abre la lista es lo mejor que
# hay para esa persona y no puede presentarse con un 60%.
PORCENTAJE_TOP_MINIMO = 85.0
# Del segundo hacia abajo no hay mínimo: cada uno resta su diferencia real con
# el de arriba, en caída libre. Un encaje malo tiene que poder verse malo.
PASO_MINIMO = 1         # garantiza que no haya dos porcentajes iguales

# Traducción del campo `piso` del formulario.
PISOS = {0: "bajo", 1: "medio", 3: "alto", 4: "sin preferencia"}
PISO_SIN_PREFERENCIA = 4


# ===========================================================================
# A. Lectura y estructuración de la información del usuario
# ===========================================================================
def leer_info_user(path_user_info):
    """Lee el formulario del usuario y lo parte en las tres estructuras del pipeline.

    Args:
        path_user_info: acepta tres formas, para que el front no tenga que
            escribir un archivo temporal solo para invocar al modelo:
              - dict ya deserializado (el payload que manda la API)
              - string con el JSON serializado
              - ruta a un archivo .json

    Returns:
        (usuario_modelo, usuario_segmentado, usuario_info_contacto_v1)

        usuario_modelo            -> features numéricas que consume el modelo.
        usuario_segmentado        -> llaves del filtro duro.
        usuario_info_contacto_v1  -> datos de contacto y preferencias restantes.
    """
    crudo = _cargar_formulario(path_user_info)
    if isinstance(crudo, list):          # tolera un archivo con un solo registro
        crudo = crudo[0]

    # Catálogos de referencia usados para traducir los códigos del formulario.
    # Se toman de `catalogos.py` para que prep y modelo compartan exactamente
    # los mismos índices.
    localidades_bogota = list(LOCALIDADES_BOGOTA)   # 20 localidades, índice 0..19
    zonas_comunes = list(ZONAS_COMUNES)             # 25 zonas, índice 0..24

    errores = []

    # --- campos del modelo -------------------------------------------------
    salario = _entero(crudo.get("salario"))
    if salario not in (1, 2, 3, 4):
        errores.append(f"salario debe estar entre 1 y 4 (recibido: {crudo.get('salario')!r})")

    personas = _entero(crudo.get("personas_a_cargo"))
    if personas not in (1, 2, 3, 4):
        errores.append(
            f"personas_a_cargo debe estar entre 1 y 4 (recibido: {crudo.get('personas_a_cargo')!r})"
        )

    edad = _entero(crudo.get("edad"))
    if edad is None or not (18 <= edad <= 125):
        errores.append(f"edad debe estar entre 18 y 125 (recibido: {crudo.get('edad')!r})")

    # --- campos de segmentación -------------------------------------------
    tipo_cod = codigo_tipo_vivienda(crudo.get("tipo_vivienda"))
    if tipo_cod is None:
        errores.append(
            f"tipo_vivienda debe ser 0 (No VIS) o 1 (VIS) (recibido: {crudo.get('tipo_vivienda')!r})"
        )

    # El formulario admite la llave con o sin mayúscula inicial.
    localidad_cruda = crudo.get("Localidad", crudo.get("localidad"))
    localidad_id = indice_localidad(localidad_cruda)

    # `barrio` es opcional (nombre o código de sector catastral). Si viene y
    # se reconoce, afina la distancia en el score; si viene sin Localidad, la
    # localidad se deduce de él; si contradice a la Localidad declarada, es un
    # error del formulario y se reporta junto con los demás.
    barrio_crudo = crudo.get("barrio", crudo.get("Barrio"))
    barrio_id = None
    if barrio_crudo not in (None, ""):
        barrio_id = indice_barrio(barrio_crudo, localidad_id)
        if barrio_id is not None and localidad_id is None:
            localidad_id = localidad_de_barrio(barrio_id)   # el barrio dice dónde
        elif barrio_id is None:
            # No está en la localidad declarada: ¿existe, sin ambigüedad, en
            # otra? Si la Localidad no vino, se toma de ahí; si sí vino, el
            # formulario se contradice y hay que decirlo.
            en_otra = indice_barrio(barrio_crudo)
            if en_otra is not None and localidad_id is None:
                barrio_id = en_otra
                localidad_id = localidad_de_barrio(barrio_id)
            elif en_otra is not None:
                errores.append(
                    f"barrio {barrio_crudo!r} ({nombre_barrio(en_otra)}) queda en "
                    f"{nombre_localidad(localidad_de_barrio(en_otra))}, no en "
                    f"{nombre_localidad(localidad_id)} (Localidad={localidad_cruda!r})"
                )

    if localidad_id is None:
        errores.append(
            f"Localidad debe estar entre 1 y {len(localidades_bogota)} (recibido: {localidad_cruda!r})"
        )

    # Requisito duro de la búsqueda: se resuelve en el filtro, no en el modelo.
    habitaciones = _entero(crudo.get("numero_habitaciones"))
    if habitaciones not in (1, 2, 3):
        errores.append(
            "numero_habitaciones debe estar entre 1 y 3, donde 3 es '3 o más' "
            f"(recibido: {crudo.get('numero_habitaciones')!r})"
        )

    # La selección puede llegar como lista de strings o como un único string
    # con los nombres separados por comas; en ambos casos se traduce a índices.
    zonas_idx, zonas_desconocidas = mapear_zonas(crudo.get("zonas_comunes"))

    if errores:
        raise ValueError("JSON de usuario inválido:\n  - " + "\n  - ".join(errores))

    usuario_modelo = {
        "salario": salario,
        "personas_a_cargo": personas,
        "edad": edad,
    }

    usuario_segmentado = {
        "tipo_vivienda": tipo_cod,
        "localidad": localidad_id,
        "zonas_comunes": zonas_idx,
        "numero_habitaciones": habitaciones,
        # El barrio NO es llave del filtro duro: no admite ni excluye a nadie.
        # Solo afina la distancia (`_distancia_km`) con la que el score mide
        # la cercanía. None = el usuario no lo dio o no se reconoció.
        "barrio": barrio_id,
        # Extras legibles, útiles para logging y para la vista; el filtro solo
        # usa las cuatro llaves de arriba.
        "tipo_vivienda_nombre": nombre_tipo_vivienda(tipo_cod),
        "localidad_nombre": localidades_bogota[localidad_id - 1],
        "barrio_nombre": nombre_barrio(barrio_id),
        "zonas_comunes_nombres": [zonas_comunes[i] for i in zonas_idx],
    }

    # El piso se captura pero hoy no filtra nada: el seed de proyectos no trae
    # esa columna. Ante ausencia o valor inválido se asume "sin preferencia".
    piso = _entero(crudo.get("piso"))
    if piso not in PISOS:
        piso = PISO_SIN_PREFERENCIA
    usuario_info_contacto_v1 = {
        "nombres": crudo.get("nombres"),
        "apellidos": crudo.get("apellidos"),
        "nombre_completo": " ".join(
            parte for parte in (crudo.get("nombres"), crudo.get("apellidos")) if parte
        ).strip() or None,
        "correo": crudo.get("correo"),
        "telefono": crudo.get("telefono"),
        "afiliado": bool(crudo.get("afiliado")),
        "piso": piso,
        "piso_nombre": PISOS.get(piso),
        "zonas_comunes_no_reconocidas": zonas_desconocidas,
        # Un barrio que no está en el grafo no rompe nada: se anota y el
        # score usa la localidad, igual que si no lo hubieran dado.
        "barrio_no_reconocido": (str(barrio_crudo) if barrio_crudo not in (None, "")
                                 and barrio_id is None else None),
    }

    return usuario_modelo, usuario_segmentado, usuario_info_contacto_v1


def _cargar_formulario(entrada):
    """Normaliza la entrada del formulario a un dict.

    El front manda un payload JSON por HTTP; la CLI manda una ruta. Aceptar
    las dos evita que la capa HTTP tenga que escribir un archivo temporal
    solo para poder llamar al modelo.
    """
    if isinstance(entrada, (dict, list)):
        return entrada
    if isinstance(entrada, (bytes, bytearray)):
        entrada = entrada.decode("utf-8")
    if isinstance(entrada, str):
        texto = entrada.strip()
        if texto.startswith("{") or texto.startswith("["):
            return json.loads(texto)
        with open(entrada, "r", encoding="utf-8") as archivo:
            return json.load(archivo)
    raise TypeError(
        f"El formulario debe ser un dict, un JSON o una ruta; llegó {type(entrada).__name__}"
    )


def _entero(valor):
    """Convierte a int lo que venga del formulario. None si no es convertible."""
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    if isinstance(valor, str) and valor.strip().lstrip("+-").isdigit():
        return int(valor.strip())
    return None


# ===========================================================================
# B. Primer filtro (duro) con expansión sobre el grafo urbano
# ===========================================================================
def primer_filtro(usuario_segmentado, ruta_modelo=RUTA_MODELO,
                  minimo=MINIMO_PRESELECCIONADOS):
    """Filtra `proyectos_model.json` por tipo de vivienda, habitaciones,
    localidad y zonas comunes.

    Criterio base (coincidencia exacta):
        - mismo `tipo_vivienda`
        - al menos las `numero_habitaciones` solicitadas
        - misma `localidad`
        - al menos 1 coincidencia en las zonas comunes solicitadas

    Si el resultado trae menos de `minimo` proyectos, se expande en dos ejes.
    Primero el geográfico: se recorre el grafo urbano por saltos de distancia
    mínima (BFS), completando cada nivel entero antes de decidir si hace falta
    seguir. Si ni recorriendo todo el grafo alcanza, entra la escalera de
    `PASOS_RELAJACION`: se sueltan las zonas comunes y, solo como último
    recurso, las habitaciones. El tipo de vivienda nunca se relaja: VIS y
    No VIS son categorías legales y financieras distintas, no una preferencia.

    El barrio del usuario (`usuario_segmentado["barrio"]`, opcional) NO
    filtra: anota en cada candidato `_distancia_km` por el grafo de barrios
    para que el score y el orden midan la cercanía real dentro de la
    localidad, que el salto de localidad no distingue.

    Returns:
        proyectos_preseleccionados: lista de proyectos enriquecidos con la
        metadata del filtro (`_distancia_localidad`, `_distancia_km`,
        `_cobertura_zonas`, `_cumple_habitaciones`, `_nivel_relajacion`, ...).
    """
    proyectos = _cargar_proyectos(ruta_modelo)

    tipo_usuario = usuario_segmentado["tipo_vivienda"]
    localidad_usuario = usuario_segmentado["localidad"]
    barrio_usuario = usuario_segmentado.get("barrio")
    zonas_usuario = set(usuario_segmentado.get("zonas_comunes") or [])
    habitaciones_usuario = usuario_segmentado.get("numero_habitaciones") or 1

    # Restricción no negociable: el universo se reduce al tipo de vivienda.
    universo = [p for p in proyectos if p.get("tipo_vivienda_cod") == tipo_usuario]

    niveles = localidades_por_distancia(localidad_usuario)
    proyectos_preseleccionados = []
    ya_incluidos = set()

    for exige_zonas, exige_habitaciones, nivel in PASOS_RELAJACION:
        if len(proyectos_preseleccionados) >= minimo:
            break
        for distancia in sorted(niveles):
            localidades_nivel = set(niveles[distancia])
            for proyecto in universo:
                if proyecto["id_proyecto"] in ya_incluidos:
                    continue
                if proyecto.get("localidad_id") not in localidades_nivel:
                    continue
                if exige_habitaciones and not _cumple_habitaciones(proyecto, habitaciones_usuario):
                    continue
                zonas_proyecto = set(proyecto.get("zonas_comunes_idx") or [])
                coincidentes = zonas_usuario & zonas_proyecto
                # Sin zonas solicitadas el criterio de amenidades no aplica.
                # Tampoco aplica si el proyecto no publica ninguna: no se puede
                # exigir coincidencia contra una lista que no existe.
                if exige_zonas and zonas_usuario and zonas_proyecto and not coincidentes:
                    continue
                proyectos_preseleccionados.append(
                    _anotar_filtro(proyecto, distancia, coincidentes, zonas_usuario,
                                   habitaciones_usuario, nivel, barrio_usuario)
                )
                ya_incluidos.add(proyecto["id_proyecto"])
            # Se completa el nivel de distancia antes de cortar, para no partir
            # un empate de localidades igual de cercanas.
            if len(proyectos_preseleccionados) >= minimo:
                break

    # Orden de preferencia: primero lo que cumple todo, después lo relajado.
    # Dentro del mismo salto de localidad, los kilómetros del grafo de barrios
    # (si el usuario dio barrio) ponen primero al que queda más cerca.
    proyectos_preseleccionados.sort(
        key=lambda p: (p["_nivel_relajacion"], p["_distancia_localidad"],
                       p["_distancia_km"] if p["_distancia_km"] is not None else float("inf"),
                       -p["_n_zonas_coincidentes"])
    )
    return proyectos_preseleccionados


def _distancia_km(barrio_usuario, proyecto, saltos_localidad):
    """Kilómetros entre el barrio del usuario y el proyecto, y si son estimados.

    Returns:
        (km, estimada): km es None si el usuario no dio barrio, y entonces
        el score cae a la fórmula por saltos de localidad de la v0.3. Si el
        usuario sí dio barrio pero el proyecto no tiene, se estima por el
        salto de localidad (`KM_BASE_SIN_BARRIO` + `KM_POR_SALTO_LOCALIDAD`
        por salto) y se marca como estimada.
    """
    if barrio_usuario is None:
        return None, False
    km = distancia_barrios(barrio_usuario, proyecto.get("barrio_id"))
    if km is not None:
        return km, False
    return round(KM_BASE_SIN_BARRIO + KM_POR_SALTO_LOCALIDAD * saltos_localidad, 3), True


def pesos_score(proyectos_preseleccionados):
    """Los pesos del score para esta consulta.

    Si el usuario dio barrio (los candidatos traen `_distancia_km`), la
    cercanía pesa `PESO_LOCALIDAD_CON_BARRIO` y la diferencia sale de
    `modelo`; si no, `PESOS_SCORE` tal cual.
    """
    pesos = dict(PESOS_SCORE)
    if any(p.get("_distancia_km") is not None for p in proyectos_preseleccionados):
        extra = PESO_LOCALIDAD_CON_BARRIO - PESOS_SCORE["localidad"]
        pesos["localidad"] = PESO_LOCALIDAD_CON_BARRIO
        pesos["modelo"] = PESOS_SCORE["modelo"] - extra
    return pesos


def score_cercania(proyecto):
    """Afinidad [0,1] por cercanía geográfica.

    Con kilómetros (el usuario dio barrio): decae linealmente dentro de
    `RADIO_CERCANIA_KM` y sigue decayendo fuera, sin llegar nunca a 0 (ver
    `FRACCION_BORDE_CERCANIA`). Sin ellos: la fórmula por saltos de localidad
    de la v0.3, `1 - 0.25 * saltos`, para que un formulario sin barrio dé el
    mismo resultado de siempre.
    """
    km = proyecto.get("_distancia_km")
    if km is not None:
        km = max(0.0, float(km))
        if km <= RADIO_CERCANIA_KM:
            # Tramo calibrado: recta de 1,0 al borde, igual que antes salvo
            # por el 8% que se reserva para la cola.
            caida = (km / RADIO_CERCANIA_KM) * (1.0 - FRACCION_BORDE_CERCANIA)
            return 1.0 - caida
        # Fuera del radio: hipérbola que vale exactamente
        # FRACCION_BORDE_CERCANIA en el borde (la función es continua) y sigue
        # bajando. Nunca llega a 0, así que nunca deja de ordenar.
        return FRACCION_BORDE_CERCANIA * RADIO_CERCANIA_KM / km
    return max(0.0, 1.0 - 0.25 * proyecto.get("_distancia_localidad", 0))


def _cumple_habitaciones(proyecto, solicitadas):
    """¿El proyecto ofrece al menos las habitaciones pedidas?

    El formulario codifica 3 como "3 o más", así que la comparación es `>=`.
    Quien pide 2 habitaciones no queda excluido de un proyecto de 3: el filtro
    garantiza el piso y afinar el exceso es trabajo del modelo, que ya penaliza
    esa distancia vía `personas_objetivo`.

    Un proyecto que **no publica** el dato no se da por incumplido. Antes se
    trataba el vacío como un "no cumple", y eso volvía invisibles a los
    proyectos cuya constructora simplemente no lista habitaciones: 5 de los
    102 del catálogo no aparecían jamás en un Top 6, por un hueco de la fuente
    y no por su ficha. Se admiten, se marcan en `_dato_incompleto` y el score
    los penaliza.
    """
    disponibles = proyecto.get("habitaciones_max")
    if disponibles is None:
        return True
    return disponibles >= solicitadas


def _datos_incompletos(proyecto):
    """Campos que el proyecto no publica y que el filtro necesitaba evaluar."""
    faltantes = []
    if proyecto.get("habitaciones_max") is None:
        faltantes.append("habitaciones")
    if not proyecto.get("zonas_comunes_idx"):
        faltantes.append("zonas_comunes")
    return faltantes


def _anotar_filtro(proyecto, distancia, coincidentes, zonas_usuario,
                   habitaciones_usuario, relajacion, barrio_usuario=None):
    """Copia el proyecto y le añade la trazabilidad del filtro."""
    anotado = dict(proyecto)
    coincidentes = sorted(coincidentes)
    # Un match completo pero en localidad vecina se marca como nivel 1.
    nivel = 1 if (relajacion == 0 and distancia > 0) else relajacion
    faltantes = _datos_incompletos(proyecto)
    km, km_estimada = _distancia_km(barrio_usuario, proyecto, distancia)

    if not zonas_usuario:
        cobertura = 1.0                      # no pidió zonas: el criterio no aplica
    elif not proyecto.get("zonas_comunes_idx"):
        cobertura = COBERTURA_ZONAS_SIN_DATO  # el proyecto no publica amenidades
    else:
        cobertura = round(len(coincidentes) / len(zonas_usuario), 4)

    anotado.update({
        "_distancia_localidad": distancia,
        # Kilómetros por el grafo de barrios desde el barrio del usuario.
        # None si no dio barrio; estimados si el proyecto no tiene el suyo.
        "_distancia_km": km,
        "_distancia_km_estimada": km_estimada,
        "_zonas_coincidentes": coincidentes,
        "_zonas_coincidentes_nombres": nombres_zonas(coincidentes),
        "_n_zonas_coincidentes": len(coincidentes),
        "_cobertura_zonas": cobertura,
        "_dato_incompleto": faltantes,
        "_habitaciones_solicitadas": habitaciones_usuario,
        "_cumple_habitaciones": _cumple_habitaciones(proyecto, habitaciones_usuario),
        # 0 = match completo en la localidad pedida | 1 = localidad vecina
        # 2 = sin coincidencia de zonas   | 3 = menos habitaciones de las pedidas
        "_nivel_relajacion": nivel,
        # Prioridad dura para el ranking final. La expansión geográfica (nivel 1)
        # NO penaliza aquí: ya se paga en `score_localidad`. Lo que sí bloquea es
        # haber roto un requisito del filtro, y nada relajado puede quedar por
        # encima de algo que cumple todo, por mucho score que saque.
        "_prioridad_filtro": 0 if nivel in (0, 1) else nivel,
    })
    return anotado


_CACHE_PROYECTOS = {}


def _cargar_proyectos(ruta_modelo=RUTA_MODELO):
    """Carga `proyectos_model.json`, aceptando lista plana o dict con `meta`.

    Se cachea por (ruta, fecha de modificación): el catálogo se lee en cada
    recomendación y no cambia entre corridas de `prep.py`. Los proyectos que
    salen de aquí nunca se mutan (`_anotar_filtro` trabaja sobre copias).
    """
    if not os.path.exists(ruta_modelo):
        raise FileNotFoundError(
            f"No existe {ruta_modelo}. Ejecuta primero: python prep.py"
        )
    clave = (os.path.abspath(ruta_modelo), os.path.getmtime(ruta_modelo))
    if clave not in _CACHE_PROYECTOS:
        with open(ruta_modelo, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        _CACHE_PROYECTOS.clear()          # solo interesa la versión vigente
        _CACHE_PROYECTOS[clave] = datos["proyectos"] if isinstance(datos, dict) else datos
    return _CACHE_PROYECTOS[clave]


# ===========================================================================
# C. Modelo de Nearest Neighbors
# ===========================================================================
def modelo(proyectos_preseleccionados, usuario_modelo, ruta_historial=RUTA_HISTORIAL,
           top_n=TOP_N, k_vecinos=K_VECINOS, usar_subsidio=False):
    """Puntúa los preseleccionados contra el usuario y devuelve el Top `top_n`.

    Trabaja en dos modos, según haya o no histórico disponible:

    1. **Contenido** (siempre activo). Se instancia un `NearestNeighbors` sobre
       el perfil objetivo de cada proyecto preseleccionado
       ([salario_objetivo, personas_objetivo, edad_objetivo]) y se consulta con
       el vector del usuario. La distancia se convierte en afinidad.

    2. **Colaborativo** (si existe `historial_simulado.json`). Se instancia un
       segundo `NearestNeighbors` sobre los vectores de usuarios históricos; se
       buscan los `k_vecinos` más parecidos al usuario actual y se acumulan sus
       interacciones por proyecto, ponderadas por cercanía. Es el modo que
       "establece los clústeres" a partir del historial.

       Formato esperado del histórico (lista de registros; también se acepta
       {"historial": [...]}):

           {"salario": 3, "personas_a_cargo": 2, "edad": 34,
            "id_proyecto": "COL-011", "interaccion": 1.0}

       `interaccion` es opcional (default 1.0) y admite pesos por tipo de
       evento, p. ej. vista=0.2, lead=0.6, compra=1.0. También se acepta la
       forma anidada {"usuario": {...}, "id_proyecto": ..., "interaccion": ...}.

    El score final mezcla el modelo con las afinidades del filtro
    (ver `PESOS_SCORE`); todos los componentes se devuelven por separado para
    que el ranking sea auditable.

    Returns:
        proyectos_seleccionados: lista con los `top_n` mejores proyectos y su
        score, ordenada de mayor a menor.
    """
    if not proyectos_preseleccionados:
        return []

    campo_salario = "salario_objetivo_con_subsidio" if usar_subsidio else "salario_objetivo"

    # --- 1. Componente de contenido ---------------------------------------
    matriz_proyectos = np.array([
        _escalar_vector(
            proyecto.get(campo_salario, proyecto.get("salario_objetivo")),
            proyecto.get("personas_objetivo"),
            proyecto.get("edad_objetivo"),
        )
        for proyecto in proyectos_preseleccionados
    ])
    vector_usuario = np.array([_escalar_vector(
        usuario_modelo["salario"],
        usuario_modelo["personas_a_cargo"],
        usuario_modelo["edad"],
    )])

    vecinos_contenido = NearestNeighbors(
        n_neighbors=len(proyectos_preseleccionados), metric="euclidean"
    )
    vecinos_contenido.fit(matriz_proyectos)
    distancias, indices = vecinos_contenido.kneighbors(vector_usuario)

    distancia_por_indice = dict(zip(indices[0].tolist(), distancias[0].tolist()))

    # --- 2. Componente colaborativo (si hay histórico) --------------------
    scores_historial, motor = _scores_desde_historial(
        usuario_modelo, proyectos_preseleccionados, ruta_historial, k_vecinos
    )

    # --- 3. Score final ----------------------------------------------------
    pesos = pesos_score(proyectos_preseleccionados)
    resultados = []
    for posicion, proyecto in enumerate(proyectos_preseleccionados):
        distancia = distancia_por_indice.get(posicion, DISTANCIA_MAXIMA)
        afinidad_perfil = max(0.0, 1.0 - distancia / DISTANCIA_MAXIMA)

        score_historial = scores_historial.get(proyecto["id_proyecto"], 0.0)
        if scores_historial:
            score_modelo = (
                ALPHA_HISTORIAL * score_historial
                + (1 - ALPHA_HISTORIAL) * afinidad_perfil
            )
        else:
            score_modelo = afinidad_perfil

        score_zonas = float(proyecto.get("_cobertura_zonas", 0.0))
        # En km si el usuario dio barrio; por saltos de localidad si no.
        score_localidad = score_cercania(proyecto)

        # El esfuerzo de pago entra AQUÍ, y no solo en `Cota_minimaBG`, para
        # que afecte QUÉ proyectos entran al Top N y no únicamente el orden en
        # que salen: un proyecto que esta persona no puede pagar no debería
        # ocupar una de las 18 casillas por parecerse a ella demográficamente.
        esfuerzo = evaluar_esfuerzo(proyecto, usuario_modelo.get("salario"), usar_subsidio)
        score_esfuerzo_proyecto = esfuerzo["score_esfuerzo"]

        score = (
            pesos["modelo"] * score_modelo
            + pesos["esfuerzo"] * score_esfuerzo_proyecto
            + pesos["zonas"] * score_zonas
            + pesos["localidad"] * score_localidad
        )

        # Lo que no se pudo verificar se descuenta una sola vez, aquí, en vez
        # de repartirlo entre los componentes: así queda visible en el JSON
        # cuánto le costó al proyecto no publicar sus datos.
        faltantes = proyecto.get("_dato_incompleto") or []
        penalizacion = PENALIZACION_DATO_INCOMPLETO * len(faltantes)
        score = max(0.0, score - penalizacion)

        seleccionado = dict(proyecto)
        seleccionado.update({
            "score": round(float(score), 4),
            "penalizacion_dato_incompleto": round(float(penalizacion), 4),
            "score_modelo": round(float(score_modelo), 4),
            "score_afinidad_perfil": round(float(afinidad_perfil), 4),
            "score_historial": round(float(score_historial), 4),
            "score_esfuerzo": round(float(score_esfuerzo_proyecto), 4),
            "score_zonas": round(float(score_zonas), 4),
            "score_localidad": round(float(score_localidad), 4),
            "distancia_perfil": round(float(distancia), 4),
            # Trazabilidad del esfuerzo: sin estos números el score de arriba
            # no se puede explicar ni a un asesor ni a un comprador.
            "_anos_de_pago": esfuerzo["anos_de_pago"],
            "_alcanzable": esfuerzo["alcanzable"],
            "_cuota_que_puede_pagar_cop": esfuerzo["cuota_que_puede_pagar_cop"],
            "_cuota_del_proyecto_cop": esfuerzo["cuota_del_proyecto_cop"],
            "motor": motor,
        })
        resultados.append(seleccionado)

    # El score ordena DENTRO de cada tramo de prioridad, nunca entre tramos:
    # lo que cumple todos los requisitos del filtro va primero, y solo después
    # entra lo que se admitió relajando zonas o habitaciones.
    resultados.sort(key=lambda p: (p.get("_prioridad_filtro", 0), -p["score"],
                                   p["_distancia_localidad"],
                                   p.get("_distancia_km") if p.get("_distancia_km") is not None else 0.0,
                                   p["id_proyecto"]))
    proyectos_seleccionados = resultados[:top_n]
    return proyectos_seleccionados


def _escalar_vector(salario, personas, edad):
    """Lleva las tres features a [0, 1] con rangos fijos y aplica sus pesos."""
    valores = {
        "salario": salario if salario is not None else 2,
        "personas_a_cargo": personas if personas is not None else 2,
        "edad": edad if edad is not None else 35,
    }
    vector = []
    for nombre, valor in valores.items():
        minimo, maximo = RANGOS_FEATURES[nombre]
        normalizado = (float(valor) - minimo) / (maximo - minimo)
        normalizado = max(0.0, min(1.0, normalizado))   # acota fuera de rango
        vector.append(normalizado * PESOS_FEATURES[nombre])
    return vector


def k_automatico(n_registros, registros_por_perfil=1.0):
    """Vecinos a consultar para llegar a `PERFILES_A_CONSULTAR` perfiles distintos.

    Args:
        registros_por_perfil: cuántas filas del historial comparten, en
            promedio, el mismo vector (salario, personas, edad). Es lo que
            traduce "quiero 30 vecinos" a "pídele 570 filas al índice".
    """
    objetivo = PERFILES_A_CONSULTAR * max(1.0, float(registros_por_perfil))
    return max(K_VECINOS_MIN, min(K_VECINOS_MAX, int(round(objetivo))))


def _registros_por_perfil(registros):
    """Factor de repetición del historial: filas por vector distinto."""
    if not registros:
        return 1.0
    perfiles = {(r["salario"], r["personas_a_cargo"], r["edad"]) for r in registros}
    return len(registros) / len(perfiles)


def _scores_desde_historial(usuario_modelo, proyectos_preseleccionados,
                            ruta_historial, k_vecinos):
    """Puntaje colaborativo por vecinos históricos. Devuelve ({}, motor) si no hay datos."""
    registros = _cargar_historial(ruta_historial)
    if not registros:
        return {}, "contenido"

    matriz_historial = np.array([
        _escalar_vector(r["salario"], r["personas_a_cargo"], r["edad"]) for r in registros
    ])

    if k_vecinos is None:
        k_vecinos = k_automatico(len(registros), _registros_por_perfil(registros))
    k = int(min(k_vecinos, len(registros)))
    vecinos_historial = NearestNeighbors(n_neighbors=k, metric="euclidean")
    vecinos_historial.fit(matriz_historial)

    vector_usuario = np.array([_escalar_vector(
        usuario_modelo["salario"],
        usuario_modelo["personas_a_cargo"],
        usuario_modelo["edad"],
    )])
    distancias, indices = vecinos_historial.kneighbors(vector_usuario)

    ids_candidatos = {p["id_proyecto"] for p in proyectos_preseleccionados}
    acumulado = {}
    for distancia, indice in zip(distancias[0], indices[0]):
        registro = registros[int(indice)]
        id_proyecto = registro["id_proyecto"]
        if id_proyecto not in ids_candidatos:
            continue
        peso = 1.0 / (1.0 + float(distancia))    # vecino más cercano, más voto
        acumulado[id_proyecto] = acumulado.get(id_proyecto, 0.0) + peso * registro["interaccion"]

    if not acumulado:
        # Hay histórico, pero ningún vecino interactuó con estos candidatos.
        return {}, "contenido"

    maximo = max(acumulado.values())
    return {k_: v / maximo for k_, v in acumulado.items()}, "colaborativo+contenido"


def _cargar_historial(ruta_historial):
    """Lee y normaliza el histórico de interacciones. Lista vacía si no existe."""
    if not ruta_historial or not os.path.exists(ruta_historial):
        return []
    with open(ruta_historial, "r", encoding="utf-8") as archivo:
        datos = json.load(archivo)
    if isinstance(datos, dict):
        datos = datos.get("historial", [])

    registros = []
    for fila in datos:
        usuario = fila.get("usuario", fila)      # admite forma plana o anidada
        salario = _entero(usuario.get("salario"))
        personas = _entero(usuario.get("personas_a_cargo"))
        edad = _entero(usuario.get("edad"))
        id_proyecto = fila.get("id_proyecto")
        if None in (salario, personas, edad) or not id_proyecto:
            continue                             # registro incompleto: se ignora
        registros.append({
            "salario": salario,
            "personas_a_cargo": personas,
            "edad": edad,
            "id_proyecto": id_proyecto,
            "interaccion": float(fila.get("interaccion", 1.0)),
        })
    return registros


# ===========================================================================
# D. Normalización comercial del score
# ===========================================================================
def _precio_desempate(proyecto):
    """Precio del proyecto para desempatar, o infinito si no lo publica.

    Un proyecto sin precio no puede reclamar ser la mejor oferta del empate,
    así que se va al final del grupo en vez de ganarlo por defecto.
    """
    try:
        precio = float(proyecto.get("precio_desde_cop"))
    except (TypeError, ValueError):
        return float("inf")
    return precio if precio > 0 else float("inf")


def _desempatar_por_precio(ordenados, brutos):
    """Reordena los grupos que quedaron con el mismo porcentaje redondeado.

    Dentro de un empate manda el precio: entre dos proyectos que el modelo ve
    igual de compatibles, el más barato es la mejor oferta y se queda con el
    porcentaje alto; el otro baja un punto en `post_arreglos`.

    El empate se rompe **solo dentro del mismo tramo de `_prioridad_filtro`**:
    un proyecto admitido relajando requisitos no puede adelantar a uno que
    cumple todo por ser más barato. Como `brutos` no crece dentro de un tramo,
    los empates son siempre posiciones consecutivas.

    Returns:
        [(proyecto, porcentaje_bruto), ...] con los grupos reordenados.
    """
    pares = list(zip(ordenados, brutos))
    claves = [(proyecto.get("_prioridad_filtro", 0), bruto) for proyecto, bruto in pares]

    desempatados = []
    inicio = 0
    while inicio < len(pares):
        fin = inicio + 1
        while fin < len(pares) and claves[fin] == claves[inicio]:
            fin += 1
        desempatados.extend(sorted(pares[inicio:fin],
                                   key=lambda par: _precio_desempate(par[0])))
        inicio = fin
    return desempatados


def _scores_por_posicion(ordenados):
    """Reparte los scores de mayor a menor sobre el orden ya decidido.

    Se hace **dentro de cada tramo de `_prioridad_filtro`**, nunca entre
    tramos: mezclarlos permitiría que un score alto de un proyecto relajado se
    le prestara a uno que cumple todo, o al revés (invariante 4).

    El conjunto de porcentajes que ve el usuario es exactamente el mismo que
    saldría sin la cota; lo único que cambia es quién ocupa cada puesto. Así la
    caída de la lista sigue midiendo lo que mide el modelo —qué tan rápido
    empeora el encaje— y no se inventa una escala nueva.
    """
    scores = [float(p.get("score", 0.0)) for p in ordenados]
    resultado = [0.0] * len(ordenados)
    inicio = 0
    while inicio < len(ordenados):
        fin = inicio + 1
        prioridad = ordenados[inicio].get("_prioridad_filtro", 0)
        while fin < len(ordenados) and ordenados[fin].get("_prioridad_filtro", 0) == prioridad:
            fin += 1
        resultado[inicio:fin] = sorted(scores[inicio:fin], reverse=True)
        inicio = fin
    return resultado


def post_arreglos(proyectos_seleccionados, semilla=None, ruta_salida=RUTA_LLAMATIVOS):
    """Convierte los scores del modelo en porcentajes de compatibilidad.

    Dos capas, en este orden:

    1. **Normalización encadenada.** El primero muestra su propio score como
       porcentaje, elevado a `PORCENTAJE_TOP_MINIMO` si se queda corto. Cada
       uno de los siguientes resta los puntos de score que lo separan del
       proyecto inmediatamente anterior, no del líder: si el 3º tiene 0,06 de
       score menos que el 2º, muestra 6 puntos menos que el 2º. En caída
       libre, sin piso: si el encaje es malo, el porcentaje lo dice.

    2. **Desempate por precio.** La capa de arriba produce empates a propósito
       —dos scores casi iguales redondean al mismo número—, y ningún proyecto
       puede mostrar el mismo porcentaje que otro. Entre los empatados se
       queda con el número alto **el más barato**, y el resto baja de a un
       punto (`_desempatar_por_precio`).

    Args:
        semilla: se acepta por compatibilidad; ya no hay nada aleatorio que
            fijar. El porcentaje del líder sale de su score.
        ruta_salida: si no es None, guarda el resultado en ese JSON.

    Returns:
        proyectos_listos_llamativos, ordenada de mayor a menor porcentaje.
    """
    if not proyectos_seleccionados:
        return []

    # Mismo criterio que `modelo()`: la prioridad del filtro manda sobre el
    # score. La excepción es `_orden_cota`: si `Cota_minimaBG` ya corrió, el
    # orden que dejó es el bueno y volver a ordenar por score lo desharía —
    # justamente el reordenamiento por precio que esa capa acaba de hacer.
    hubo_cota = any("_orden_cota" in p for p in proyectos_seleccionados)
    if hubo_cota:
        ordenados = sorted(proyectos_seleccionados,
                           key=lambda p: (p.get("_prioridad_filtro", 0),
                                          p.get("_orden_cota", 0)))
        # La cota decide el ORDEN; el modelo decide la ESCALA. Se reparten los
        # mismos scores que el modelo produjo, pero de mayor a menor según la
        # posición final. Sin esto el porcentaje describe un ranking que ya no
        # existe: un proyecto que la cota hundió al 14º por caro seguiría
        # mostrando el 3er score más alto del top, y la lista se leería al
        # revés de como está ordenada.
        scores = _scores_por_posicion(ordenados)
    else:
        ordenados = sorted(proyectos_seleccionados,
                           key=lambda p: (p.get("_prioridad_filtro", 0), -p.get("score", 0.0)))
        scores = [float(p.get("score", 0.0)) for p in ordenados]

    # Capa 1. El líder: su score en porcentaje, con el mínimo de arriba.
    porcentaje = max(scores[0] * 100.0, PORCENTAJE_TOP_MINIMO)
    brutos = [int(round(porcentaje))]

    for anterior, actual in zip(scores, scores[1:]):
        # Cuánto peor es este que el de arriba, en puntos de score. Como la
        # cadena arranca en el score del líder, el porcentaje de cada uno
        # termina siendo su propio score más lo que se elevó al líder.
        # Se acota en 0 porque un proyecto admitido relajando requisitos puede
        # traer score bruto mayor y aun así ir detrás: nunca sube el
        # porcentaje, y el empate que eso produce lo resuelve la capa 2.
        porcentaje -= max(0.0, (anterior - actual) * 100.0)
        brutos.append(int(round(porcentaje)))

    # Capa 2. Entre los que quedaron con el mismo número manda el precio.
    ordenados = _desempatar_por_precio(ordenados, brutos)
    brutos = [bruto for _, bruto in ordenados]
    ordenados = [proyecto for proyecto, _ in ordenados]
    total = len(ordenados)

    proyectos_listos_llamativos = []
    porcentaje_anterior = None
    for posicion, (proyecto, porcentaje) in enumerate(zip(ordenados, brutos), start=1):
        if porcentaje_anterior is not None:
            # El orden debe leerse claro: siempre al menos un punto por debajo
            # del anterior. Es lo que separa a los empatados una vez que el
            # precio ya decidió cuál de ellos se queda con el número alto.
            porcentaje = min(porcentaje, porcentaje_anterior - PASO_MINIMO)
        # Que nadie se salga por abajo: se le reserva un punto a cada uno de
        # los que vienen detrás. No es un piso comercial —el último puede
        # aterrizar en 0— sino lo que impide que dos choquen contra el 0 y
        # terminen mostrando el mismo número.
        porcentaje = max(porcentaje, (total - posicion) * PASO_MINIMO)
        porcentaje_anterior = porcentaje

        listo = dict(proyecto)
        listo.update({
            "posicion": posicion,
            "porcentaje_compatibilidad": porcentaje,
            "porcentaje_texto": f"{porcentaje}%",
        })
        proyectos_listos_llamativos.append(listo)

    proyectos_listos_llamativos.sort(key=lambda p: -p["porcentaje_compatibilidad"])

    if ruta_salida:
        asegurar_salidas()
        with open(ruta_salida, "w", encoding="utf-8") as archivo:
            json.dump(proyectos_listos_llamativos, archivo, ensure_ascii=False, indent=2)

    return proyectos_listos_llamativos
