#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Genera `js/mapa_bogota.js` y `js/mapa_barrios.js`: el mapa clicable de Bogota,
la geometria de los barrios y el indice del buscador. Uso:

    python tools/generar_mapa.py

ESTO NO ES UN BUILD STEP. Se corre a mano cuando cambien los limites oficiales
o el gazetteer; `app/` sigue funcionando con el archivo ya generado. Igual que
tools/empaquetar_demo.py, si se rompe, la app no se entera.

DE DONDE SALE CADA COSA
-----------------------
- La geometria, de `datos/localidades_bogota.json` (Datos Abiertos Bogota).
  Es esriJSON, no GeoJSON: los pares viven en `geometry.rings`, no en
  `coordinates`, y el id de la localidad es `attributes.LocCodigo`.
- Los nombres, de `catalogos.LOCALIDADES_BOGOTA`, NO del propio archivo. El
  esriJSON trae "CANDELARIA" (mayusculas, sin "La") y "USAQUEN" sin tilde, y
  esos strings no cruzarian con la tabla de `js/machea.js`, que es la que
  convierte el nombre en `Localidad` 1..20 para el modelo.
- Los barrios del BUSCADOR, de `scraper_projects._GAZETTEER`. Se LEE, no se
  copia.
- Los barrios del MAPA, de la capa "Sector catastral" de IDECA (capa 37 de
  Mapa_Referencia). Son 1.231 poligonos y se bajan una vez a
  `tools/.cache_barrios.json`.

EL GAZETTEER SIGUE SIENDO LA UNICA FUENTE PARA RESOLVER DIRECCIONES
-------------------------------------------------------------------
`GDF_BARRIOS` (el indice del buscador) es un SUPERCONJUNTO: el gazetteer mas
los nombres de sector catastral que no estaban. Eso vale para buscar y para
pintar, y para nada mas. `scraper_projects._GAZETTEER` no cambia, y sigue
siendo lo unico que decide en que localidad cae una direccion del catalogo:
ahi entra solo lo que se puede afirmar, y esta capa trae 1.150 nombres de los
que muchos son ambiguos entre localidades.

POR QUE HAY QUE SIMPLIFICAR
---------------------------
El archivo son 57.840 vertices para 20 poligonos. La Candelaria sola gasta
13.201 en 2 km2: la distancia mediana entre vertices consecutivos es ~0,50 m.
Eso es geometria de catastro. En pantalla un mapa de 800 px cubre unos 26 km,
o sea ~32 m por pixel, asi que sobran unos 60x los puntos. Se simplifica con
Douglas-Peucker hasta bajar de OBJETIVO_PUNTOS.

LAS DOS TRAMPAS DEL DATASET
---------------------------
1. LA CANDELARIA ES UN AGUJERO DENTRO DE SANTA FE. Santa Fe (id 3) es el unico
   feature con dos anillos, y el segundo es exactamente el contorno de La
   Candelaria con el giro invertido. En GeoJSON eso ES un agujero, y Leaflet lo
   respeta solo: La Candelaria queda clicable sin trucos. (En la version SVG de
   esto hacia falta fill-rule="evenodd" o Santa Fe la tapaba.)
2. SUMAPAZ SE DIBUJA, PERO NO ENTRA EN EL ENCUADRE INICIAL. Es el 78 % del area
   del Distrito, es rural y no tiene un solo proyecto del catalogo. Si entrara
   en el `bbox`, el mapa abriria tan alejado que la ciudad quedaria en un tercio
   de la pantalla.

   Y no basta con sacarla: el limite administrativo de Usme y Ciudad Bolivar
   tambien baja al paramo, asi que el encuadre inicial NO sale de los limites
   de las localidades sino de la extension de los sectores catastrales urbanos
   (SCATIPO 0), que llega hasta el casco de Usme. Esa es la Bogota que la gente
   reconoce como Bogota. El Distrito completo sigue siendo el limite de paneo.
