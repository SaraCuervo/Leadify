"""
Model/grafo_barrios.py
======================
El grafo de proximidad a nivel de **barrio** (sector catastral). Es la versión
fina del grafo de 20 localidades de `catalogos.py`, y existe porque "misma
localidad" es demasiado grueso para ordenar: Suba concentra un tercio del
catálogo y va de La Colina a Lisboa, que están a 8 km.

    G = (V, E, W)
    V = 1.164 sectores catastrales, con su código oficial de 6 dígitos
    E = pares de sectores cuyos polígonos comparten frontera
    W = kilómetros entre los centroides de los dos sectores

Lo que cambia respecto al grafo de localidades, y por qué:

- **Las aristas no las declara nadie a mano.** Salen de
  `data_projects/barrios_bogota_vecinos.txt`, calculado sobre la capa oficial
  de sectores catastrales (UAECD / IDECA, captura 2018) con una tolerancia de
  ~0,2 m. 1.164 listas de vecinos no se transcriben; se parsean.
- **Las aristas pesan kilómetros, no 1.** Entre localidades todas las
  fronteras valían lo mismo y el BFS era la distancia mínima. Entre barrios
  un salto puede ser 300 m o 3 km, así que el peso es la distancia entre
  centroides y la distancia mínima la da Dijkstra. El BFS en saltos se
  conserva (`saltos_barrios`) porque sigue siendo la forma legible de decir
  "está a dos barrios".
- **Los nodos tienen geometría.** Los centroides —y, si se descargó,
  `barrios_bogota_geo.json` con los polígonos simplificados— permiten ubicar
  un proyecto en su barrio a partir de la coordenada que publica la
  constructora, que es lo que la mayoría de las direcciones del catálogo
  no dicen ("Calle 235 # 52-50" no nombra ningún barrio).

Qué NO hace este módulo: no decide nada sobre admisión. `primer_filtro`
sigue expandiendo por el grafo de localidades (§3.3 del CLAUDE.md); el barrio
entra en el score (`score_localidad`) y en el orden de los candidatos, para
que dentro de una misma localidad el que queda al lado le gane al que queda
cruzando la localidad entera.

Construir el JSON compilado (una vez, o cuando cambie el TXT):

    python Model/grafo_barrios.py                 # parsea el TXT y baja la geometría
    python Model/grafo_barrios.py --sin-descargar  # solo el TXT, sin centroides
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import re
import unicodedata
from collections import deque
from functools import lru_cache

# Ejecutable por ruta (`python Model/grafo_barrios.py`) o como módulo: en el
# primer caso Python pone en el path esta carpeta y no `backend/`.
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Model.catalogos import (
    LOCALIDADES_BOGOTA,
    distancia_localidades,
    indice_localidad,
    nombre_localidad,
    normalizar_texto,
)
from Model.rutas import RUTA_BARRIOS_GEO, RUTA_BARRIOS_GRAFO, RUTA_BARRIOS_VECINOS_TXT

# Capa oficial "Sector Catastral" (Datos Abiertos Bogotá / IDECA). Es la misma
# capa con la que se calculó el TXT de vecinos, así que los códigos coinciden
# (1.152 de los 1.164 en la última verificación; los 12 restantes son sectores
# rurales que la capa viva renumeró y quedan sin centroide).
URL_SECTOR_CATASTRAL = (
    "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services/"
    "catastro/sectorcatastral/MapServer/0/query"
)
# Tolerancia de simplificación de los polígonos, en grados (~10 m). Con eso la
# capa entera pesa ~0,8 MB en vez de decenas; para decidir en qué barrio cae
# un proyecto sobra de precisión.
TOLERANCIA_GEOMETRIA_GRADOS = 0.0001

# Un punto que no cae dentro de ningún polígono (vacíos entre sectores, o un
# sector que la capa viva tiene y el TXT no) se asigna al centroide más
# cercano SOLO si está a menos de esto. Más lejos, el barrio queda en null.
RADIO_CENTROIDE_MAX_KM = 1.5

RADIO_TIERRA_KM = 6371.0088


# ===========================================================================
# Carga del grafo compilado
# ===========================================================================
_GRAFO = None          # dict{"meta": {...}, "barrios": {codigo: {...}}}
_PESOS = None          # dict{codigo: {vecino: km}}
_POR_NOMBRE = None     # dict{nombre_normalizado: [codigos]}
_POR_LOCALIDAD = None  # dict{id_localidad: [codigos]}
_POLIGONOS = None      # dict{codigo: [anillos]}  (solo si existe el geo)


def cargar_grafo(ruta=RUTA_BARRIOS_GRAFO):
    """Lee `barrios_bogota.json` una sola vez. Devuelve None si no existe.

    Sin este archivo el recomendador sigue funcionando con el grafo de
    localidades: el de barrios afina, no sostiene.
    """
    global _GRAFO, _PESOS, _POR_NOMBRE, _POR_LOCALIDAD
    if _GRAFO is not None:
        return _GRAFO or None
    if not os.path.exists(ruta):
        _GRAFO = {}
        return None
    with open(ruta, "r", encoding="utf-8") as archivo:
        _GRAFO = json.load(archivo)

    barrios = _GRAFO["barrios"]
    mediana = float(_GRAFO.get("meta", {}).get("km_arista_mediana") or 0.6)
    _PESOS, _POR_NOMBRE, _POR_LOCALIDAD = {}, {}, {}
    for codigo, barrio in barrios.items():
        _POR_NOMBRE.setdefault(normalizar_texto(barrio["nombre"]), []).append(codigo)
        _POR_LOCALIDAD.setdefault(int(barrio["localidad"]), []).append(codigo)
        pesos = {}
        for vecino in barrio["vecinos"]:
            km = _haversine_km(barrio.get("centroide"), barrios.get(vecino, {}).get("centroide"))
            # Sin centroide en alguno de los dos extremos, la arista pesa lo
            # que pesa una arista típica: es mejor que 0 (los pegaría) y que
            # infinito (los desconectaría).
            pesos[vecino] = km if km is not None else mediana
        _PESOS[codigo] = pesos
    return _GRAFO


def hay_grafo_barrios():
    """¿Está disponible el grafo de barrios? El pipeline pregunta antes de usarlo."""
    return cargar_grafo() is not None


def _barrios():
    grafo = cargar_grafo()
    return grafo["barrios"] if grafo else {}


def _haversine_km(a, b):
    """Distancia sobre la esfera entre dos [lon, lat]. None si falta alguno."""
    if not a or not b:
        return None
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(h))


# ===========================================================================
# Resolución de barrios
# ===========================================================================
def indice_barrio(valor, localidad=None):
    """Convierte un código de 6 dígitos o un nombre de barrio en su código.

    `localidad` (id o nombre) desambigua: hay 62 nombres repetidos en la
    ciudad ("Santa Bárbara" existe en Santa Fe y en Ciudad Bolívar). Con la
    localidad se elige el de esa localidad; sin ella, un nombre repetido en
    dos localidades distintas devuelve None en vez de adivinar.
    """
    barrios = _barrios()
    if not barrios or valor is None or isinstance(valor, bool):
        return None
    texto = str(valor).strip()
    if re.fullmatch(r"\d{6}", texto):
        return texto if texto in barrios else None
    if re.fullmatch(r"\d{1,5}", texto):        # código sin ceros a la izquierda
        texto = texto.zfill(6)
        return texto if texto in barrios else None

    candidatos = _POR_NOMBRE.get(normalizar_texto(texto), [])
    if not candidatos:
        return None
    loc = indice_localidad(localidad) if localidad is not None else None
    if loc is not None:
        candidatos = [c for c in candidatos if int(barrios[c]["localidad"]) == loc]
        # Dos sectores con el mismo nombre en la misma localidad son, casi
        # siempre, el mismo barrio partido en dos por catastro (los polígonos
        # se tocan). Cualquiera de los dos es una respuesta válida: se toma
        # el urbano (código que empieza por 0) antes que el rural.
        return sorted(candidatos)[0] if candidatos else None
    localidades = {int(barrios[c]["localidad"]) for c in candidatos}
    return sorted(candidatos)[0] if len(localidades) == 1 else None


def nombre_barrio(codigo):
    barrio = _barrios().get(codigo)
    return barrio["nombre"] if barrio else None


def localidad_de_barrio(codigo):
    """Id de la localidad a la que pertenece el barrio, o None."""
    barrio = _barrios().get(codigo)
    return int(barrio["localidad"]) if barrio else None


def centroide_barrio(codigo):
    """(lat, lon) del centroide, o None si el sector no tiene geometría."""
    barrio = _barrios().get(codigo)
    if not barrio or not barrio.get("centroide"):
        return None
    lon, lat = barrio["centroide"]
    return (lat, lon)


def barrios_de_localidad(id_localidad):
    """[(codigo, nombre), ...] de una localidad, ordenados por nombre.

    Es lo que sirve `GET /api/barrios` para que el front arme un desplegable
    dependiente de la localidad sin copiar 1.164 nombres.
    """
    cargar_grafo()
    loc = indice_localidad(id_localidad)
    if loc is None or not _POR_LOCALIDAD:
        return []
    barrios = _barrios()
    return sorted(
        ((c, barrios[c]["nombre"]) for c in _POR_LOCALIDAD.get(loc, [])),
        key=lambda par: normalizar_texto(par[1]),
    )


def _veredicto(codigo, confianza, evidencia):
    return {
        "barrio": codigo,
        "nombre": nombre_barrio(codigo),
        "localidad": localidad_de_barrio(codigo),
        "confianza": confianza,
        "evidencia": evidencia,
    }


_VEREDICTO_VACIO = {"barrio": None, "nombre": None, "localidad": None,
                    "confianza": None, "evidencia": None}


def barrio_desde_direccion(direccion, localidad=None):
    """Busca en la dirección el nombre de un barrio del grafo.

    Se prueban los nombres de más largo a más corto —"San Cristóbal Norte" le
    gana a "San Cristóbal"— y solo cuentan como coincidencia si aparecen como
    palabras completas. Con `localidad` se restringe a esa localidad y, si
    ahí no hay nada, a las vecinas (la constructora a veces nombra el barrio
    comercial, que cae al otro lado de la frontera): esa segunda pasada sale
    con confianza `media`.

    Nombres de menos de 5 letras no se buscan: "Roma", "Muzú" o "Bosa" como
    palabras sueltas aparecen en direcciones de otras partes de la ciudad.
    """
    cargar_grafo()
    texto = normalizar_texto(direccion)
    if not texto or not _POR_NOMBRE:
        return dict(_VEREDICTO_VACIO)
    loc = indice_localidad(localidad) if localidad is not None else None
    barrios = _barrios()

    mejor = None
    for nombre, codigos in _nombres_ordenados():
        if len(nombre) < 5 or not re.search(rf"(?<![a-z0-9]){re.escape(nombre)}(?![a-z0-9])", texto):
            continue
        if loc is None:
            localidades = {int(barrios[c]["localidad"]) for c in codigos}
            if len(localidades) == 1:
                return _veredicto(sorted(codigos)[0], "media",
                                  f"barrio en la direccion: {nombre_barrio(sorted(codigos)[0])}")
            continue        # nombre repetido en varias localidades y sin pista
        propios = sorted(c for c in codigos if int(barrios[c]["localidad"]) == loc)
        if propios:
            return _veredicto(propios[0], "alta",
                              f"barrio en la direccion: {nombre_barrio(propios[0])}")
        if mejor is None:
            vecinos = sorted(c for c in codigos
                             if (distancia_localidades(loc, int(barrios[c]["localidad"])) or 9) <= 1)
            if vecinos:
                mejor = _veredicto(vecinos[0], "media",
                                   f"barrio en la direccion, en localidad vecina: "
                                   f"{nombre_barrio(vecinos[0])} ({nombre_localidad(localidad_de_barrio(vecinos[0]))})")
    return mejor or dict(_VEREDICTO_VACIO)


@lru_cache(maxsize=1)
def _nombres_ordenados():
    cargar_grafo()
    return tuple(sorted(_POR_NOMBRE.items(), key=lambda kv: -len(kv[0])))


def _cargar_poligonos(ruta=RUTA_BARRIOS_GEO):
    global _POLIGONOS
    if _POLIGONOS is not None:
        return _POLIGONOS
    if not os.path.exists(ruta):
        _POLIGONOS = {}
        return _POLIGONOS
    with open(ruta, "r", encoding="utf-8") as archivo:
        crudo = json.load(archivo)
    _POLIGONOS = crudo.get("poligonos", {})
    return _POLIGONOS


def _punto_en_anillo(lon, lat, anillo):
    """Ray casting clásico sobre un anillo [[lon, lat], ...]."""
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if (yi > lat) != (yj > lat):
            corte = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < corte:
                dentro = not dentro
        j = i
    return dentro


def _punto_en_poligono(lon, lat, anillos):
    dentro = False
    for anillo in anillos:
        if anillo and _punto_en_anillo(lon, lat, anillo):
            dentro = not dentro     # los huecos invierten la pertenencia
    return dentro


def barrio_desde_coordenadas(lat, lon, localidad=None):
    """Barrio en el que cae una coordenada.

    1. Punto dentro del polígono de un sector del grafo -> confianza `alta`.
    2. Si no cae en ninguno (huecos entre sectores, sectores que la capa viva
       tiene y el TXT no), el centroide más cercano a menos de
       `RADIO_CENTROIDE_MAX_KM` -> confianza `media`.

    Con `localidad` se exige que el barrio encontrado esté en esa localidad:
    si la coordenada dice otra cosa que la dirección, la coordenada es la
    sospechosa (el pin de la sala de ventas, ver §6.3 del CLAUDE.md) y se
    devuelve vacío en vez de contradecir la localidad ya asignada.
    """
    cargar_grafo()
    if lat is None or lon is None or not _barrios():
        return dict(_VEREDICTO_VACIO)
    lat, lon = float(lat), float(lon)
    loc = indice_localidad(localidad) if localidad is not None else None
    barrios = _barrios()

    def _admite(codigo):
        return loc is None or int(barrios[codigo]["localidad"]) == loc

    for codigo, anillos in _cargar_poligonos().items():
        if codigo in barrios and _admite(codigo) and _punto_en_poligono(lon, lat, anillos):
            return _veredicto(codigo, "alta",
                              f"coordenada dentro del sector catastral ({lat:.5f}, {lon:.5f})")

    mejor, mejor_km = None, None
    for codigo, barrio in barrios.items():
        if not barrio.get("centroide") or not _admite(codigo):
            continue
        km = _haversine_km([lon, lat], barrio["centroide"])
        if mejor_km is None or km < mejor_km:
            mejor, mejor_km = codigo, km
    if mejor is not None and mejor_km <= RADIO_CENTROIDE_MAX_KM:
        return _veredicto(mejor, "media",
                          f"centroide de sector mas cercano a {mejor_km:.2f} km ({lat:.5f}, {lon:.5f})")
    return dict(_VEREDICTO_VACIO)


# ===========================================================================
# Recorridos sobre el grafo
# ===========================================================================
@lru_cache(maxsize=512)
def _bfs_saltos(origen):
    """Saltos mínimos desde `origen` a cada barrio alcanzable. Inmutable, cacheado."""
    saltos = {origen: 0}
    cola = deque([origen])
    while cola:
        actual = cola.popleft()
        for vecino in _barrios().get(actual, {}).get("vecinos", []):
            if vecino not in saltos:
                saltos[vecino] = saltos[actual] + 1
                cola.append(vecino)
    return tuple(sorted(saltos.items()))


@lru_cache(maxsize=512)
def _dijkstra(origen):
    """Kilómetros mínimos por el grafo desde `origen`. Inmutable, cacheado.

    Es Dijkstra y no BFS porque las aristas ya no pesan igual: entre barrios
    un salto puede ser 300 m o 3 km, y contarlos como iguales devolvería el
    problema que este grafo viene a resolver.
    """
    cargar_grafo()
    distancias = {origen: 0.0}
    monticulo = [(0.0, origen)]
    while monticulo:
        km, actual = heapq.heappop(monticulo)
        if km > distancias.get(actual, math.inf):
            continue
        for vecino, peso in _PESOS.get(actual, {}).items():
            nuevo = km + peso
            if nuevo < distancias.get(vecino, math.inf):
                distancias[vecino] = nuevo
                heapq.heappush(monticulo, (nuevo, vecino))
    return tuple(sorted(distancias.items()))


def saltos_barrios(origen, destino):
    """Número mínimo de fronteras de barrio entre dos códigos. None si no se resuelve."""
    origen, destino = indice_barrio(origen), indice_barrio(destino)
    if origen is None or destino is None:
        return None
    return dict(_bfs_saltos(origen)).get(destino)


def distancia_barrios(origen, destino):
    """Kilómetros mínimos por el grafo entre dos barrios. None si no se resuelve.

    Es la distancia que consume `score_localidad` en `modelo.py`. Como sigue
    las aristas de vecindad y no la línea recta, se parece más al recorrido
    real por la ciudad que la distancia euclidiana entre centroides.
    """
    origen, destino = indice_barrio(origen), indice_barrio(destino)
    if origen is None or destino is None:
        return None
    km = dict(_dijkstra(origen)).get(destino)
    return round(km, 3) if km is not None else None


def barrios_por_distancia(origen, km_maximo=None):
    """[(codigo, km), ...] ordenado por cercanía, con el propio origen en 0.0.

    Es el equivalente de `orden_expansion` del grafo de localidades, en
    kilómetros. `km_maximo` corta la lista.
    """
    origen = indice_barrio(origen)
    if origen is None:
        return []
    pares = sorted(_dijkstra(origen), key=lambda par: (par[1], par[0]))
    if km_maximo is not None:
        pares = [par for par in pares if par[1] <= km_maximo]
    return [(codigo, round(km, 3)) for codigo, km in pares]


# ===========================================================================
# Construcción del JSON compilado
# ===========================================================================
_RE_LOCALIDAD = re.compile(r"^LOCALIDAD (\d+) - ")
_RE_BARRIO = re.compile(r"^(\d{6})  (.+)$")
_RE_VECINOS = re.compile(r"^\s+Vecinos \((\d+)\):\s*(.*)$")
_RE_OTRA_LOCALIDAD = re.compile(r"^(.*?)\s*\(L(\d+)\)$")


def parsear_vecinos_txt(ruta=RUTA_BARRIOS_VECINOS_TXT, poligonos=None):
    """Convierte el TXT de vecinos en nodos y aristas.

    Formato de entrada (por localidad):

        008510  Acacias Usaquen
            Vecinos (5): Bosque De Pinos I; Caobos Salazar; Cedro Narvaez; Los
              Cedros; Los Cedros Oriental

    Un vecino marcado "(L#)" está en otra localidad. Los nombres se resuelven
    a código dentro de la localidad que corresponda. Cuando un nombre se
    repite dentro de esa misma localidad (catastro parte algunos barrios en
    dos sectores homónimos) el TXT no dice a cuál se refiere: si hay
    `poligonos`, se elige el homónimo cuya caja envolvente toca la del
    origen; si no los hay, se conecta con todos —la arista sobrante une dos
    polígonos que ya se tocan entre sí, así que no acorta ningún camino que
    no exista— y queda anotado en `avisos["vecino_ambiguo"]`.

    Returns:
        (barrios, avisos) con barrios = {codigo: {nombre, localidad, vecinos}}
    """
    with open(ruta, "r", encoding="utf-8") as archivo:
        lineas = archivo.read().splitlines()

    barrios, pendientes = {}, {}     # pendientes: codigo -> [(nombre, localidad)]
    localidad_actual, codigo_actual, esperados = None, None, None
    acumulado = []

    def _cerrar():
        if codigo_actual is None or not acumulado:
            return
        tokens = [t.strip() for t in " ".join(acumulado).split(";") if t.strip()]
        if esperados is not None and len(tokens) != esperados:
            avisos["conteo_distinto"].append(f"{codigo_actual}: dice {esperados}, trae {len(tokens)}")
        vecinos = []
        for token in tokens:
            marca = _RE_OTRA_LOCALIDAD.match(token)
            if marca:
                vecinos.append((marca.group(1).strip(), int(marca.group(2))))
            else:
                vecinos.append((token, localidad_actual))
        pendientes[codigo_actual] = vecinos

    avisos = {"conteo_distinto": [], "vecino_no_resuelto": [], "vecino_ambiguo": []}
    for linea in lineas:
        cabecera = _RE_LOCALIDAD.match(linea)
        if cabecera:
            _cerrar()
            codigo_actual, acumulado = None, []
            localidad_actual = int(cabecera.group(1))
            continue
        inicio = _RE_BARRIO.match(linea)
        if inicio and localidad_actual is not None:
            _cerrar()
            codigo_actual, acumulado, esperados = inicio.group(1), [], None
            barrios[codigo_actual] = {
                "nombre": _titulo(inicio.group(2).strip()),
                "localidad": localidad_actual,
                "vecinos": [],
            }
            continue
        lista = _RE_VECINOS.match(linea)
        if lista and codigo_actual is not None:
            esperados = int(lista.group(1))
            acumulado = [lista.group(2)]
            continue
        if codigo_actual is not None and acumulado and linea.startswith("      "):
            acumulado.append(linea.strip())
            continue
        if not linea.strip():
            _cerrar()
            codigo_actual, acumulado = None, []
    _cerrar()

    # nombre normalizado + localidad -> códigos
    indice = {}
    for codigo, barrio in barrios.items():
        indice.setdefault((normalizar_texto(barrio["nombre"]), barrio["localidad"]), []).append(codigo)

    cajas = {c: _caja(a) for c, a in (poligonos or {}).items()}
    for codigo, vecinos in pendientes.items():
        destinos = set()
        for nombre, localidad in vecinos:
            candidatos = indice.get((normalizar_texto(nombre), localidad), [])
            if not candidatos:
                avisos["vecino_no_resuelto"].append(f"{codigo} -> {nombre} (L{localidad})")
                continue
            if len(candidatos) > 1 and codigo in cajas:
                tocan = [c for c in candidatos if c in cajas and _cajas_se_tocan(cajas[codigo], cajas[c])]
                if tocan:
                    candidatos = tocan
            if len(candidatos) > 1:
                avisos["vecino_ambiguo"].append(f"{codigo} -> {nombre} (L{localidad}): {candidatos}")
            destinos.update(candidatos)
        destinos.discard(codigo)
        barrios[codigo]["vecinos"] = sorted(destinos)

    # Simetrizar: si a lista a b, b lista a a. El TXT ya es simétrico por
    # construcción, pero la resolución de homónimos puede dejar un lado solo.
    for codigo, barrio in barrios.items():
        for vecino in barrio["vecinos"]:
            if codigo not in barrios[vecino]["vecinos"]:
                barrios[vecino]["vecinos"].append(codigo)
    for barrio in barrios.values():
        barrio["vecinos"].sort()
    return barrios, avisos


def _caja(anillos):
    """Caja envolvente (lon_min, lat_min, lon_max, lat_max) de un polígono."""
    puntos = [p for anillo in anillos for p in anillo]
    return (min(p[0] for p in puntos), min(p[1] for p in puntos),
            max(p[0] for p in puntos), max(p[1] for p in puntos))


def _cajas_se_tocan(a, b, holgura=0.0005):
    """¿Dos cajas se solapan, con ~50 m de holgura por la simplificación?"""
    return not (a[2] + holgura < b[0] or b[2] + holgura < a[0]
                or a[3] + holgura < b[1] or b[3] + holgura < a[1])


def _titulo(nombre):
    """'Acacias Usaquen' -> 'Acacias Usaquén'? No: no se inventan tildes.

    Solo se corrigen partículas ('De', 'Del', 'La', 'Y') y los ordinales
    romanos ('Ii' -> 'II'), que el TXT trae en Title Case mecánico.
    """
    partes = []
    for i, palabra in enumerate(nombre.split()):
        baja = palabra.lower()
        if i > 0 and baja in ("de", "del", "la", "las", "los", "el", "y", "o"):
            partes.append(baja)
        elif re.fullmatch(r"[ivx]+", baja):
            partes.append(baja.upper())
        else:
            partes.append(palabra)
    return " ".join(partes)


def descargar_geometria(ruta=RUTA_BARRIOS_GEO, tolerancia=TOLERANCIA_GEOMETRIA_GRADOS):
    """Baja los polígonos simplificados de la capa oficial y los deja en `ruta`.

    Se guarda solo lo que hace falta para resolver un punto: código, nombre
    y anillos [lon, lat] con 5 decimales. Devuelve el dict de polígonos.
    """
    import urllib.parse
    import urllib.request

    poligonos, nombres, desplazamiento = {}, {}, 0
    while True:
        parametros = urllib.parse.urlencode({
            "where": "1=1",
            "outFields": "SCACODIGO,SCANOMBRE",
            "returnGeometry": "true",
            "outSR": "4326",
            "maxAllowableOffset": tolerancia,
            "geometryPrecision": 5,
            "resultOffset": desplazamiento,
            "resultRecordCount": 2000,
            "f": "json",
        })
        with urllib.request.urlopen(f"{URL_SECTOR_CATASTRAL}?{parametros}", timeout=300) as respuesta:
            pagina = json.load(respuesta)
        if "error" in pagina:
            raise RuntimeError(f"la capa de sectores respondio con error: {pagina['error']}")
        for feature in pagina.get("features", []):
            atributos = feature.get("attributes") or {}
            codigo = str(atributos.get("SCACODIGO") or "").strip()
            anillos = (feature.get("geometry") or {}).get("rings") or []
            if codigo and anillos:
                poligonos[codigo] = anillos
                nombres[codigo] = atributos.get("SCANOMBRE")
        if not pagina.get("exceededTransferLimit"):
            break
        desplazamiento += len(pagina.get("features", []))

    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump({
            "meta": {
                "fuente": URL_SECTOR_CATASTRAL,
                "tolerancia_grados": tolerancia,
                "n_sectores": len(poligonos),
                "nota": "anillos [lon, lat] simplificados; solo para ubicar puntos",
            },
            "nombres": nombres,
            "poligonos": poligonos,
        }, archivo, ensure_ascii=False, separators=(",", ":"))
    return poligonos


def _centroide(anillos):
    """Centroide por fórmula del polígono (shoelace) sobre el anillo mayor."""
    anillo = max(anillos, key=len)
    area, cx, cy = 0.0, 0.0, 0.0
    for i in range(len(anillo)):
        x1, y1 = anillo[i][0], anillo[i][1]
        x2, y2 = anillo[(i + 1) % len(anillo)][0], anillo[(i + 1) % len(anillo)][1]
        cruz = x1 * y2 - x2 * y1
        area += cruz
        cx += (x1 + x2) * cruz
        cy += (y1 + y2) * cruz
    if abs(area) < 1e-12:       # degenerado: promedio de vértices
        return [round(sum(p[0] for p in anillo) / len(anillo), 6),
                round(sum(p[1] for p in anillo) / len(anillo), 6)]
    area *= 0.5
    return [round(cx / (6 * area), 6), round(cy / (6 * area), 6)]


def construir(ruta_txt=RUTA_BARRIOS_VECINOS_TXT, ruta_geo=RUTA_BARRIOS_GEO,
              ruta_salida=RUTA_BARRIOS_GRAFO, descargar=True, verbose=True):
    """TXT de vecinos (+ geometría oficial) -> `barrios_bogota.json`."""
    poligonos = {}
    if os.path.exists(ruta_geo):
        with open(ruta_geo, "r", encoding="utf-8") as archivo:
            poligonos = json.load(archivo).get("poligonos", {})
    elif descargar:
        try:
            poligonos = descargar_geometria(ruta_geo)
        except Exception as error:      # sin red el grafo igual se construye
            print(f"  [aviso] no se pudo bajar la geometria de sectores: {error}")

    barrios, avisos = parsear_vecinos_txt(ruta_txt, poligonos)

    sin_centroide = []
    for codigo, barrio in barrios.items():
        if codigo in poligonos:
            barrio["centroide"] = _centroide(poligonos[codigo])
        else:
            barrio["centroide"] = None
            sin_centroide.append(codigo)

    kms = []
    for codigo, barrio in barrios.items():
        for vecino in barrio["vecinos"]:
            if codigo < vecino:
                km = _haversine_km(barrio["centroide"], barrios[vecino]["centroide"])
                if km is not None:
                    kms.append(km)
    kms.sort()
    n_aristas = sum(len(b["vecinos"]) for b in barrios.values()) // 2

    salida = {
        "meta": {
            "fuente_aristas": os.path.basename(ruta_txt),
            "fuente_geometria": os.path.basename(ruta_geo) if poligonos else None,
            "n_barrios": len(barrios),
            "n_aristas": n_aristas,
            "n_sin_centroide": len(sin_centroide),
            "sin_centroide": sin_centroide,
            "km_arista_mediana": round(kms[len(kms) // 2], 3) if kms else None,
            "km_arista_media": round(sum(kms) / len(kms), 3) if kms else None,
            "peso_arista": "km entre centroides (haversine); mediana si falta centroide",
            "localidades": {str(i + 1): n for i, n in enumerate(LOCALIDADES_BOGOTA)},
            "avisos": {k: v for k, v in avisos.items() if v},
        },
        "barrios": barrios,
    }
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8") as archivo:
        json.dump(salida, archivo, ensure_ascii=False, indent=1)

    if verbose:
        meta = salida["meta"]
        print(f"[grafo_barrios] {meta['n_barrios']} barrios, {meta['n_aristas']} aristas "
              f"-> {os.path.basename(ruta_salida)}")
        print(f"[grafo_barrios] con centroide: {meta['n_barrios'] - meta['n_sin_centroide']} "
              f"| arista mediana: {meta['km_arista_mediana']} km | media: {meta['km_arista_media']} km")
        for clave, mensajes in meta["avisos"].items():
            print(f"[grafo_barrios] AVISO {clave} ({len(mensajes)}): {mensajes[:5]}")
    return salida


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compila el grafo de barrios desde el TXT de vecinos.")
    parser.add_argument("--txt", default=RUTA_BARRIOS_VECINOS_TXT)
    parser.add_argument("--geo", default=RUTA_BARRIOS_GEO)
    parser.add_argument("--salida", default=RUTA_BARRIOS_GRAFO)
    parser.add_argument("--sin-descargar", action="store_true",
                        help="no bajar la geometria oficial aunque falte (sin centroides)")
    args = parser.parse_args(argv)
    construir(args.txt, args.geo, args.salida, descargar=not args.sin_descargar)


if __name__ == "__main__":
    main()