"""

from __future__ import annotations

import json
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
EXPERIENCIA = os.path.dirname(AQUI)
RAIZ = os.path.dirname(EXPERIENCIA)
sys.path.insert(0, RAIZ)

from catalogos import LOCALIDADES_BOGOTA, normalizar_texto  # noqa: E402
import scraper_projects as sp  # noqa: E402

GEO = os.path.join(RAIZ, "datos", "localidades_bogota.json")
SALIDA = os.path.join(EXPERIENCIA, "js", "mapa_bogota.js")
SALIDA_BARRIOS = os.path.join(EXPERIENCIA, "js", "mapa_barrios.js")

# Capa 37 "Sector catastral" del Mapa de Referencia de IDECA. Es la unica
# fuente publica con el contorno de cada barrio; el gazetteer solo tiene
# nombres. `maxAllowableOffset` simplifica DEL LADO DEL SERVIDOR, que es lo que
# baja los 1,2 millones de vertices del original a 18 mil sin traerselos.
SECTORES_URL = (
    "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services"
    "/Mapa_Referencia/Mapa_Referencia/MapServer/37/query"
)
SECTORES_PAGINA = 1000  # el maxRecordCount que declara la capa
# Grados. 0,0001 son ~11 m. Se pide FINO al servidor y se aprieta despues por
# barrio (ver `simplificar_adaptativo`): con un 0,0003 global, Cedritos —1,4 km
# de lado— se quedaba en 6 vertices y se dibujaba como una cuna torcida encima
# de las calles. A 0,0001 llegan 24 y el contorno vuelve a seguir la malla.
SECTORES_OFFSET = 0.0001
# El nombre del cache lleva el offset: cambiarlo obliga a volver a bajar, en
# vez de reusar en silencio una geometria mas gruesa.
CACHE_BARRIOS = os.path.join(AQUI, ".cache_barrios_%s.json" % SECTORES_OFFSET)

# LOS BARRIOS "DE VERDAD" SON PUNTOS DE OPENSTREETMAP. No existe ninguna fuente
# publica con el contorno de barrios como Cantalejo o Pontevedra: la unidad
# mas fina que publica el Distrito es el sector catastral, y un sector suele
# contener varios barrios (Cantalejo esta dentro del sector "Gilmar"). Se
# revisaron las 58 capas del Mapa de Referencia y las 22 de ordenamiento
# territorial de IDECA, Datos Abiertos Bogota y OSM: nada tiene esos
# poligonos. OSM si tiene el PUNTO de ~1.100 barrios (`place=neighbourhood`),
# y con eso cada sector se parte en celdas, una por barrio (ver
# `partir_sector`). Bbox = la Bogota urbana con margen: sur,oeste,norte,este.
OSM_BBOX = "4.45,-74.25,4.85,-73.98"
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
CACHE_OSM = os.path.join(AQUI, ".cache_osm_barrios.json")
# Dos puntos de OSM a menos de esto (grados, ~40 m) son el mismo barrio
# cargado dos veces: se queda el primero. Mas cerca que eso la bisectriz
# partiria el sector en dos celdas que nadie distingue.
MINIMO_ENTRE_PUNTOS = 0.00035

# Barrios del gazetteer que OSM no tiene como punto: se cuelgan a mano del
# poligono (sector o celda) que los contiene, por su clave. Lo que no este
# aqui ni en OSM se DESCARTA del buscador y se lista al final: es preferible
# que un nombre no aparezca a que aparezca y no pinte nada.
BARRIO_MANUAL = {
    # Usaquen
    "santa barbara": "santa barbara central",
    "toberin": "el toberin",
    "el codito": "codito",
    "pepe sierra": "santa barbara occidental",
    # Chapinero
    "chapinero alto": "chapinero central",
    "chico": "el chico",
    "zona rosa": "el retiro",
    "zona g": "los rosales",
    "rosales": "los rosales",
    "el virrey": "la cabrera",
    "la porciuncula": "porciuncula",
    # San Cristobal
    "20 de julio": "veinte de julio",
    "la gloria": "la gloria occidental",
    "sosiego": "sociego",
    # Usme
    "portal de usme": "ciudadela del portal",
    "ciudad usme": "usme centro",
    "marichuela": "la marichuela",
    "tocaimita": "tocaimita oriental",
    # Tunjuelito
    "ontario": "venecia",
    "el tunal": "tunal oriental",
    "tunal": "tunal oriental",
    # Bosa
    "bosa recreo": "el recreo",
    "bosa central": "bosa",
    "bosa porvenir": "parcela el porvenir",
    "el porvenir": "parcela el porvenir",
    "brasilia bosa": "brasilia",
    # Kennedy
    "kennedy central": "ciudad kennedy central",
    "tintal": "tintala",
    "ciudad tintal": "tintala",
    "el tintal": "tintala",
    # Fontibon
    "hayuelos": "ciudad hayuelos",
    "ciudad salitre occidente": "salitre occidental",
    "fontibon centro": "fontibon",
    "san pablo fontibon": "san pablo jerico",
    "ferrocaja": "ferrocaja fontibon",
    # Engativa
    "boyaca real": "boyaca",
    "minuto de dios": "el minuto de dios",
    # Suba
    "la colina": "nueva zelandia",
    "colina campestre": "nueva zelandia",
    "niza": "niza suba",
    "britalia norte": "britalia",
    "julio flores": "julio florez",
    "salitre norte": "salitre suba",
    "lagos de torca": "lagos de torca el carmen",
    "hacienda el otono": "el otono",
    # Barrios Unidos
    "12 de octubre": "doce de octubre",
    "los alcazares": "alcazares",
    "entrerrios": "entrerios",
    "el polo": "polo club",
    # Teusaquillo
    "ciudad salitre": "ciudad salitre nor oriental",
    "el campin": "campin",
    "corferias": "quinta paredes",
    # Antonio Narino
    "ciudad jardin": "ciudad jardin sur",
    # Puente Aranda
    "la primavera": "primavera occidental",
    "zona industrial": "centro industrial",
    # La Candelaria
    "belen candelaria": "belen",
    "centro historico": "la catedral",
    # Ciudad Bolivar
    "el lucero": "lucero alto",
    "arborizadora": "arborizadora baja",
    "mochuelo": "el mochuelo",
    # Sumapaz
    "betania sumapaz": "betania",
    "san juan de sumapaz": "san juan",
}

# Grados decimales. 5 son ~1 m en el ecuador, muy por debajo de la tolerancia
# de simplificacion (~0,0002 grados = 22 m), asi que no se pierde nada y se
# ahorran bytes frente a los 8-14 decimales que trae el archivo oficial.
DECIMALES = 5
OBJETIVO_PUNTOS = 3000
# 120 KB y no los 90 de antes: el indice del buscador paso de 331 entradas a
# 1.258 al sumarle los sectores catastrales que el gazetteer no tenia. La
# geometria de las 20 localidades no se movio.
PRESUPUESTO_BYTES = 120 * 1024
# Los barrios son 1.230 poligonos contra 20: su presupuesto es otro. No se
# cargan como capa dibujada —js/mapa.js los usa como datos para el hit-test y
# solo pinta el que se elige—, asi que lo que cuesta es el peso del archivo, no
# el DOM. 18.200 vertices dan ~455 KB; apretarlos mas empieza a mover los
# limites de barrios que miden tres manzanas, y el hit-test acertaria peor.
OBJETIVO_PUNTOS_BARRIOS = 26000
# ~490 KB de geometria mas ~110 KB de los campos n/c/bb de los 1.230 barrios.
# El archivo no bloquea nada: es local, se lee una vez y no toca el DOM.
PRESUPUESTO_BARRIOS = 900 * 1024
# Divisor de la simplificacion adaptativa: la tolerancia de cada barrio es su
# diagonal partida por esto, acotada entre TOL_BARRIO_MIN y TOL_BARRIO_MAX.
DIVISOR_BARRIO = 120
TOL_BARRIO_MIN = 0.00005
TOL_BARRIO_MAX = 0.0004
# Cuanto se le perdona a un sector que cae FUERA de las 20 localidades antes de
# darlo por no-Bogota. ~0,0045 grados son unos 500 m: de sobra para la costura
# entre el limite que publica IDECA y el que publica Datos Abiertos —el unico
# caso real es PARAMO II, a 97 m del borde de Chapinero— y muy poco para que se
# cuele un sector de Soacha o La Calera, que estan a kilometros.
TOLERANCIA_HUERFANO = 0.0045

# Nombres con tilde o enye que el gazetteer perdio al normalizarse. Solo los
# que de verdad cambian: el resto sale bien con capitalizacion automatica.
EXCEPCIONES = {
    "alamos": "Álamos", "alcala": "Alcalá", "alcazares": "Alcázares",
    "los alcazares": "Los Alcázares", "alfonso lopez": "Alfonso López",
    "batan": "Batán", "belen candelaria": "Belén (Candelaria)",
    "belen fontibon": "Belén (Fontibón)", "benjamin herrera": "Benjamín Herrera",
    "bosque calderon": "Bosque Calderón", "boyaca real": "Boyacá Real",
    "bravo paez": "Bravo Páez", "bosa san jose": "Bosa San José",
    "capellania": "Capellanía", "centro historico": "Centro Histórico",
    "chico": "Chicó", "chico norte": "Chicó Norte", "el chico": "El Chicó",
    "ciudad jardin": "Ciudad Jardín", "el campin": "El Campín",
    "el ensueno": "El Ensueño", "el liston": "El Listón",
    "el rincon": "El Rincón", "emaus": "Emaús", "entrerrios": "Entrerríos",
    "fatima": "Fátima", "fontibon centro": "Fontibón Centro",
    "galan": "Galán", "galerias": "Galerías", "garces navas": "Garcés Navas",
    "gran america": "Gran América", "hacienda el otono": "Hacienda El Otoño",
    "jerusalen": "Jerusalén", "jorge eliecer gaitan": "Jorge Eliécer Gaitán",
    "la pena": "La Peña", "la porciuncula": "La Porciúncula",
    "las americas": "Las Américas", "lujan": "Luján",
    "marco fidel suarez": "Marco Fidel Suárez", "mazuren": "Mazurén",
    "metropolis": "Metrópolis", "muequeta": "Muequetá", "muzu": "Muzú",
    "nicolas de federman": "Nicolás de Federmán", "normandia": "Normandía",
    "potosi": "Potosí", "salazar gomez": "Salazar Gómez",
    "san cristobal norte": "San Cristóbal Norte",
    "san cristobal sur": "San Cristóbal Sur",
    "san jose de bavaria": "San José de Bavaria", "san jose sur": "San José Sur",
    "san martin": "San Martín", "san pablo fontibon": "San Pablo (Fontibón)",
    "santa barbara": "Santa Bárbara",
    "serrania de los nogales": "Serranía de los Nogales",
    "toberin": "Toberín", "versalles fontibon": "Versalles (Fontibón)",
}

# Palabras que en un nombre propio van en minuscula, y numeros romanos que la
# capitalizacion automatica dejaria como "Xxiii".
MINUSCULAS = {"de", "del", "la", "las", "los", "el", "y", "en"}
ROMANOS = {"vi": "VI", "xii": "XII", "xxiii": "XXIII", "ii": "II", "iii": "III"}

# nombre normalizado -> nombre canonico con tildes, para los 20 oficiales.
CANON = {normalizar_texto(n): n for n in LOCALIDADES_BOGOTA}
CANON.update({
    "santafe": "Santa Fe", "candelaria": "La Candelaria",
    "martires": "Los Mártires", "rafael uribe": "Rafael Uribe Uribe",
})


def bonito(clave: str) -> str:
    """La clave del gazetteer, presentable. La busqueda NO usa esto."""
    if clave in CANON:
        return CANON[clave]
    if clave in EXCEPCIONES:
        return EXCEPCIONES[clave]
    palabras = []
    for i, p in enumerate(clave.split()):
        if p in ROMANOS:
            palabras.append(ROMANOS[p])
        elif p.isdigit():
            palabras.append(p)
        elif i > 0 and p in MINUSCULAS:
            palabras.append(p)
        else:
            palabras.append(p[:1].upper() + p[1:])
    return " ".join(palabras)


# ------------------------------------------------------------------ descarga

def descargar_sectores():
    """Los 1.231 sectores catastrales de IDECA, con cache en disco.

    SE CACHEA A PROPOSITO, igual que .cache_localidades.json: es medio mega de
    un servidor del Distrito que no siempre esta rapido, y regenerar el mapa
    por un cambio de nombres no tiene por que volver a pedirlo. Borrar
    `tools/.cache_barrios.json` fuerza la descarga.

    El servidor pagina de 1.000 en 1.000 (su `maxRecordCount`), asi que se pide
    con `resultOffset` hasta que deja de contestar features.
    """
    if os.path.isfile(CACHE_BARRIOS):
        with open(CACHE_BARRIOS, encoding="utf-8") as fh:
            guardado = json.load(fh)
        # Un cache de antes de que se pidiera SCATIPO no sirve: sin ese campo
        # no se puede separar la ciudad construida del paramo, y el encuadre
        # inicial saldria mal sin que nada falle a la vista.
        if guardado and "SCATIPO" in (guardado[0].get("attributes") or {}):
            return guardado

    import urllib.parse
    import urllib.request

    features = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            # SCATIPO separa los sectores urbanos (0) de los rurales: es lo
            # que define el encuadre inicial (ver `bbox` en main).
            "outFields": "SCACODIGO,SCANOMBRE,SCATIPO",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
            "resultOffset": str(offset),
            "resultRecordCount": str(SECTORES_PAGINA),
            # Simplificacion del lado del servidor: se traen ya los vertices
            # que caben en pantalla, no los del catastro.
            "maxAllowableOffset": str(SECTORES_OFFSET),
        }
        url = SECTORES_URL + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=180) as r:
            pagina = json.loads(r.read().decode("utf-8"))
        if pagina.get("error"):
            raise RuntimeError("IDECA respondio error: %s" % pagina["error"])
        trozo = pagina.get("features") or []
        features.extend(trozo)
        if len(trozo) < SECTORES_PAGINA:
            break
        offset += SECTORES_PAGINA

    # encoding EXPLICITO: SCANOMBRE trae enyes y en Windows el open() por
    # defecto escribe en cp1252, que luego no se puede releer como utf-8.
    with open(CACHE_BARRIOS, "w", encoding="utf-8") as fh:
        json.dump(features, fh, ensure_ascii=False)
    return features


def descargar_puntos_osm():
    """Los nodos `place=neighbourhood` con nombre dentro de OSM_BBOX, como
    [{"n": nombre, "lat": .., "lon": ..}]. Con cache en disco, como los
    sectores: borrar `tools/.cache_osm_barrios.json` fuerza la descarga.

    Overpass devuelve 429 (demasiadas peticiones) y 504 con frecuencia, y no
    por culpa nuestra: es un servicio publico compartido. Se reintenta con
    espera creciente y alternando espejos antes de rendirse.
    """
    if os.path.isfile(CACHE_OSM):
        with open(CACHE_OSM, encoding="utf-8") as fh:
            return json.load(fh)

    import time
    import urllib.error
    import urllib.parse
    import urllib.request

    consulta = (
        '[out:json][timeout:120][bbox:%s];'
        'node["place"="neighbourhood"]["name"];out;' % OSM_BBOX
    )
    datos = urllib.parse.urlencode({"data": consulta}).encode("utf-8")
    ultimo = None
    for intento in range(6):
        for url in OVERPASS_URLS:
            req = urllib.request.Request(
                url, data=datos,
                headers={"User-Agent": "machea-generar-mapa/1.0 (mapa de barrios de Bogota)"},
            )
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    respuesta = json.loads(r.read().decode("utf-8"))
                break
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                ultimo = e
                respuesta = None
                print("  overpass %s: %s" % (url.split('/')[2], e))
        if respuesta is not None:
            break
        time.sleep(10 * (intento + 1))
    else:
        raise RuntimeError("Overpass no respondio: %s" % ultimo)

    puntos = []
    for el in respuesta.get("elements") or []:
        nombre = (el.get("tags") or {}).get("name", "").strip()
        if not nombre or "lat" not in el:
            continue
        puntos.append({"n": nombre, "lat": el["lat"], "lon": el["lon"]})
    with open(CACHE_OSM, "w", encoding="utf-8") as fh:
        json.dump(puntos, fh, ensure_ascii=False)
    return puntos


# ---------------------------------------------------------------- geometria

def _dist2_a_segmento(p, a, b) -> float:
    """Distancia al cuadrado de p al segmento ab. Al cuadrado para no sacar
    raices dentro del bucle caliente de Douglas-Peucker."""
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return (px - ax) ** 2 + (py - ay) ** 2
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    qx, qy = ax + t * dx, ay + t * dy
    return (px - qx) ** 2 + (py - qy) ** 2


def simplificar(puntos, tolerancia):
    """Douglas-Peucker ITERATIVO. Iterativo y no recursivo a proposito: con
    16.053 puntos en un solo anillo (Santa Fe) la version recursiva puede
    llegar al limite de pila de Python."""
    n = len(puntos)
    if n < 4:
        return list(puntos)
    tol2 = tolerancia * tolerancia
    conservar = [False] * n
    conservar[0] = conservar[n - 1] = True
    pila = [(0, n - 1)]
    while pila:
        i, j = pila.pop()
        if j <= i + 1:
            continue
        peor, idx = -1.0, -1
        a, b = puntos[i], puntos[j]
        for k in range(i + 1, j):
            d = _dist2_a_segmento(puntos[k], a, b)
            if d > peor:
                peor, idx = d, k
        if peor > tol2:
            conservar[idx] = True
            pila.append((i, idx))
            pila.append((idx, j))
    return [puntos[k] for k in range(n) if conservar[k]]


def cerrar(anillo):
    """El primer punto y el ultimo tienen que coincidir: es lo que espera un
    <path> terminado en Z, y lo que asume el ray casting."""
    if len(anillo) >= 2 and anillo[0] != anillo[-1]:
        anillo = anillo + [anillo[0]]
    return anillo


def area_firmada(anillo) -> float:
    s = 0.0
    for i in range(len(anillo) - 1):
        x1, y1 = anillo[i]
        x2, y2 = anillo[i + 1]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def dentro(x, y, anillos) -> bool:
    """Even-odd sobre todos los anillos: el mismo criterio que usa
    `scraper_projects._punto_en_anillo` en su bucle, y el que hace que un punto
    del centro historico caiga en La Candelaria y no en Santa Fe."""
    d = False
    for anillo in anillos:
        if sp._punto_en_anillo(x, y, anillo):
            d = not d
    return d


def punto_interior(anillos):
    """Un punto garantizado DENTRO. El centroide no sirve solo: en localidades
    concavas (Suba, Usme) cae fuera. Si eso pasa, se corta el poligono con una
    horizontal y se toma el medio del tramo interior mas largo."""
    mayor = max(anillos, key=lambda a: abs(area_firmada(a)))
    cx = sum(p[0] for p in mayor[:-1]) / (len(mayor) - 1)
    cy = sum(p[1] for p in mayor[:-1]) / (len(mayor) - 1)
    if dentro(cx, cy, anillos):
        return cx, cy
    cortes = []
    for anillo in anillos:
        for i in range(len(anillo) - 1):
            x1, y1 = anillo[i]
            x2, y2 = anillo[i + 1]
            if (y1 > cy) != (y2 > cy):
                cortes.append(x1 + (cy - y1) * (x2 - x1) / (y2 - y1))
    cortes.sort()
    mejor, ancho = None, -1.0
    for i in range(0, len(cortes) - 1, 2):
        w = cortes[i + 1] - cortes[i]
        if w > ancho:
            ancho, mejor = w, (cortes[i] + cortes[i + 1]) / 2.0
    return (mejor, cy) if mejor is not None else (cx, cy)


def localidad_mas_cercana(x, y, originales_loc):
    """(id, distancia en grados) de la localidad cuyo borde pasa mas cerca de
    (x, y). Solo para sectores que no cayeron dentro de ninguna; ver el uso en
    `procesar_barrios`."""
    mejor_id, mejor_d = None, float("inf")
    for i, anillos in originales_loc.items():
        for anillo in anillos:
            for px, py in anillo:
                d = math.hypot(px - x, py - y)
                if d < mejor_d:
                    mejor_d, mejor_id = d, i
    return mejor_id, mejor_d


# ----------------------------------------------------------- celdas de barrio

# Un grado de longitud mide menos que uno de latitud: a la latitud de Bogota
# (4,6 N) la diferencia es del 0,3 %, pero las bisectrices se calculan en
# metros y no en grados para que la celda no salga sesgada.
COS_LAT = math.cos(math.radians(4.65))


def recortar_semiplano(anillo, p, q):
    """El trozo de `anillo` que queda mas cerca de `p` que de `q`
    (Sutherland-Hodgman contra la mediatriz de p y q). Vale para anillos
    concavos: puede devolver un anillo con aristas sobre la mediatriz, que es
    exactamente lo que se quiere pintar. Devuelve [] si no queda nada."""
    px, py = p[0] * COS_LAT, p[1]
    qx, qy = q[0] * COS_LAT, q[1]
    ax, ay = 2 * (qx - px), 2 * (qy - py)
    c = qx * qx + qy * qy - px * px - py * py

    def f(pt):
        return ax * pt[0] * COS_LAT + ay * pt[1] - c

    salida = []
    n = len(anillo) - 1  # cerrado: el ultimo repite al primero
    if n < 3:
        return []
    for i in range(n):
        a, b = anillo[i], anillo[i + 1]
        fa, fb = f(a), f(b)
        if fa <= 0:
            salida.append(a)
        if (fa <= 0) != (fb <= 0):
            t = fa / (fa - fb)
            salida.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    if len(salida) < 3:
        return []
    return cerrar(salida)


def partir_sector(anillos, puntos):
    """Las celdas de Voronoi de `puntos` recortadas al poligono `anillos`:
    una lista de anillos por punto, en el mismo orden. Una celda vacia (el
    punto quedo sin area tras recortar) sale como []."""
    celdas = []
    for i, p in enumerate(puntos):
        actuales = anillos
        for j, q in enumerate(puntos):
            if i == j:
                continue
            actuales = [r for r in (recortar_semiplano(a, p, q) for a in actuales) if len(r) >= 4]
            if not actuales:
                break
        celdas.append(actuales)
    return celdas


def procesar_barrios(originales_loc):
    """Los sectores catastrales, simplificados y repartidos por localidad.

    Devuelve `(por_localidad, sueltos, vertices, bbox_ciudad, huerfanos)`,
    donde `por_localidad` es {id: [ {n, c, bb, anillos} ]}, `sueltos` la lista
    de los que no cayeron en ninguna localidad, `bbox_ciudad` la extension de
    los sectores URBANOS (SCATIPO 0) —el encuadre con el que abre el mapa— y
    `huerfanos` los que se asignaron por cercania al no caer dentro de ninguna.

    LA LOCALIDAD SE DECIDE CON UN PUNTO INTERIOR, NO CON EL CENTROIDE. El
    centroide de un sector en forma de L cae fuera de el, y entonces se compara
    contra la localidad equivocada. `punto_interior` ya resuelve eso para las
    localidades concavas y aqui sirve igual.

    Y SE COMPARA CONTRA LOS ANILLOS ORIGINALES, no contra los simplificados:
    los limites simplificados se mueven hasta 33 m, y en un barrio pegado al
    borde eso alcanza para mandarlo a la localidad de al lado.
    """
    crudos = descargar_sectores()

    # LA TOLERANCIA ES DE CADA BARRIO, NO GLOBAL. Con las 20 localidades una
    # sola tolerancia servia porque todas son grandes; aqui conviven Cedritos
    # (1,4 km) con sectores rurales de Sumapaz de 20 km, y la tolerancia que
    # deja bien al rural borra al urbano. Se le da a cada uno su diagonal
    # partida por DIVISOR_BARRIO: los pequenos conservan el contorno y los
    # rurales —que son los que se comen los vertices— se aplanan.
    divisor = float(DIVISOR_BARRIO)
    while True:
        simples = []
        for f in crudos:
            anillos_o = f["geometry"]["rings"]
            xs = [pt[0] for r in anillos_o for pt in r]
            ys = [pt[1] for r in anillos_o for pt in r]
            diagonal = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
            tol = min(TOL_BARRIO_MAX, max(TOL_BARRIO_MIN, diagonal / divisor))
            anillos = [cerrar(simplificar([tuple(pt) for pt in r], tol))
                       for r in anillos_o]
            simples.append((f["attributes"], anillos))
        total = sum(len(r) for _, a in simples for r in a)
        if total <= OBJETIVO_PUNTOS_BARRIOS or divisor < 20:
            break
        divisor /= 1.4

    por_localidad = {}
    sueltos = []
    huerfanos = []
    for attrs, anillos in simples:
        nombre = (attrs.get("SCANOMBRE") or "").strip()
        if not nombre:
            continue
        # Un anillo de menos de 4 puntos no encierra nada: lo dejo fuera en vez
        # de emitir un poligono que el hit-test nunca podria acertar.
        anillos = [a for a in anillos if len(a) >= 4]
        if not anillos:
            sueltos.append((nombre, "sin area tras simplificar"))
            continue
        x, y = punto_interior(anillos)
        idx = None
        for i, rs in originales_loc.items():
            if dentro(x, y, rs):
                idx = i
                break
        if idx is None:
            # CAE EN LA GRIETA ENTRE LOS DOS DATASETS. Los sectores los publica
            # IDECA y los limites de localidad Datos Abiertos, y en el borde de
            # los cerros orientales no coinciden al metro: PARAMO II (rural, en
            # Chapinero, vecino de PARAMO I) queda 97 m por fuera de todas las
            # localidades y se caia del mapa entero.
            #
            # Se le asigna la localidad MAS CERCANA, y solo si el hueco es de
            # verdad un hueco de costura (TOLERANCIA_HUERFANO). Mas lejos que
            # eso ya no es desajuste de datasets sino un sector que no es de
            # Bogota, y ese si tiene que caerse y reportarse.
            idx, hueco = localidad_mas_cercana(x, y, originales_loc)
            if idx is None or hueco > TOLERANCIA_HUERFANO:
                sueltos.append((nombre, "punto interior fuera de las 20 localidades"))
                continue
            huerfanos.append((nombre, LOCALIDADES_BOGOTA[idx - 1], hueco * 111000))
        xs = [pt[0] for a in anillos for pt in a]
        ys = [pt[1] for a in anillos for pt in a]
        por_localidad.setdefault(idx, []).append({
            "n": bonito(normalizar_texto(nombre)),
            "c": normalizar_texto(nombre),
            "bb": [min(xs), min(ys), max(xs), max(ys)],
            "anillos": anillos,
        })

    # DOS SECTORES CON EL MISMO NOMBRE EN LA MISMA LOCALIDAD SON UNO SOLO para
    # quien busca: IDECA tiene dos "Tibabuyes" en Suba (codigos distintos) y
    # tres "Sierra Morena" en Ciudad Bolivar. Antes el buscador solo podia
    # llegar al primero; fusionados, el nombre pinta las dos partes.
    fusionados = 0
    for idx, lista in por_localidad.items():
        vistos = {}
        unicos = []
        for b in lista:
            previo = vistos.get(b["c"])
            if previo is None:
                vistos[b["c"]] = b
                unicos.append(b)
                continue
            previo["anillos"] = previo["anillos"] + b["anillos"]
            previo["bb"] = [min(previo["bb"][0], b["bb"][0]), min(previo["bb"][1], b["bb"][1]),
                            max(previo["bb"][2], b["bb"][2]), max(previo["bb"][3], b["bb"][3])]
            fusionados += 1
        por_localidad[idx] = unicos

    particion = partir_en_barrios(por_localidad)

    vertices = sum(len(r) for lista in por_localidad.values()
                   for b in lista for r in b["anillos"])

    # EL ENCUADRE INICIAL SALE DE LOS SECTORES URBANOS, no de los limites
    # administrativos. Bogota D.C. llega por el sur hasta el paramo: encuadrando
    # el limite oficial, la ciudad construida —donde estan los 96 proyectos—
    # ocupa el tercio de arriba y el resto es monte. Los 1.000 sectores con
    # SCATIPO 0 llegan hasta el casco urbano de Usme (lat 4,4685) en vez de
    # hasta 4,2697, y esa es la Bogota que la gente reconoce como Bogota.
    urbanos = [f for f in crudos if f["attributes"].get("SCATIPO") == 0]
    xs = [pt[0] for f in urbanos for r in f["geometry"]["rings"] for pt in r]
    ys = [pt[1] for f in urbanos for r in f["geometry"]["rings"] for pt in r]
    # Leaflet quiere [[lat_min, lon_min], [lat_max, lon_max]]: LATITUD PRIMERO.
    bbox_ciudad = [[min(ys), min(xs)], [max(ys), max(xs)]]

    particion["fusionados"] = fusionados
    return por_localidad, sueltos, vertices, bbox_ciudad, huerfanos, particion


def partir_en_barrios(por_localidad):
    """Parte cada sector catastral entre los barrios de OSM que caen dentro.
    MUTA `por_localidad`: los sectores con dos o mas puntos se reemplazan por
    sus celdas, en su sitio de la lista.

    Devuelve el resumen: {"alias": [(clave, idLoc, nombre, entrada)],
    "partidos": n, "celdas": n, "fuera": n, "repetidos": [..]}. `alias` son
    nombres que NO tienen entrada propia en la lista pero apuntan a una —el
    unico barrio de OSM de un sector que se quedo entero, o el nombre del
    sector cuando se partio y ninguna celda lo lleva— y van al buscador.

    LAS CELDAS SON APROXIMADAS, y se dice asi en el archivo generado: el
    contorno de cada barrio es la region del sector mas cercana a su punto de
    OSM que a los demas (Voronoi recortado). Es lo mas honesto que se puede
    dibujar sin un dataset de barrios, y deja a Cantalejo y a Gilmar como dos
    manchas distintas y contiguas, cada una donde esta.
    """
    puntos = descargar_puntos_osm()
    alias = []
    partidos = 0
    celdas_total = 0
    asignados = 0
    repetidos = []

    for idx, lista in por_localidad.items():
        nueva = []
        for b in lista:
            bb = b["bb"]
            dentro_del_sector = []
            for p in puntos:
                x, y = p["lon"], p["lat"]
                if x < bb[0] or x > bb[2] or y < bb[1] or y > bb[3]:
                    continue
                if not dentro(x, y, b["anillos"]):
                    continue
                clave = normalizar_texto(p["n"])
                if not clave:
                    continue
                # El mismo barrio dos veces en OSM (mismo nombre, o dos nodos
                # casi encima): se queda el primero.
                duplicado = False
                for otro in dentro_del_sector:
                    if otro["c"] == clave or math.hypot(otro["x"] - x, otro["y"] - y) < MINIMO_ENTRE_PUNTOS:
                        duplicado = True
                        break
                if duplicado:
                    continue
                dentro_del_sector.append({"c": clave, "n": p["n"], "x": x, "y": y})
            asignados += len(dentro_del_sector)

            if len(dentro_del_sector) < 2:
                nueva.append(b)
                if dentro_del_sector and dentro_del_sector[0]["c"] != b["c"]:
                    alias.append((dentro_del_sector[0]["c"], idx, dentro_del_sector[0]["n"], b))
                continue

            celdas = partir_sector(b["anillos"], [(p["x"], p["y"]) for p in dentro_del_sector])
            hechas = []
            for p, anillos in zip(dentro_del_sector, celdas):
                if not anillos:
                    continue
                xs = [pt[0] for a in anillos for pt in a]
                ys = [pt[1] for a in anillos for pt in a]
                hechas.append({
                    "n": p["n"], "c": p["c"],
                    "bb": [min(xs), min(ys), max(xs), max(ys)],
                    "anillos": anillos,
                    "s": b["c"],
                })
            if len(hechas) < 2:
                nueva.append(b)
                continue
            partidos += 1
            celdas_total += len(hechas)
            nueva.extend(hechas)
            # El nombre del sector sigue existiendo para quien lo escriba: si
            # ninguna celda lo lleva, apunta a la que contiene su punto interior.
            if not any(h["c"] == b["c"] for h in hechas):
                cx, cy = punto_interior(b["anillos"])
                destino = next((h for h in hechas if dentro(cx, cy, h["anillos"])), hechas[0])
                alias.append((b["c"], idx, b["n"], destino))

        # Dos celdas con el mismo nombre en la misma localidad (OSM repite
        # nombres en sectores distintos): la segunda dice de que sector es.
        vistos = {}
        for b in nueva:
            if b["c"] in vistos:
                repetidos.append((b["n"], LOCALIDADES_BOGOTA[idx - 1]))
                if b.get("s"):
                    b["n"] = "%s (%s)" % (b["n"], bonito(b["s"]))
            vistos[b["c"]] = True
        por_localidad[idx] = nueva

    return {
        "alias": alias, "partidos": partidos, "celdas": celdas_total,
        "fuera": len(puntos) - asignados, "repetidos": repetidos,
    }


# ------------------------------------------------------------------- salida

def fmt(v: float) -> str:
    s = ("%." + str(DECIMALES) + "f") % v
    s = s.rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def main() -> int:
    if not os.path.isfile(GEO):
        print("No encuentro %s" % GEO)
        return 1

    with open(GEO, encoding="utf-8") as fh:
        crudo = json.load(fh)

    originales = {}
    for f in crudo["features"]:
        idx = int(f["attributes"]["LocCodigo"])
        originales[idx] = [cerrar([tuple(p) for p in r]) for r in f["geometry"]["rings"]]

    faltan = [i for i in range(1, 21) if i not in originales]
    if faltan:
        print("Faltan localidades en el geojson: %s" % faltan)
        return 1

    crudos_totales = sum(len(r) for a in originales.values() for r in a)

    # Se sube la tolerancia hasta bajar del objetivo. Empieza fina para no
    # deformar de mas a las pequenas del centro.
    tolerancia = 0.00002
    while True:
        simples = {}
        for idx, anillos in originales.items():
            simples[idx] = [cerrar(simplificar(a, tolerancia)) for a in anillos]
        total = sum(len(r) for a in simples.values() for r in a)
        if total <= OBJETIVO_PUNTOS or tolerancia > 0.01:
            break
        tolerancia *= 1.6

    # Comprobacion: un punto interior del poligono SIMPLIFICADO tiene que
    # seguir cayendo dentro del ORIGINAL, y el area no puede irse mas de un
    # 2 %. Es lo que delata una simplificacion demasiado agresiva.
    fallos = []
    for idx, anillos in simples.items():
        x, y = punto_interior(anillos)
        if not dentro(x, y, originales[idx]):
            fallos.append((idx, "punto interior fuera del original"))
        a0 = abs(sum(area_firmada(r) for r in originales[idx]))
        a1 = abs(sum(area_firmada(r) for r in anillos))
        if a0 > 0 and abs(a1 - a0) / a0 > 0.02:
            fallos.append((idx, "area cambia %.1f %%" % (100 * abs(a1 - a0) / a0)))

    # EL ENCUADRE DE PANEO ES EL DISTRITO ENTERO, Sumapaz incluida. No es el
    # que abre —ese sale de los sectores urbanos, mas abajo— sino hasta donde
    # js/mapa.js deja pasear (`maxBounds`). Si el limite fuera el urbano,
    # Sumapaz quedaria dibujada pero inalcanzable.
    #
    # Leaflet quiere [[lat_min, lon_min], [lat_max, lon_max]]: LATITUD PRIMERO,
    # al reves que los pares de los anillos, que van [lon, lat] como en GeoJSON.
    xs_t = [p[0] for a in simples.values() for r in a for p in r]
    ys_t = [p[1] for a in simples.values() for r in a for p in r]
    bbox_distrito = [[min(ys_t), min(xs_t)], [max(ys_t), max(xs_t)]]

    # De mayor a menor area: en Leaflet el ultimo que se agrega queda encima,
    # asi que emitiendolas de grande a pequena las del centro (Candelaria,
    # Martires, Antonio Narino) reciben el clic y no la que las rodea.
    orden = sorted(simples, key=lambda i: -abs(sum(area_firmada(r) for r in simples[i])))

    def anillos_js(anillos):
        return "[" + ",".join(
            "[" + ",".join("[%s,%s]" % (fmt(x), fmt(y)) for x, y in r) + "]"
            for r in anillos
        ) + "]"

    filas = []
    for idx in orden:
        cx, cy = punto_interior(simples[idx])
        filas.append("{id:%d,nombre:%s,centro:[%s,%s],anillos:%s}" % (
            idx,
            json.dumps(LOCALIDADES_BOGOTA[idx - 1], ensure_ascii=False),
            fmt(cy), fmt(cx),
            anillos_js(simples[idx]),
        ))

    # LOS BARRIOS DEL MAPA. Se resuelven contra los anillos ORIGINALES de las
    # localidades, no contra los simplificados (ver procesar_barrios).
    barrios_geo, sueltos, vertices_b, bbox, huerfanos, particion = procesar_barrios(originales)

    # EL INDICE DEL BUSCADOR SALE DEL MAPA, no del gazetteer. Antes era al
    # reves —el gazetteer mandaba y el mapa completaba— y el resultado eran 123
    # nombres que se podian escribir pero no pintaban nada, porque no tenian
    # poligono. Ahora cada entrada lleva `bi`, la posicion del poligono exacto
    # dentro de su localidad, y solo entra al buscador lo que se puede pintar:
    #   1. cada poligono (sector entero o celda de barrio), uno por localidad;
    #   2. los alias: el barrio unico de un sector entero, o el nombre de un
    #      sector partido (ver `partir_en_barrios`);
    #   3. los 20 nombres oficiales de localidad (sin `bi`: pintan la localidad);
    #   4. lo del gazetteer que quede sin cubrir, solo si BARRIO_MANUAL lo
    #      cuelga de un poligono. El resto se descarta y se lista.
    # Se ordenan por clave mas larga primero: es la regla de
    # _GAZETTEER_ORDENADO, la que hace que "san cristobal norte" (Usaquen) le
    # gane a "san cristobal" (localidad 4), que es prefijo suyo.
    entradas = []          # (clave, idLoc, nombre, bi | None)
    cubiertos = {}         # (clave, idLoc) -> bi
    poligono_por_clave = {}  # (clave, idLoc) -> bi, incluye alias
    for idx, lista in barrios_geo.items():
        for bi, b in enumerate(lista):
            entradas.append((b["c"], idx, b["n"], bi))
            cubiertos.setdefault((b["c"], idx), bi)
            poligono_por_clave.setdefault((b["c"], idx), bi)
    for clave, idx, nombre, destino in particion["alias"]:
        if (clave, idx) in cubiertos:
            continue
        bi = next(i for i, b in enumerate(barrios_geo[idx]) if b is destino)
        entradas.append((clave, idx, nombre, bi))
        cubiertos[(clave, idx)] = bi
        poligono_por_clave[(clave, idx)] = bi
    for i, nombre in enumerate(LOCALIDADES_BOGOTA, start=1):
        clave = normalizar_texto(nombre)
        entradas.append((clave, i, nombre, None))
        cubiertos[(clave, i)] = None

    manuales = 0
    descartados = []
    discrepancias = []
    for clave, idx in sp._GAZETTEER.items():
        if (clave, idx) in cubiertos:
            continue
        if clave in CANON:
            continue
        destino = BARRIO_MANUAL.get(clave)
        if destino is not None:
            bi = poligono_por_clave.get((normalizar_texto(destino), idx))
            if bi is None:
                descartados.append((clave, LOCALIDADES_BOGOTA[idx - 1], "BARRIO_MANUAL apunta a %r, que no existe ahi" % destino))
                continue
            entradas.append((clave, idx, bonito(clave), bi))
            cubiertos[(clave, idx)] = bi
            manuales += 1
            continue
        en_otra = [LOCALIDADES_BOGOTA[j - 1] for (c, j) in cubiertos if c == clave and j != idx]
        if en_otra:
            discrepancias.append((clave, LOCALIDADES_BOGOTA[idx - 1], en_otra))
            continue
        descartados.append((clave, LOCALIDADES_BOGOTA[idx - 1], "sin poligono ni punto en OSM"))

    barrios = sorted(entradas, key=lambda e: (-len(e[0]), e[0], e[1]))
    filas_b = []
    for clave, idx, nombre, bi in barrios:
        fila = "[%s,%d,%s" % (json.dumps(clave, ensure_ascii=False), idx, json.dumps(nombre, ensure_ascii=False))
        filas_b.append(fila + ("]" if bi is None else ",%d]" % bi))

    cabecera = (
        "// GENERADO POR tools/generar_mapa.py - NO EDITAR A MANO.\n"
        "//\n"
        "// GDF_MAPA.localidades: las 20 localidades como anillos [lon, lat],\n"
        "// listos para L.geoJSON (ver js/mapa.js). Van de mayor a menor area\n"
        "// porque en Leaflet el ultimo que se agrega queda ENCIMA: asi las\n"
        "// pequenas del centro reciben el clic y no la que las rodea.\n"
        "//\n"
        "// Santa Fe (3) trae DOS anillos. El segundo es La Candelaria, que es un\n"
        "// enclave dentro suyo: en GeoJSON eso es un agujero y Leaflet lo respeta\n"
        "// solo, asi que La Candelaria queda clicable sin trucos.\n"
        "//\n"
        "// `centro` es un punto GARANTIZADO dentro de la localidad (el centroide\n"
        "// no vale: en las concavas como Suba o Usme cae fuera). Se usa para\n"
        "// centrar el mapa cuando alguien elige un barrio en el buscador.\n"
        "//\n"
        "// `bbox` es el encuadre inicial: la BOGOTA CONSTRUIDA, la extension de\n"
        "// los sectores catastrales urbanos. No son los limites del Distrito, que\n"
        "// bajan hasta el paramo de Sumapaz: encuadrando esos, la ciudad —donde\n"
        "// estan los 96 proyectos— abriria ocupando el tercio de arriba.\n"
        "// `bboxDistrito` si son los limites completos, y es hasta donde\n"
        "// js/mapa.js deja pasear el mapa.\n"
        "//\n"
        "// GDF_BARRIOS: [clave normalizada, id de localidad, nombre, bi].\n"
        "// `bi` es la posicion del poligono EXACTO dentro de la lista de su\n"
        "// localidad en GDF_BARRIOS_GEO (js/mapa_barrios.js): es lo que pinta el\n"
        "// buscador. Solo los 20 nombres de localidad van sin `bi`. Todo lo que\n"
        "// esta aqui pinta algo; lo que no tenia poligono se quedo fuera.\n"
        "// Ordenado de clave mas larga a mas corta, como _GAZETTEER_ORDENADO.\n"
        "//\n"
        "// Origen: datos/localidades_bogota.json, sectores catastrales de IDECA y\n"
        "// puntos de barrio de OpenStreetMap (c) OpenStreetMap contributors, ODbL.\n"
        "// %d vertices -> %d (tolerancia %.5f grados).\n"
    ) % (crudos_totales, sum(len(r) for a in simples.values() for r in a), tolerancia)

    js = (
        cabecera
        + "window.GDF_MAPA = {\n"
        + "  bbox: [[%s,%s],[%s,%s]],\n" % (
            fmt(bbox[0][0]), fmt(bbox[0][1]), fmt(bbox[1][0]), fmt(bbox[1][1]))
        + "  bboxDistrito: [[%s,%s],[%s,%s]],\n" % (
            fmt(bbox_distrito[0][0]), fmt(bbox_distrito[0][1]),
            fmt(bbox_distrito[1][0]), fmt(bbox_distrito[1][1]))
        + "  localidades: [\n    "
        + ",\n    ".join(filas)
        + "\n  ]\n};\n"
        + "window.GDF_BARRIOS = [\n  "
        + ",\n  ".join(filas_b)
        + "\n];\n"
    )

    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(js)

    # ------------------------------------------------- js/mapa_barrios.js
    # INDEXADO POR LOCALIDAD a proposito. js/mapa.js ya sabe en que localidad
    # cayo el clic —se lo dice la capa de localidades, que es la autoritativa—,
    # asi que el hit-test solo mira los barrios de esa localidad: 8 en La
    # Candelaria, 134 en Ciudad Bolivar, nunca los 1.230 de golpe.
    cab_b = (
        "// GENERADO POR tools/generar_mapa.py - NO EDITAR A MANO.\n"
        "//\n"
        "// Los barrios de Bogota, agrupados por id de localidad 1..20:\n"
        "//\n"
        "//   n   nombre presentable      c   clave normalizada, cruza con GDF_BARRIOS\n"
        "//   bb  [minLon,minLat,maxLon,maxLat]    a   anillos [lon, lat], como GDF_MAPA\n"
        "//   s   (solo celdas) clave del sector catastral del que sale la celda\n"
        "//\n"
        "// DE DONDE SALE CADA CONTORNO. La base son los sectores catastrales de\n"
        "// IDECA (capa 37 del Mapa de Referencia). Un sector suele contener\n"
        "// varios barrios y ninguna fuente publica tiene el contorno de esos\n"
        "// barrios, asi que cada sector se PARTE entre los barrios que\n"
        "// OpenStreetMap ubica dentro (nodos place=neighbourhood): la celda de\n"
        "// un barrio es la region del sector mas cercana a su punto que a los\n"
        "// demas (Voronoi recortado al sector). Son APROXIMADAS: el borde\n"
        "// entre dos barrios del mismo sector es una mediatriz, no una calle.\n"
        "// Los sectores con cero o un barrio dentro quedan enteros.\n"
        "// Datos de OSM (c) OpenStreetMap contributors, ODbL.\n"
        "//\n"
        "// ESTO NO ES UNA CAPA DIBUJADA. js/mapa.js lo usa como datos para el\n"
        "// hit-test del clic y solo pinta DOS poligonos: el que esta bajo el\n"
        "// cursor y el elegido. Mil doscientos paths en el DOM dejarian el\n"
        "// mapa inusable en movil.\n"
        "//\n"
        "// `bb` esta para descartar por rectangulo antes del ray casting.\n"
        "//\n"
        "// %d barrios en %d localidades - %d vertices.\n"
    ) % (sum(len(v) for v in barrios_geo.values()), len(barrios_geo), vertices_b)

    trozos = []
    for idx in sorted(barrios_geo):
        uno = ",".join(
            "{n:%s,c:%s,bb:[%s,%s,%s,%s],%sa:%s}" % (
                json.dumps(b["n"], ensure_ascii=False),
                json.dumps(b["c"], ensure_ascii=False),
                fmt(b["bb"][0]), fmt(b["bb"][1]), fmt(b["bb"][2]), fmt(b["bb"][3]),
                ("s:%s," % json.dumps(b["s"], ensure_ascii=False)) if b.get("s") else "",
                anillos_js(b["anillos"]),
            )
            for b in barrios_geo[idx]
        )
        trozos.append("  %d: [%s]" % (idx, uno))
    js_b = cab_b + "window.GDF_BARRIOS_GEO = {\n" + ",\n".join(trozos) + "\n};\n"

    with open(SALIDA_BARRIOS, "w", encoding="utf-8") as fh:
        fh.write(js_b)

    peso = os.path.getsize(SALIDA)
    peso_b = os.path.getsize(SALIDA_BARRIOS)
    print("localidades : %d (Sumapaz dibujada, fuera del encuadre inicial)" % len(simples))
    print("vertices    : %d -> %d  (tolerancia %.5f grados)"
          % (crudos_totales, sum(len(r) for a in simples.values() for r in a), tolerancia))
    print("buscador    : %d entradas  (%d poligonos + %d alias + 20 localidades"
          " + %d manuales del gazetteer)"
          % (len(barrios), sum(len(v) for v in barrios_geo.values()),
             len(particion["alias"]), manuales))
    print("barrios     : %d poligonos en %d localidades, %d vertices"
          % (sum(len(v) for v in barrios_geo.values()), len(barrios_geo), vertices_b))
    print("celdas      : %d sectores partidos en %d celdas de barrio (OSM);"
          " %d sectores fusionados por nombre; %d puntos de OSM fuera de todo sector"
          % (particion["partidos"], particion["celdas"], particion["fusionados"], particion["fuera"]))
    if particion["repetidos"]:
        print("nombres repetidos dentro de una localidad (la celda dice su sector): %d"
              % len(particion["repetidos"]))
        for nombre, loc in particion["repetidos"][:10]:
            print("   %-32s %s" % (nombre[:32], loc))
    if discrepancias:
        print("gazetteer vs mapa: %d nombres que el gazetteer pone en una localidad"
              " y el mapa tiene en otra (manda el mapa)" % len(discrepancias))
        for clave, loc, otras in discrepancias:
            print("   %-32s gazetteer: %-18s mapa: %s" % (clave[:32], loc, ", ".join(otras)))
    if descartados:
        print("descartados del buscador (sin poligono; ver BARRIO_MANUAL): %d" % len(descartados))
        for clave, loc, motivo in descartados:
            print("   %-32s %-18s %s" % (clave[:32], loc, motivo))
    for i in sorted(barrios_geo, key=lambda k: -len(barrios_geo[k]))[:3]:
        print("              %-20s %d" % (LOCALIDADES_BOGOTA[i - 1], len(barrios_geo[i])))
    print("bbox ciudad : lat %s..%s  lon %s..%s  (sectores urbanos)"
          % (fmt(bbox[0][0]), fmt(bbox[1][0]), fmt(bbox[0][1]), fmt(bbox[1][1])))
    print("bbox paneo  : lat %s..%s  lon %s..%s  (Distrito con Sumapaz)"
          % (fmt(bbox_distrito[0][0]), fmt(bbox_distrito[1][0]),
             fmt(bbox_distrito[0][1]), fmt(bbox_distrito[1][1])))
    print("salida      : %s" % os.path.relpath(SALIDA, RAIZ))
    print("peso        : %.1f KB  (presupuesto %d KB)" % (peso / 1024.0, PRESUPUESTO_BYTES // 1024))
    print("peso barrios: %.1f KB  (presupuesto %d KB)  %s"
          % (peso_b / 1024.0, PRESUPUESTO_BARRIOS // 1024,
             os.path.relpath(SALIDA_BARRIOS, RAIZ)))
    # Nada se cae en silencio: si un sector no encontro localidad, se nombra.
    if sueltos:
        print("sectores sin localidad: %d" % len(sueltos))
        for nombre, motivo in sueltos[:10]:
            print("   %-32s %s" % (nombre[:32], motivo))
    # Tampoco se cae en silencio lo que se rescato por cercania: se dice cual,
    # a que localidad fue a parar y a cuantos metros del borde estaba.
    if huerfanos:
        print("sectores asignados por cercania: %d" % len(huerfanos))
        for nombre, loc, metros in huerfanos:
            print("   %-32s -> %-20s a %.0f m del borde" % (nombre[:32], loc, metros))
    if fallos:
        print("VERIFICACION: %d problemas" % len(fallos))
        for idx, msg in fallos:
            print("   %-20s %s" % (LOCALIDADES_BOGOTA[idx - 1], msg))
    else:
        print("verificacion: OK - los 20 puntos interiores caen dentro del original")
    if peso > PRESUPUESTO_BYTES or peso_b > PRESUPUESTO_BARRIOS:
        print("AVISO: pasa del presupuesto de peso.")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
