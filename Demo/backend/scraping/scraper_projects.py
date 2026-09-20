"""
scraper_projects.py
===================
Catálogo de proyectos de vivienda de Bogotá D.C. para el recomendador Leadify.

Hace tres cosas, en este orden:

1. **Asignación de localidad por dirección** (`asignar_localidades`): recibe el
   JSON de proyectos, lee la dirección de cada uno y le agrega el atributo
   `Localidad` (id 1..20). Es la pieza que conecta el catálogo con el grafo de
   proximidad de `catalogos.py`.
2. **Scraping** de las cuatro constructoras (Amarilo, Cusezar, Constructora
   Bolívar y Colsubsidio), normalizando cada ficha al contrato JSON del modelo.
3. **Descarga de imágenes** a `imagenes_proyectos/<id_proyecto>/`.

Uso:

    python scraper_projects.py                    # scraping + localidades + imágenes
    python scraper_projects.py --no-imagenes      # solo el JSON
    python scraper_projects.py --fuente amarilo cusezar
    python scraper_projects.py --salida otro_catalogo.json

Las cuatro webs cargan sus proyectos por JavaScript, así que ninguna se puede
leer del HTML plano de la página de listado. En vez de montar un navegador
headless se usa la misma fuente de datos que consume el front de cada sitio,
que además llega ya estructurada:

    Amarilo      -> API interna  https://apiweb.amarilo.com.co/search/v1/proyecto
    Cusezar      -> HTML del listado (sí trae las tarjetas) + ficha por proyecto
    Bolívar      -> API interna  /api/proyectos-vivienda/{ciudad}/all/all/all/all
                    + JSON-LD ApartmentComplex de cada ficha
    Colsubsidio  -> sitemap + __NEXT_DATA__ de cada ficha (su JSON:API pide auth)

El vocabulario de localidades y zonas comunes NO se redefine aquí: se importa
de `catalogos.py`, que es el único lugar donde viven los ids que viajan hasta
`modelo.py`. Si cada módulo tuviera su copia, un desfase de un índice cruzaría
mal las preferencias del usuario sin que nada fallara de forma visible.

Dependencias: requests, beautifulsoup4, lxml.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Ejecutable por ruta (`python scraping/scraper_projects.py`) o como módulo
# (`python -m scraping.scraper_projects`): en el primer caso Python pone en el path esta
# carpeta y no `backend/`, así que el paquete `Model` no se encontraría.
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Model.catalogos import (
    LOCALIDADES_BOGOTA,
    ZONAS_COMUNES,
    codigo_tipo_vivienda,
    distancia_localidades,
    indice_localidad,
    indice_zona,
    nombre_localidad,
    normalizar_texto,
)

# El barrio se resuelve DESPUÉS de la localidad y nunca la contradice: el
# grafo de barrios (Model/grafo_barrios.py) afina la posición dentro de la
# localidad ya asignada. Ver `asignar_barrios`.
from Model.grafo_barrios import (
    barrio_desde_coordenadas,
    barrio_desde_direccion,
    hay_grafo_barrios,
)

try:  # el aviso de TLS sin verificar se emite una sola vez; ver `_get`
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:  # pragma: no cover - urllib3 viene con requests
    urllib3 = None

# El catálogo y los límites oficiales son datos de entrada del modelo, así que
# viven en `Model/data_projects/`. Las imágenes NO: son binarios pesados que
# sirve el front, y por eso van a sus recursos, con el id del proyecto como
# nombre de carpeta. Todo eso lo declara `Model/rutas.py`.
from Model.rutas import (
    DIR_DATA_PROJECTS as DIR_DATOS,
    DIR_IMAGENES,
    RUTA_CATALOGO as RUTA_SALIDA,
    RUTA_LOCALIDADES_GEO,
)

# Límites oficiales de las 20 localidades (Datos Abiertos Bogotá). Se usan solo
# como verificación cuando la fuente publica coordenadas; ver asignar_localidades.
URL_LOCALIDADES_GEO = (
    "https://datosabiertos.bogota.gov.co/dataset/856cb657-8ca3-4ee8-857f-37211173b1f8/"
    "resource/497b8756-0927-4aee-8da9-ca4e32ca3a8a/download/loca.json"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT = 45
REINTENTOS = 4
ESPERA_REINTENTO = 1.5   # segundos, se duplica en cada intento

# Hilos para bajar fichas de detalle. Colsubsidio sirve páginas de ~1,7 MB y
# corta conexiones cuando se le piden muchas a la vez: con 6 hilos se caían
# 12 de 29 fichas y el proyecto quedaba sin dirección. Se baja por fuente en
# lugar de globalmente para no penalizar a las otras tres.
HILOS = 6
HILOS_POR_FUENTE = {"colsubsidio": 3}

# Piso: el formulario lo captura como preferencia del usuario (0 bajo, 1 medio,
# 3 alto, 4 sin preferencia). Un proyecto no tiene "un piso", tiene torres de
# muchos, así que se emite 4 = sin preferencia, el mismo valor neutro que
# modelo.py asume cuando el dato no viene.
PISO_SIN_PREFERENCIA = 4


# ===========================================================================
# A. Zonas comunes: alias observados en estas cuatro webs
#
# catalogos.indice_zona ya resuelve el vocabulario canónico y los alias del
# seed original. Aquí solo se añaden las etiquetas que publican Amarilo,
# Cusezar, Bolívar y Colsubsidio y que aquel no conoce. Se resuelven de forma
# explícita, nunca por parecido: una amenidad desconocida se reporta en
# zonas_comunes_no_mapeadas en lugar de forzarla a una categoría ajena
# ("Cuarto de residuos" o "Subestación eléctrica" no son ninguna de las 25).
# ===========================================================================
_ALIAS_EXTRA = {
    # Lobby / acceso
    "lobby doble altura": 0, "recepcion": 0, "porteria": 0, "hall de acceso": 0,
    "porteria de control vehicular y peatonal": 0, "porteria y recepcion": 0,
    # Piscina
    "piscina adultos": 1, "piscina ninos": 1, "piscina semiolimpica": 1,
    "piscina cubierta": 1, "jacuzzi": 1,
    # Lavandería
    "zona de ropas": 2, "zona de lavanderia comunal": 2, "lavanderia comunal": 2,
    # BBQ
    "terraza bbq": 3, "zona asados": 3, "asadores": 3, "zona bbq y terraza": 3,
    # Mascotas
    "zona de mascotas": 4, "pet friendly": 4, "zona pet friendly": 4,
    "parque para mascotas": 4, "pet park": 4, "zona canina": 4,
    # Niños
    "zona de ninos": 5, "zona infantil": 5, "parque infantil": 5,
    "juegos infantiles": 5, "salon de ninos": 5, "ludoteca": 5, "guarderia": 5,
    "zona de juegos infantiles": 5,
    # Comercio
    "comercio": 6, "zona comercial": 6, "local comercial": 6,
    # Fitness / gimnasio
    "zona de fitness": 7, "aerobicos": 7, "aerobics": 7, "zona crossfit": 7,
    "salon de aerobicos": 7, "zona biosaludable": 7, "gimnasio al aire libre": 7,
    "gimnasio privado": 15, "gimnasio equipado": 15,
    # Salón social
    "salones sociales": 8, "salon de eventos": 8, "salon multiple": 8,
    "salon de reuniones": 8, "zona social": 8, "salon social y terraza": 8,
    "oficinas de administracion": 8,
    # Spa mascotas
    "spa para mascotas": 9, "lavado de mascotas": 9,
    # Zona cool / terraza
    "terraza": 10, "terraza social": 10, "rooftop": 10, "mirador": 10,
    "solarium": 10, "cubierta": 10, "zona chimenea": 10, "area de chimenea": 10,
    "chimenea": 10,
    # Cine
    "sala de cine": 11, "cinema": 11, "teatrino": 11,
    # Coworking
    "zona coworking": 12, "espacio coworking": 12, "sala de estudio": 12,
    "zona de estudio": 12, "business center": 12, "cafe coworking": 12,
    # Sala VIP
    "sala premium": 13, "lounge": 13, "salon vip": 13,
    # Café
    "zona de cafe": 14, "cafe": 14, "cafeteria": 14, "bar": 14,
    # Parqueadero
    "parqueadero visitantes": 16, "parqueadero de visitantes": 16,
    "parqueaderos privados para residentes": 16, "parqueadero cubierto": 16,
    "parqueaderos comunales para visitantes": 16, "bicicleteros": 16,
    "parqueadero bicicletas": 16, "biciparqueadero": 16,
    # Zona verde
    "jardines": 17, "huerta": 17, "huerta urbana": 17, "zona ecologica": 17,
    "senderos peatonales": 17, "alameda": 17, "zonas verdes y senderos": 17,
    # Parque
    "plazoleta": 18, "plaza": 18, "plazoletas": 18,
    # Sala de juegos
    "sala de juegos": 19, "juegos de mesa": 19, "mesa de ping pong": 19,
    "billar": 19, "salon de juegos infantiles": 19,
    # Trote / deporte
    "trotadero": 20, "cancha multiple": 20, "cancha multiproposito": 20,
    "canchas deportivas": 20, "zona deportiva": 20, "cancha sintetica": 20,
    "sendero de trote": 20,
    # Voleibol
    "cancha de voleibol": 21, "voleibol": 21,
    # Pádel
    "cancha de squash": 22, "squash": 22, "cancha de tenis": 22, "tenis": 22,
    # Bicicletas
    "zona de bicicletas": 23, "taller bici": 23,
    # Sauna
    "turco": 24, "sauna y turco": 24, "spa": 24, "zona humeda": 24,
    "zonas humedas": 24,
    # --- variantes observadas al revisar el catálogo ya construido ---
    "zona para mascotas": 4, "salon infantil": 5, "triciclodromo": 5,
    "piscina para adultos": 1, "piscina para ninos": 1,
    "gimnasio biosaludable": 7, "juegos biosaludables": 7, "zona de yoga": 7,
    "gimnasio semidotado": 15, "gimnasio dotado": 15,
    "porteria con lobby": 0, "porteria tipo lobby a doble altura": 0,
    "porteria recepcion": 0, "lobby recepcion": 0, "porteria doble altura": 0,
    "social kitchen": 14, "cocina social": 14,
    "cancha multiple no reglamentaria": 20, "plazoleta de ping pong": 19,
    "terraza transitable": 10, "fogata": 10, "zona de fogata": 10,
    "social spot": 10, "terraza 360": 10,
    "sala de reuniones": 12, "work and chill": 12, "zona de trabajo": 12,
    "salas premium": 13, "parqueadero de bicicletas": 16,
    "lavanderia comunal": 2, "zona de lavanderia": 2,
}


def mapear_zonas_comunes(etiquetas):
    """Traduce etiquetas crudas de cualquiera de las cuatro webs al vocabulario
    canónico de 25 zonas comunes.

    Returns:
        (nombres_canonicos, indices, no_mapeadas)
    """
    if not etiquetas:
        return [], [], []
    if isinstance(etiquetas, str):
        etiquetas = [p for p in re.split(r"[,\n;]", etiquetas) if p.strip()]

    indices, no_mapeadas = set(), []
    for cruda in etiquetas:
        texto = normalizar_texto(cruda)
        if not texto:
            continue
        idx = indice_zona(texto)
        if idx is None:
            idx = _ALIAS_EXTRA.get(texto)
        if idx is None:
            # Las webs anteponen artículos sin criterio ("Las zonas verdes").
            reducido = re.sub(r"^(el|la|los|las|de|del)\s+", "", texto)
            idx = indice_zona(reducido)
            if idx is None:
                idx = _ALIAS_EXTRA.get(reducido)
        if idx is None:
            no_mapeadas.append(str(cruda).strip())
        else:
            indices.add(idx)

    indices = sorted(indices)
    return [ZONAS_COMUNES[i] for i in indices], indices, sorted(set(no_mapeadas))


# ===========================================================================
# B. Localidad a partir de la dirección
#
# Este es el punto 2 del encargo y la pieza de la que depende todo el grafo de
# proximidad: si la localidad sale mal, el BFS de primer_filtro expande hacia
# vecinas equivocadas y el Top 6 completo queda sesgado.
#
# Se resuelve en tres pasadas, de más a menos confiable, y cada proyecto queda
# marcado con la pasada que lo resolvió para poder auditar el catálogo:
#
#   alta   -> la dirección nombra la localidad ("Bosa, Bogotá", "localidad de Suba")
#   media  -> la dirección nombra un barrio/sector del gazetteer ("La Colina")
#   baja   -> solo se pudo inferir por la malla vial (calle/carrera)
#
# La malla vial de Bogotá es regular y eso la hace utilizable como último
# recurso: las calles crecen hacia el norte (y hacia el sur con el sufijo
# "Sur") y las carreras crecen hacia el occidente (y hacia el oriente con
# "Este"). Traducir esos dos números a una localidad es aproximado, nunca
# exacto, por eso queda marcado como confianza baja y no pisa a las otras dos.
# ===========================================================================

# Municipios que NO son Bogotá D.C. Aparecen mezclados en los listados de
# Cusezar y Bolívar, que filtran por área metropolitana y no por ciudad.
_FUERA_DE_BOGOTA = {
    "soacha", "chia", "cajica", "mosquera", "funza", "madrid", "la calera",
    "zipaquira", "tocancipa", "cota", "ubate", "villeta", "fusagasuga",
    "girardot", "ricaurte", "sopo", "tabio", "tenjo", "sibate", "facatativa",
    "guasca", "gachancipa", "cali", "cartagena", "medellin", "barranquilla",
    "villavicencio", "ibague", "valledupar", "pereira", "santa marta",
    "soledad", "puerto colombia", "restrepo", "armenia", "rionegro",
    "bucaramanga", "monteria", "neiva", "panama",
}

# Barrio / sector / UPZ -> id de localidad. Es un gazetteer explícito: solo
# entra lo que se puede afirmar. Los nombres que una misma etiqueta tiene en
# dos localidades (p. ej. "Claret", en Tunjuelito y en Rafael Uribe) se dejan
# fuera a propósito: es preferible caer a la malla vial que resolver mal con
# aire de certeza.
_GAZETTEER = {
    # 1 Usaquén
    # "Unicentro" queda fuera a propósito: hay uno en Usaquén y otro de
    # Occidente en Engativá, y Colsubsidio usa el segundo como referencia.
    "usaquen": 1, "santa barbara": 1, "cedritos": 1,
    "country club": 1, "la carolina": 1, "toberin": 1, "verbenal": 1,
    "san cristobal norte": 1, "la uribe": 1, "el contador": 1,
    "bella suiza": 1, "santa ana": 1, "chico norte": 1, "barrancas": 1,
    "el codito": 1, "pepe sierra": 1, "la calleja": 1, "san patricio": 1,
    "los cedros": 1, "el redil": 1,
    # 2 Chapinero
    "chapinero": 2, "chapinero alto": 2, "chapinero central": 2,
    "el chico": 2, "chico": 2, "el retiro": 2, "zona rosa": 2, "zona g": 2,
    "quinta camacho": 2, "la cabrera": 2, "rosales": 2, "los rosales": 2,
    "el nogal": 2, "pardo rubio": 2, "san isidro": 2, "juan xxiii": 2,
    "marly": 2, "el virrey": 2, "antiguo country": 2, "la porciuncula": 2,
    "bosque calderon": 2, "las acacias": 2, "granada norte": 2,
    "serrania de los nogales": 2, "emaus": 2, "la salle": 2,
    # 3 Santa Fe
    "santa fe": 3, "santafe": 3, "la macarena": 3, "las nieves": 3,
    "las cruces": 3, "san diego": 3, "bosque izquierdo": 3, "monserrate": 3,
    "la alameda": 3, "parque nacional": 3, "san martin": 3, "veracruz": 3,
    "samper": 3, "la pena": 3,
    # 4 San Cristóbal
    "san cristobal": 4, "san cristobal sur": 4, "20 de julio": 4,
    "veinte de julio": 4, "la victoria": 4, "la gloria": 4,
    "los libertadores": 4, "sosiego": 4, "san blas": 4, "altamira": 4,
    "juan rey": 4, "la belleza": 4, "vitelma": 4,
    # 5 Usme
    "usme": 5, "portal de usme": 5, "gran yomasa": 5, "comuneros": 5,
    "alfonso lopez": 5, "danubio": 5, "ciudad usme": 5, "monteblanco": 5,
    "santa librada": 5, "la marichuela": 5, "marichuela": 5, "tocaimita": 5,
    "tres quebradas": 5, "la requilina": 5,
    # 6 Tunjuelito
    "tunjuelito": 6, "venecia": 6, "isla del sol": 6, "abraham lincoln": 6,
    "ontario": 6, "fatima": 6, "san benito": 6, "el tunal": 6, "tunal": 6,
    # 7 Bosa
    "bosa": 7, "bosa recreo": 7, "el recreo": 7, "bosa central": 7,
    "bosa occidental": 7, "bosa san jose": 7, "bosa porvenir": 7,
    "el porvenir": 7, "tintal sur": 7, "apogeo": 7, "la marlene": 7,
    "san bernardino": 7, "san pablo bosa": 7, "piamonte": 7,
    "brasilia bosa": 7, "bosa nova": 7,
    # 8 Kennedy
    "kennedy": 8, "kennedy central": 8, "timiza": 8, "castilla": 8,
    "banderas": 8, "tintal": 8, "ciudad tintal": 8, "patio bonito": 8,
    "corabastos": 8, "carvajal": 8, "las americas": 8, "mandalay": 8,
    "marsella": 8, "techo": 8, "calandaima": 8, "bavaria": 8,
    "gran britalia": 8, "villa alsacia": 8, "hipotecho": 8, "provivienda": 8,
    "pio xii": 8, "el tintal": 8,
    # 9 Fontibón
    "fontibon": 9, "modelia": 9, "la felicidad": 9, "hayuelos": 9,
    "capellania": 9, "ciudad salitre occidente": 9, "salitre occidental": 9,
    "zona franca": 9, "fontibon centro": 9, "san pablo fontibon": 9,
    "atahualpa": 9, "belen fontibon": 9, "montevideo": 9, "puerta de teja": 9,
    "versalles fontibon": 9, "ferrocaja": 9,
    # 10 Engativá
    "engativa": 10, "normandia": 10, "alamos": 10, "boyaca real": 10,
    "santa helenita": 10, "la granja": 10, "minuto de dios": 10,
    "el minuto de dios": 10, "ciudadela colsubsidio": 10, "quirigua": 10,
    "garces navas": 10, "bolivia": 10, "villa luz": 10, "florencia": 10,
    "tabora": 10, "san marcos": 10, "las ferias": 10, "lujan": 10,
    "villas de granada": 10, "el dorado industrial": 10, "palo blanco": 10,
    # 11 Suba
    "suba": 11, "la colina": 11, "colina campestre": 11, "niza": 11,
    "iberia": 11, "prado veraniego": 11, "mazuren": 11, "gratamira": 11,
    "san jose de bavaria": 11, "britalia norte": 11, "pontevedra": 11,
    "puente largo": 11, "batan": 11, "julio flores": 11, "lisboa": 11,
    "tibabuyes": 11, "el rincon": 11, "aures": 11, "villa elisa": 11,
    "casablanca suba": 11, "la alhambra": 11, "cantalejo": 11,
    "tuna alta": 11, "guaymaral": 11, "arrayanes": 11, "la floresta": 11,
    "floresta": 11, "salitre norte": 11, "villa del prado": 11,
    # Lagos de Torca y sus desarrollos quedan al occidente de la Autopista
    # Norte, del lado de Suba, aunque el plan parcial se anuncie como "norte".
    "lagos de torca": 11, "hacienda el bosque": 11, "hacienda el otono": 11,
    "tramonte": 11, "torca": 11,
    # 12 Barrios Unidos
    "barrios unidos": 12, "doce de octubre": 12, "12 de octubre": 12,
    "siete de agosto": 12, "7 de agosto": 12, "san fernando": 12,
    "la patria": 12, "los alcazares": 12, "alcazares": 12, "metropolis": 12,
    "entrerrios": 12, "jorge eliecer gaitan": 12, "benjamin herrera": 12,
    "muequeta": 12, "la castellana": 12, "polo club": 12, "el polo": 12,
    # 13 Teusaquillo
    "teusaquillo": 13, "ciudad salitre": 13, "el salitre": 13,
    "la esmeralda": 13, "galerias": 13, "palermo": 13,
    "nicolas de federman": 13, "quinta paredes": 13, "la soledad": 13,
    "el campin": 13, "pablo vi": 13, "gran america": 13,
    "acevedo tejada": 13, "corferias": 13, "modelo norte": 13,
    # 14 Los Mártires
    "los martires": 14, "martires": 14, "santa isabel": 14, "ricaurte": 14,
    "la sabana": 14, "paloquemao": 14, "samper mendoza": 14,
    "la estanzuela": 14, "voto nacional": 14, "san victorino": 14,
    "eduardo santos": 14, "veraguas": 14, "el liston": 14,
    # 15 Antonio Nariño
    "antonio narino": 15, "ciudad jardin": 15, "luna park": 15,
    "policarpa": 15, "la fragua": 15, "villa mayor": 15,
    # 16 Puente Aranda
    "puente aranda": 16, "ciudad montes": 16, "muzu": 16, "san rafael": 16,
    "alcala": 16, "la primavera": 16, "galan": 16, "pensilvania": 16,
    "la trinidad": 16, "zona industrial": 16, "granjas de techo": 16,
    "salazar gomez": 16, "la camelia": 16, "los ejidos": 16,
    # 17 La Candelaria
    "la candelaria": 17, "candelaria": 17, "egipto": 17,
    "belen candelaria": 17, "centro historico": 17, "la concordia": 17,
    "las aguas": 17, "centro administrativo": 17,
    # 18 Rafael Uribe Uribe
    "rafael uribe": 18, "rafael uribe uribe": 18, "quiroga": 18,
    "marco fidel suarez": 18, "marruecos": 18, "diana turbay": 18,
    "los molinos": 18, "olaya": 18, "bravo paez": 18, "country sur": 18,
    "san jose sur": 18, "palermo sur": 18, "gustavo restrepo": 18,
    # 19 Ciudad Bolívar
    "ciudad bolivar": 19, "el ensueno": 19, "ismael perdomo": 19,
    "jerusalen": 19, "el lucero": 19, "el tesoro": 19, "arborizadora": 19,
    "arborizadora alta": 19, "arborizadora baja": 19,
    "candelaria la nueva": 19, "perdomo": 19, "sierra morena": 19,
    "meissen": 19, "madelena": 19, "potosi": 19, "mochuelo": 19,
    # 20 Sumapaz
    "sumapaz": 20, "nazareth": 20, "betania sumapaz": 20,
    "san juan de sumapaz": 20,
}

# Se prueba de la frase más larga a la más corta: "san cristobal norte"
# (Usaquén) tiene que ganarle a "san cristobal" (localidad 4), que es prefijo
# suyo. Sin este orden el gazetteer resolvería por accidente de iteración.
_GAZETTEER_ORDENADO = sorted(_GAZETTEER.items(), key=lambda kv: -len(kv[0]))

# Avenidas con nombre -> el eje numerado equivalente, para poder aplicar la
# malla vial. "cl" = el número es de calle; "cra" = es de carrera.
_AVENIDAS_CON_NOMBRE = {
    "boyaca": ("cra", 72), "ciudad de cali": ("cra", 86), "suba": ("cra", 92),
    "caracas": ("cra", 14), "nqs": ("cra", 30), "norte quito sur": ("cra", 30),
    "autopista norte": ("cra", 45), "autopista sur": ("cl", -55),
    "el dorado": ("cl", 26), "jimenez": ("cl", 13), "medellin": ("cl", 80),
    "chile": ("cl", 72), "primero de mayo": ("cl", -22),
    "1 de mayo": ("cl", -22), "villavicencio": ("cl", -43),
    "las americas": ("cl", 6), "americas": ("cl", 6), "esperanza": ("cl", 24),
    "ciudad de quito": ("cra", 30), "rojas": ("cra", 70),
    "general santander": ("cra", 27), "circunvalar": ("cra", -1),
}

# Rectángulos (localidad, calle_min, calle_max, cra_min, cra_max) sobre la
# malla vial. El eje de calles es positivo al norte y negativo al sur; el de
# carreras, positivo al occidente y negativo al oriente. Se evalúan EN ORDEN:
# primero las localidades pequeñas y bien delimitadas, para que no se las
# trague un rectángulo grande que las contiene.
_MALLA_VIAL = [
    (17, 4, 13, -2, 11),        # La Candelaria
    # La Cra 30 (NQS) es el límite occidental de Los Mártires: sobre ella el
    # proyecto ya está en Puente Aranda.
    (14, 1, 26, 14, 29),        # Los Mártires
    (15, -26, 0, 9, 31),        # Antonio Nariño
    # Teusaquillo llega hasta la Calle 62; la 63 en adelante es Barrios Unidos.
    (13, 26, 62, 15, 51),       # Teusaquillo (arranca al occidente de la Caracas)
    (12, 63, 100, 14, 61),      # Barrios Unidos
    (16, -12, 27, 30, 57),      # Puente Aranda
    (3, -2, 40, -22, 15),       # Santa Fe
    (2, 39, 101, -22, 25),      # Chapinero
    (1, 100, 265, -22, 46),     # Usaquén
    # Suba baja hasta la Calle 88 por La Floresta, al occidente de la Cra 60.
    (11, 88, 265, 45, 145),     # Suba
    # Engativá baja hasta la Calle 26 por Normandía; Fontibón empieza más al
    # occidente, así que va después para no comerse esa franja.
    (10, 26, 88, 59, 132),      # Engativá
    (9, 12, 64, 70, 145),       # Fontibón
    (8, -47, 14, 55, 101),      # Kennedy
    (7, -101, -44, 74, 116),    # Bosa
    (6, -71, -37, 14, 46),      # Tunjuelito
    (18, -56, -19, 4, 31),      # Rafael Uribe Uribe
    (4, -51, 1, -26, 7),        # San Cristóbal
    (5, -111, -49, -16, 21),    # Usme
    (19, -96, -39, 14, 96),     # Ciudad Bolívar
]

_TIPOS_VIA = {
    "calle": "cl", "cll": "cl", "cl": "cl", "clle": "cl",
    "carrera": "cra", "cra": "cra", "cr": "cra", "kr": "cra", "kra": "cra",
    "diagonal": "cl", "diag": "cl", "dg": "cl",
    "transversal": "cra", "trans": "cra", "tv": "cra", "trv": "cra",
    "autopista": "cra", "auto": "cra",
}

_RE_VIA = re.compile(
    r"\b(?P<tipo>calle|cll|clle|cl|carrera|cra|cr|kra|kr|diagonal|diag|dg|"
    r"transversal|trans|trv|tv|autopista|auto)\s*"
    r"(?P<num>\d{1,3})\s*(?P<sufijo>[a-z]{0,3})\s*(?P<orientacion>sur|este|s|e)?\b"
)
_RE_AVENIDA = re.compile(r"\bav(?:enida)?\s+(?P<resto>[a-z0-9 ]{1,28})")
# El "sur"/"este" puede venir después de la placa: "# 65D 58 Sur".
_RE_CRUCE = re.compile(
    r"#\s*(?P<num>\d{1,3})\s*(?P<sufijo>[a-z]{0,3})\s*(?:\d{1,3}\s*)?(?P<orientacion>sur|este)?"
)
# Algunas fichas omiten el "#": "Carrera 7, 127b-31". El cruce se reconoce
# igual por la forma "<numero><letra opcional> - <placa>".
_RE_CRUCE_SIN_NUMERAL = re.compile(
    r"\b(?P<num>\d{1,3})\s*(?P<sufijo>[a-z]{0,2})\s*(?P<orientacion>sur|este)?\s+\d{1,3}\b"
)


def _menciona_otro_municipio(texto_normalizado):
    """Devuelve el municipio detectado si la dirección no es de Bogotá D.C."""
    for municipio in _FUERA_DE_BOGOTA:
        if re.search(r"\b" + re.escape(municipio) + r"\b", texto_normalizado):
            # "Bogotá" explícito manda: hay direcciones tipo "Cra 7, Bogotá,
            # vía La Calera" donde el municipio aparece solo como referencia.
            if re.search(r"\bbogota\b", texto_normalizado):
                continue
            return municipio
    return None


def _localidad_por_nombre_explicito(texto_normalizado):
    """La dirección nombra la localidad tal cual. Es la señal más fuerte."""
    for idx, nombre in enumerate(LOCALIDADES_BOGOTA, start=1):
        patron = r"\b" + re.escape(normalizar_texto(nombre)) + r"\b"
        if re.search(patron, texto_normalizado):
            return idx
    return None


def _localidad_por_gazetteer(texto_normalizado):
    """La dirección nombra un barrio, sector o UPZ conocido."""
    for frase, idx in _GAZETTEER_ORDENADO:
        if re.search(r"\b" + re.escape(frase) + r"\b", texto_normalizado):
            return idx, frase
    return None, None


def _eje_a_numero(num, orientacion, es_calle):
    """Lleva un número de vía al eje con signo que usa la malla vial.

    Calles: positivo al norte, negativo con sufijo "Sur".
    Carreras: positivo al occidente, negativo con sufijo "Este".
    """
    valor = int(num)
    if es_calle and orientacion in ("sur", "s"):
        return -valor
    if not es_calle and orientacion in ("este", "e"):
        return -valor
    return valor


def _parsear_malla_vial(texto_normalizado):
    """Extrae (calle, carrera) de una dirección de Bogotá.

    Devuelve (None, None) si la dirección no tiene la forma vía + cruce.
    """
    calle = carrera = None

    # 1. Avenidas con nombre: "Av. Boyacá # 21-11" -> carrera 72, calle 21.
    for m in _RE_AVENIDA.finditer(texto_normalizado):
        resto = m.group("resto").strip()
        # "av calle 26" / "av cra 68": el tipo viene justo detrás de "av".
        encabezado = re.match(r"(calle|cl|carrera|cra|kr)\s+(\d{1,3})", resto)
        if encabezado:
            eje = _TIPOS_VIA[encabezado.group(1)]
            valor = int(encabezado.group(2))
            if eje == "cl" and calle is None:
                calle = valor
            elif eje == "cra" and carrera is None:
                carrera = valor
            continue
        # "av 70": una avenida numerada es una carrera.
        solo_numero = re.match(r"(\d{1,3})\b", resto)
        if solo_numero and carrera is None:
            carrera = int(solo_numero.group(1))
            continue
        for nombre, (eje, valor) in _AVENIDAS_CON_NOMBRE.items():
            if resto.startswith(nombre):
                if eje == "cl" and calle is None:
                    calle = valor
                elif eje == "cra" and carrera is None:
                    carrera = valor
                break

    # 2. Vía principal declarada con su tipo.
    principal = None
    for m in _RE_VIA.finditer(texto_normalizado):
        eje = _TIPOS_VIA[m.group("tipo")]
        valor = _eje_a_numero(m.group("num"), m.group("orientacion"), eje == "cl")
        if eje == "cl" and calle is None:
            calle, principal = valor, "cl"
        elif eje == "cra" and carrera is None:
            carrera, principal = valor, "cra"
        if calle is not None and carrera is not None:
            break

    # 3. El número tras "#" es el cruce, y es del eje contrario al de la vía
    #    principal: "Calle 26 # 68-30" cruza con la carrera 68. Cuando la vía
    #    principal es una avenida con nombre no hay `principal`, así que se
    #    deduce por el eje que quedó vacío.
    if calle is None or carrera is None:
        cruce = _RE_CRUCE.search(texto_normalizado)
        if cruce is None and (calle is None) != (carrera is None):
            # Solo se intenta la forma sin "#" cuando ya hay una vía resuelta:
            # sobre un texto suelto ese patrón engancha cualquier par de
            # números y produciría ubicaciones inventadas.
            resto = texto_normalizado
            via = _RE_VIA.search(resto)
            if via:
                resto = resto[via.end():]
            cruce = _RE_CRUCE_SIN_NUMERAL.search(resto)
        if cruce:
            if principal == "cl":
                eje_del_cruce = "cra"
            elif principal == "cra":
                eje_del_cruce = "cl"
            else:
                eje_del_cruce = "cl" if calle is None else "cra"
            if eje_del_cruce == "cra" and carrera is None:
                carrera = _eje_a_numero(cruce.group("num"), cruce.group("orientacion"), False)
            elif eje_del_cruce == "cl" and calle is None:
                calle = _eje_a_numero(cruce.group("num"), cruce.group("orientacion"), True)

    return calle, carrera


def _localidad_por_malla_vial(texto_normalizado):
    """Último recurso: ubicar por el par (calle, carrera) de la dirección."""
    calle, carrera = _parsear_malla_vial(texto_normalizado)
    if calle is None or carrera is None:
        return None, None
    for idx, calle_min, calle_max, cra_min, cra_max in _MALLA_VIAL:
        if calle_min <= calle <= calle_max and cra_min <= carrera <= cra_max:
            return idx, f"calle {calle} x carrera {carrera}"
    return None, f"calle {calle} x carrera {carrera}"


def localidad_desde_direccion(direccion):
    """Resuelve la localidad de Bogotá D.C. a la que pertenece una dirección.

    Es la función del punto 2: recibe el texto de la dirección tal como lo
    publica la constructora y devuelve el id oficial de localidad (1..20).

    Args:
        direccion: texto libre, p. ej. "Carrera 95A # 78 Sur, Bosa Recreo".

    Returns:
        dict con:
            localidad     -> int 1..20, o None si no se pudo resolver
            nombre        -> nombre oficial de la localidad, o None
            confianza     -> "alta" | "media" | "baja" | None
            evidencia     -> qué disparó la decisión (para poder auditarla)
    """
    vacio = {"localidad": None, "nombre": None, "confianza": None, "evidencia": None}
    texto = normalizar_texto(direccion)
    if not texto:
        return dict(vacio, evidencia="direccion vacia")

    municipio = _menciona_otro_municipio(texto)
    if municipio:
        return dict(vacio, evidencia=f"fuera de Bogota: {municipio}")

    idx = _localidad_por_nombre_explicito(texto)
    if idx:
        return {
            "localidad": idx,
            "nombre": nombre_localidad(idx),
            "confianza": "alta",
            "evidencia": f"nombre de localidad en la direccion: {nombre_localidad(idx)}",
        }

    idx, frase = _localidad_por_gazetteer(texto)
    if idx:
        return {
            "localidad": idx,
            "nombre": nombre_localidad(idx),
            "confianza": "media",
            "evidencia": f"sector conocido: {frase}",
        }

    idx, detalle = _localidad_por_malla_vial(texto)
    if idx:
        return {
            "localidad": idx,
            "nombre": nombre_localidad(idx),
            "confianza": "baja",
            "evidencia": f"malla vial: {detalle}",
        }

    return dict(vacio, evidencia=f"sin coincidencia ({detalle})" if detalle else "sin coincidencia")


# ---------------------------------------------------------------------------
# Respaldo por coordenadas
#
# Tres de las cuatro fuentes publican una coordenada (Amarilo en
# field_proy_geolocalizacion, Bolívar en su JSON-LD y Colsubsidio dentro del
# iframe de Google Maps) y los límites oficiales del Distrito permiten
# convertirla en localidad de forma exacta.
#
# Aun así la coordenada NO manda sobre la dirección, y la razón es empírica:
# en varias fichas el pin apunta a la sala de ventas, no al proyecto. Eskala,
# de Colsubsidio, publica "Avenida carrera 50 # 5F-19" —Puente Aranda— y su
# iframe apunta a Bosa; Reserva del Nogal dice "Bosa Nova" y el pin cae en San
# Cristóbal, al otro extremo de la ciudad. La dirección es lo que la
# constructora afirma del proyecto, así que decide ella y la coordenada entra
# solo cuando la dirección no alcanza. Cuando ambas discrepan queda registrado
# en `_localidad_evidencia`, que es como se detectaron estos casos.
# ---------------------------------------------------------------------------
_POLIGONOS = None


def cargar_poligonos_localidades(ruta=RUTA_LOCALIDADES_GEO, descargar=True):
    """Carga los límites oficiales de las 20 localidades. None si no hay datos.

    El archivo pesa ~2 MB y no cambia, así que se guarda en `datos/` la primera
    vez y de ahí en adelante se lee de disco.
    """
    global _POLIGONOS
    if _POLIGONOS is not None:
        return _POLIGONOS or None

    crudo = None
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as archivo:
            crudo = json.load(archivo)
    elif descargar:
        try:
            respuesta = _get(URL_LOCALIDADES_GEO, timeout=120)
            crudo = respuesta.json()
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            with open(ruta, "w", encoding="utf-8") as archivo:
                json.dump(crudo, archivo, ensure_ascii=False)
        except Exception as error:  # sin red, el catálogo igual se construye
            print(f"  [aviso] no se pudieron cargar los limites oficiales: {error}")
            _POLIGONOS = []
            return None

    if not crudo:
        _POLIGONOS = []
        return None

    poligonos = []
    for feature in crudo.get("features", []):
        atributos = feature.get("attributes") or feature.get("properties") or {}
        codigo = atributos.get("LocCodigo") or atributos.get("loccodigo")
        geometria = feature.get("geometry") or {}
        anillos = geometria.get("rings") or geometria.get("coordinates") or []
        try:
            idx = int(str(codigo))
        except (TypeError, ValueError):
            continue
        if 1 <= idx <= 20 and anillos:
            poligonos.append((idx, anillos))

    _POLIGONOS = poligonos
    return poligonos or None


def _punto_en_anillo(lon, lat, anillo):
    """Ray casting clásico sobre un anillo [[lon, lat], ...]."""
    dentro = False
    n = len(anillo)
    j = n - 1
    for i in range(n):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if (yi > lat) != (yj > lat):
            corte = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < corte:
                dentro = not dentro
        j = i
    return dentro


def localidad_desde_coordenadas(lat, lon, ruta=RUTA_LOCALIDADES_GEO):
    """Localidad exacta por punto dentro de los límites oficiales.

    Returns:
        dict con la misma forma que `localidad_desde_direccion`, o None si no
        hay capa de límites disponible.
    """
    if lat is None or lon is None:
        return None
    poligonos = cargar_poligonos_localidades(ruta)
    if not poligonos:
        return None
    for idx, anillos in poligonos:
        # Los anillos interiores (huecos) invierten la pertenencia, que es
        # justo lo que hace el conteo par/impar acumulado sobre todos ellos.
        dentro = False
        for anillo in anillos:
            if anillo and isinstance(anillo[0][0], (list, tuple)):
                anillo = anillo[0]  # GeoJSON envuelve un nivel más que esriJSON
            if _punto_en_anillo(lon, lat, anillo):
                dentro = not dentro
        if dentro:
            return {
                "localidad": idx,
                "nombre": nombre_localidad(idx),
                "confianza": "alta",
                "evidencia": f"coordenada dentro del limite oficial ({lat:.5f}, {lon:.5f})",
            }
    return {
        "localidad": None,
        "nombre": None,
        "confianza": None,
        "evidencia": f"coordenada fuera de Bogota ({lat:.5f}, {lon:.5f})",
    }


# Llaves donde cada fuente puede traer la dirección, en orden de preferencia.
_LLAVES_DIRECCION = (
    "direccion", "Direccion", "dirección", "Dirección",
    "address", "streetAddress", "direccion_proyecto",
)
_LLAVES_LAT = ("lat", "latitud", "latitude")
_LLAVES_LON = ("lon", "lng", "longitud", "longitude")


def _primer_valor(registro, llaves):
    for llave in llaves:
        valor = registro.get(llave)
        if valor not in (None, ""):
            return valor
    return None


def asignar_localidades(proyectos, usar_coordenadas=True, ruta_geo=RUTA_LOCALIDADES_GEO):
    """Agrega el atributo `Localidad` a cada proyecto a partir de su dirección.

    Esta es la función del punto 2 del encargo. Recibe el JSON de proyectos de
    vivienda de Bogotá D.C., lee la dirección de cada uno y devuelve el mismo
    JSON con la localidad asignada. No muta la entrada: trabaja sobre copias.

    Acepta cualquiera de estas formas de entrada, y devuelve la misma:
        - lista de proyectos
        - dict con la llave "proyectos"
        - string con el JSON serializado
        - ruta a un archivo .json

    Cada proyecto sale con:
        Localidad                -> int 1..20, o None si no se pudo resolver
        localidad_nombre         -> nombre oficial, para que el JSON se lea solo
        _localidad_confianza     -> "alta" | "media" | "baja"
        _localidad_evidencia     -> qué dato disparó la asignación

    Args:
        usar_coordenadas: permite que un proyecto con lat/lon se resuelva por
            los límites oficiales del Distrito CUANDO la dirección no alcanzó.
            La dirección siempre tiene prioridad; ver la nota sobre los pines
            que apuntan a la sala de ventas más arriba.
    """
    entrada_era_texto = entrada_era_ruta = False
    if isinstance(proyectos, str):
        if os.path.exists(proyectos):
            entrada_era_ruta = True
            with open(proyectos, "r", encoding="utf-8") as archivo:
                datos = json.load(archivo)
        else:
            entrada_era_texto = True
            datos = json.loads(proyectos)
    else:
        datos = proyectos

    if isinstance(datos, dict) and "proyectos" in datos:
        contenedor, lista = dict(datos), datos["proyectos"]
    elif isinstance(datos, dict):
        contenedor, lista = None, [datos]
    else:
        contenedor, lista = None, list(datos)

    resueltos = []
    for proyecto in lista:
        copia = dict(proyecto)
        direccion = _primer_valor(copia, _LLAVES_DIRECCION)
        veredicto = localidad_desde_direccion(direccion)

        if usar_coordenadas and "fuera de Bogota" not in (veredicto["evidencia"] or ""):
            lat, lon = _primer_valor(copia, _LLAVES_LAT), _primer_valor(copia, _LLAVES_LON)
            try:
                por_geo = localidad_desde_coordenadas(float(lat), float(lon), ruta_geo)
            except (TypeError, ValueError):
                por_geo = None
            if por_geo and not por_geo["localidad"] and veredicto["localidad"] is None:
                # La dirección no dijo nada y la coordenada cae fuera del
                # Distrito: el proyecto es de otro municipio aunque la fuente
                # lo publique bajo "Bogotá y sus alrededores".
                veredicto = dict(veredicto, evidencia=por_geo["evidencia"])
            elif por_geo and por_geo["localidad"]:
                if veredicto["localidad"] is None:
                    veredicto = por_geo
                elif veredicto["localidad"] != por_geo["localidad"]:
                    # Manda la dirección, pero la discrepancia se anota: o al
                    # gazetteer le falta ese sector, o el pin del mapa apunta
                    # a la sala de ventas. Ambas cosas hay que poder verlas.
                    veredicto = dict(veredicto)
                    veredicto["evidencia"] += f" | la coordenada cae en {por_geo['nombre']}"

        copia["Localidad"] = veredicto["localidad"]
        copia["localidad_nombre"] = veredicto["nombre"]
        copia["_localidad_confianza"] = veredicto["confianza"]
        copia["_localidad_evidencia"] = veredicto["evidencia"]
        resueltos.append(copia)

    if contenedor is not None:
        contenedor["proyectos"] = resueltos
        salida = contenedor
    elif isinstance(datos, dict):
        salida = resueltos[0]
    else:
        salida = resueltos

    if entrada_era_texto:
        return json.dumps(salida, ensure_ascii=False, indent=2)
    if entrada_era_ruta:
        with open(proyectos, "w", encoding="utf-8") as archivo:
            json.dump(salida, archivo, ensure_ascii=False, indent=2)
    return salida


# ===========================================================================
# C. Capa HTTP
# ===========================================================================
_SESION = requests.Session()
_SESION.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9",
})

# Hosts a los que ya se les tuvo que bajar la verificación de certificado.
# amarilo.com.co no envía el certificado intermedio de su cadena, así que
# cualquier cliente que no lo tenga cacheado falla: su propio front web
# arranca axios con rejectUnauthorized:false por lo mismo. Se reintenta sin
# verificar solo por host y solo tras haberlo intentado bien primero.
_SIN_VERIFICAR = set()
_AVISADOS = set()      # para no repetir el aviso una vez por imagen


def _get(url, timeout=TIMEOUT, reintentos=REINTENTOS, **kwargs):
    """GET con reintentos y respaldo de TLS por host."""
    host = urlparse(url).netloc
    ultimo_error = None
    for intento in range(reintentos):
        verificar = host not in _SIN_VERIFICAR
        try:
            respuesta = _SESION.get(url, timeout=timeout, verify=verificar, **kwargs)
            respuesta.raise_for_status()
            return respuesta
        except requests.exceptions.SSLError as error:
            ultimo_error = error
            if not verificar:
                break            # ya iba sin verificar y aun así falló
            # El intento fue con verificación: se marca el host y se repite.
            # La condición se evalúa sobre `verificar`, no sobre el conjunto,
            # porque varios hilos golpean el mismo host a la vez: si otro ya
            # lo marcó entre medias, este intento igual se hizo verificando y
            # merece su reintento en vez de darse por perdido.
            if host not in _AVISADOS:
                _AVISADOS.add(host)
                print(f"  [aviso] {host} tiene la cadena TLS incompleta; se reintenta sin verificar")
            _SIN_VERIFICAR.add(host)
            continue
        except requests.RequestException as error:
            ultimo_error = error
            if intento == reintentos - 1:
                break
            # Backoff: los fallos que se ven aquí son de saturación, no de
            # ruta, así que reintentar de inmediato solo empeora la cola.
            time.sleep(ESPERA_REINTENTO * (2 ** intento))
    raise RuntimeError(f"GET falló en {url}: {ultimo_error}")


def _sopa(url, **kwargs):
    return BeautifulSoup(_get(url, **kwargs).text, "lxml")


def _next_data(html):
    """Extrae el JSON de <script id="__NEXT_DATA__">, que es donde Next.js deja
    el nodo completo de la página. None si la página no es Next."""
    encontrado = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S
    )
    if not encontrado:
        return None
    try:
        return json.loads(encontrado.group(1))
    except json.JSONDecodeError:
        return None


def _texto_plano(html_o_texto):
    """Quita etiquetas de un fragmento HTML y devuelve texto limpio."""
    if not html_o_texto:
        return ""
    if "<" in str(html_o_texto):
        return BeautifulSoup(str(html_o_texto), "lxml").get_text(" ", strip=True)
    return str(html_o_texto).strip()


def _entero(valor):
    """Primer entero que aparezca en el valor. None si no hay ninguno."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return int(valor)
    encontrado = re.search(r"\d[\d.,]*", str(valor))
    if not encontrado:
        return None
    limpio = encontrado.group(0).replace(".", "").replace(",", "")
    return int(limpio) if limpio.isdigit() else None


def _decimal(valor):
    """Primer número decimal del valor, tolerando la coma como separador."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    encontrado = re.search(r"\d+(?:[.,]\d+)?", str(valor))
    if not encontrado:
        return None
    return float(encontrado.group(0).replace(",", "."))


def tipo_vivienda_codificado(valor):
    """1 = VIS, 0 = No VIS, None si la fuente no lo declara.

    `catalogos.codigo_tipo_vivienda` solo entiende "VIS" y "No VIS"; las cuatro
    constructoras publican además VIP, "TOPE VIS" y "VIS de renovación urbana".
    Todas ellas están dentro del régimen de interés social, que es lo que el
    filtro del modelo necesita saber para decidir si aplica subsidio, así que
    entran como 1. "No aplica", que es como Colsubsidio marca los proyectos
    sin subsidio, es un No VIS explícito.
    """
    texto = normalizar_texto(valor)
    if not texto:
        return None
    if texto in ("no aplica", "ninguno", "n a"):
        return 0
    if "no vis" in texto:
        return 0
    if "vis" in texto or "vip" in texto:
        return 1
    return codigo_tipo_vivienda(valor)


# Un proyecto comercial no es vivienda: no tiene habitaciones ni subsidio y no
# le sirve a nadie que busca dónde vivir. Amarilo los publica en el mismo
# listado que los residenciales, así que se descartan por nombre.
_PALABRAS_NO_RESIDENCIALES = (
    "zona comercial", "locales", "local comercial", "oficina", "oficinas",
    "parque empresarial", "centro empresarial", "bodegas", "lote",
)


def _es_residencial(registro):
    nombre = normalizar_texto(registro.get("nombre_proyecto"))
    return not any(palabra in nombre for palabra in _PALABRAS_NO_RESIDENCIALES)


def _habitaciones_codificadas(valor):
    """Lleva el número de habitaciones al código del formulario: 1, 2 o 3,
    donde 3 significa "3 o más". None si el proyecto no lo publica."""
    numero = _entero(valor)
    if numero is None or numero < 1:
        return None
    return min(numero, 3)


# ===========================================================================
# D. Scrapers
#
# Cada uno devuelve una lista de registros crudos con la misma forma; la
# traducción al contrato final la hace `_a_contrato` una sola vez, para que
# agregar una quinta constructora no obligue a tocar el formato de salida.
# ===========================================================================
def _registro(fuente, **campos):
    base = {
        "fuente": fuente,
        "nombre_proyecto": None,
        "direccion": None,
        "link_proyecto": None,
        "ciudad": None,
        "tipo_vivienda_raw": None,
        "habitaciones_raw": None,
        "zonas_comunes_raw": [],
        "imagenes": [],
        "precio_desde_cop": None,
        "area_desde_m2": None,
        "lat": None,
        "lon": None,
    }
    base.update(campos)
    return base


# --------------------------------------------------------------------------
# D.1 Amarilo
#
# https://amarilo.com.co/proyectos?ciudad=Bogotá renderiza las tarjetas en el
# cliente: el <div id="proyectos"> llega vacío con class="loading" y el listado
# lo trae después /search/v1/proyecto. Ese endpoint devuelve el nodo completo
# —dirección, cifras, galería y zonas comunes— así que se consulta directo en
# vez de reconstruir a mano la ruta main > .column-project > .card-content >
# .name > .title que describe el HTML ya renderizado.
# --------------------------------------------------------------------------
API_AMARILO = "https://apiweb.amarilo.com.co/search/v1/proyecto"
CIUDAD_AMARILO = "Bogotá"


def scrape_amarilo():
    """Proyectos de Amarilo en Bogotá."""
    print("[amarilo] consultando API de proyectos...")
    datos = _get(f"{API_AMARILO}?page[limit]=500&sort=c_weight").json()
    crudos = datos.get("data", [])
    print(f"[amarilo] {len(crudos)} proyectos en todo el país")

    registros = []
    for nodo in crudos:
        if normalizar_texto(nodo.get("field_proy_ubicacion__ciudad")) != normalizar_texto(CIUDAD_AMARILO):
            continue

        cifras = nodo.get("field_proy_cifras") or {}

        # Las zonas comunes vienen como un <ul> y las características como
        # lista aparte; ambas describen amenidades y se unen antes de mapear.
        zonas = [
            li.get_text(" ", strip=True)
            for li in BeautifulSoup(nodo.get("field_proy_zonas_comunes") or "", "lxml").select("li")
        ]
        zonas += [z for z in (nodo.get("field_proy_caracteristicas") or []) if z]

        # "-74.06,4.71": la fuente publica longitud primero.
        lat = lon = None
        geo = (nodo.get("field_proy_geolocalizacion") or "").split(",")
        if len(geo) == 2:
            try:
                lon, lat = float(geo[0]), float(geo[1])
            except ValueError:
                lat = lon = None

        registros.append(_registro(
            "amarilo",
            nombre_proyecto=(nodo.get("title") or "").strip(),
            direccion=(nodo.get("field_proy_direccion") or "").strip(),
            link_proyecto=urljoin("https://amarilo.com.co", nodo.get("url") or ""),
            ciudad=nodo.get("field_proy_ubicacion__ciudad"),
            tipo_vivienda_raw=nodo.get("field_proy_subsidio"),
            habitaciones_raw=cifras.get("field_proy_habitaciones"),
            zonas_comunes_raw=zonas,
            imagenes=[u for u in (nodo.get("field_proy_galeria") or []) if u],
            precio_desde_cop=_entero(cifras.get("field_proy_precio_desde")),
            area_desde_m2=_decimal(cifras.get("field_proy_area_desde")),
            lat=lat,
            lon=lon,
        ))

    print(f"[amarilo] {len(registros)} proyectos en Bogotá")
    return registros


# --------------------------------------------------------------------------
# D.2 Cusezar
#
# El listado sí trae las tarjetas en el HTML: main > .project-cards >
# article.project-card. Cada una lleva un <a data-gtm="proyectos-cards"> con
# el enlace a la ficha y un data-gtm-props con dirección, zona y precio ya
# estructurados, que es de donde se leen para no depender del texto visible.
# Las amenidades y la galería sí hay que ir a buscarlas a la ficha.
#
# Ojo: ?ciudad=bogota NO filtra del lado del servidor; el listado trae también
# Cali, Cartagena y La Calera. El filtro real lo hace la localidad: una
# dirección de otro municipio sale con Localidad = None y se descarta.
# --------------------------------------------------------------------------
URL_CUSEZAR = "https://cusezar.com/home-proyectos/?ciudad=bogota"


def _ficha_cusezar(url):
    """Amenidades, imágenes, descripción y alcobas de una ficha de Cusezar."""
    zonas, imagenes, descripcion, habitaciones = [], [], "", None
    try:
        sopa = _sopa(url)
    except RuntimeError as error:
        print(f"  [cusezar] no se pudo leer {url}: {error}")
        return zonas, imagenes, descripcion, habitaciones

    # Las zonas comunes son la grilla de iconos que sigue al h3 homónimo; la
    # etiqueta legible está en el alt de cada <img>, no en texto suelto.
    for titulo in sopa.find_all(["h2", "h3"]):
        if "zonas comunes" in normalizar_texto(titulo.get_text()):
            grilla = titulo.find_next("div", class_=lambda c: c and "grid" in c)
            if grilla:
                zonas += [img.get("alt") for img in grilla.select("img[alt]") if img.get("alt")]
    if not zonas:
        # Respaldo: algunas fichas listan las amenidades solo como iconos SVG
        # sueltos, y el nombre del archivo es la única etiqueta disponible.
        for img in sopa.select('img[src*="/wp-content/uploads/"]'):
            src = img.get("src") or ""
            if src.endswith(".svg") and img.get("alt"):
                zonas.append(img["alt"])

    galeria = sopa.select_one(".mainGallery") or sopa.select_one(".cusezar__project__slider")
    if galeria:
        imagenes = [
            img.get("src") or img.get("data-src")
            for img in galeria.select("img")
            if (img.get("src") or img.get("data-src"))
        ]
    else:
        # Algunos proyectos usan otra plantilla (.section__five-slider) sin la
        # galería principal. Se recogen las fotos subidas al CMS, quitando
        # logos e iconos, que son marca y no el proyecto.
        vistas = []
        for img in sopa.select("img[src], img[data-src]"):
            src = img.get("src") or img.get("data-src") or ""
            if "/wp-content/uploads/" not in src or src.lower().endswith(".svg"):
                continue
            if re.search(r"logo|icono|icon[-_]", src, re.I):
                continue
            vistas.append(src)
        imagenes = list(dict.fromkeys(vistas))

    bloque = sopa.select_one(".project-description")
    if bloque:
        descripcion = bloque.get_text(" ", strip=True)

    # Las alcobas no están en la descripción sino en el bloque de tipologías
    # ("3 Alcobas 1 Baño"), que se repite por cada tipo de apartamento: se
    # toma el máximo, que es la oferta tope del proyecto.
    habitaciones = _habitaciones_desde_texto(sopa.get_text(" ", strip=True))

    return zonas, imagenes, descripcion, habitaciones


def scrape_cusezar():
    """Proyectos de Cusezar publicados en el listado de Bogotá."""
    print("[cusezar] leyendo listado...")
    sopa = _sopa(URL_CUSEZAR)
    tarjetas = sopa.select("article.project-card")
    print(f"[cusezar] {len(tarjetas)} tarjetas en el listado")

    pendientes = []
    vistos = set()
    for tarjeta in tarjetas:
        enlace = tarjeta.select_one('a[data-gtm="proyectos-cards"][href]')
        if not enlace:
            continue
        url = urljoin(URL_CUSEZAR, enlace["href"])
        if url in vistos:
            continue
        vistos.add(url)
        try:
            props = json.loads(enlace.get("data-gtm-props") or "{}")
        except json.JSONDecodeError:
            props = {}

        # event_action trae el nombre, pero a veces llega como "NA" o con el
        # claim de marketing pegado; el h2/h3 de la tarjeta es más limpio.
        nombre = (props.get("event_action") or "").strip()
        if nombre.upper() in ("", "NA"):
            titulo = tarjeta.find(["h2", "h3", "h4"])
            if titulo:
                nombre = titulo.get_text(" ", strip=True)
            else:
                # Último recurso: el slug de la ficha, sin la query, que es
                # lo que diferencia /proyectos-vizcaya/?ciudad=bogota.
                slug = urlparse(url).path.rstrip("/").split("/")[-1]
                nombre = slug.replace("proyectos-", "").replace("-", " ").title()
        nombre = nombre.split(":")[0].strip()

        metricas = tarjeta.select_one(".project-card__info--metrics")
        pendientes.append((url, {
            "nombre_proyecto": nombre,
            "direccion": (props.get("direccion") or props.get("zona") or "").strip(),
            "ciudad": (props.get("zona") or "").strip(),
            "precio_desde_cop": _entero(props.get("precio")),
            "area_desde_m2": _decimal(metricas.get_text(" ", strip=True)) if metricas else None,
        }))

    registros = []
    with ThreadPoolExecutor(max_workers=HILOS) as pool:
        futuros = {pool.submit(_ficha_cusezar, url): (url, base) for url, base in pendientes}
        for futuro in as_completed(futuros):
            url, base = futuros[futuro]
            zonas, imagenes, descripcion, habitaciones = futuro.result()
            # La descripción de la ficha suele decir "ubicado en la localidad
            # de X"; se pega a la dirección porque es la señal más fuerte que
            # publica Cusezar, que no da coordenadas.
            direccion = base["direccion"]
            localidad_en_texto = re.search(
                r"localidad de ([A-Za-zÁÉÍÓÚÑáéíóúñ ]{3,25})", descripcion
            )
            if localidad_en_texto:
                direccion = f"{direccion}, {localidad_en_texto.group(1).strip()}"

            # El tipo de vivienda no está en la tarjeta: la URL lo delata
            # (/proyectos/con-subsidio/...) y la descripción lo confirma.
            es_vis = "con-subsidio" in url or "interes social" in normalizar_texto(descripcion)
            registros.append(_registro(
                "cusezar",
                link_proyecto=url,
                tipo_vivienda_raw="VIS" if es_vis else "No VIS",
                habitaciones_raw=habitaciones,
                zonas_comunes_raw=zonas,
                imagenes=imagenes,
                **{**base, "direccion": direccion},
            ))

    print(f"[cusezar] {len(registros)} proyectos leídos")
    return registros


def _habitaciones_desde_texto(texto):
    """Número máximo de alcobas mencionado en un texto libre."""
    if not texto:
        return None
    encontrados = re.findall(r"(\d)\s*(?:alcoba|habitaci)", normalizar_texto(texto))
    return max((int(n) for n in encontrados), default=None)


# --------------------------------------------------------------------------
# D.3 Constructora Bolívar
#
# El listado es una app Vue: el HTML trae la plantilla (.sectionPageResult >
# .container > .col-12.col-md-4 > .itemProject) pero no los datos, que llegan
# de /api/proyectos-vivienda/{ciudad}/all/{tipo}/{estado}/{clasificacion}.
# La ciudad 20 es "Bogotá y sus alrededores".
#
# El listado no publica la dirección, así que hay que entrar a cada ficha.
# Ahí sí está, y bien: cada ficha lleva un JSON-LD ApartmentComplex con
# dirección postal, coordenadas, amenidades y alcobas ya estructurados.
# --------------------------------------------------------------------------
BASE_BOLIVAR = "https://www.constructorabolivar.com"
API_BOLIVAR = BASE_BOLIVAR + "/api/proyectos-vivienda/{ciudad}/all/all/all/all"
CIUDAD_BOLIVAR = 20


def _ficha_bolivar(url):
    """JSON-LD, imágenes y amenidades de una ficha de Constructora Bolívar."""
    vacio = {"direccion": None, "lat": None, "lon": None, "zonas": [], "imagenes": [], "habitaciones": None}
    try:
        html = _get(url).text
    except RuntimeError as error:
        print(f"  [bolivar] no se pudo leer {url}: {error}")
        return vacio

    sopa = BeautifulSoup(html, "lxml")
    bloque = sopa.find("script", id="schema-proyectos-complex")
    ficha = {}
    if bloque and bloque.string:
        try:
            ficha = json.loads(bloque.string)
        except json.JSONDecodeError:
            ficha = {}

    direccion = None
    if isinstance(ficha.get("address"), dict):
        partes = [
            ficha["address"].get("streetAddress"),
            ficha["address"].get("addressLocality"),
        ]
        direccion = ", ".join(p for p in partes if p)
    if not direccion:
        # Respaldo: el bloque de la sala de ventas al pie de la ficha.
        etiqueta = sopa.find("strong", string=re.compile(r"Direcci"))
        if etiqueta and etiqueta.parent:
            direccion = etiqueta.parent.get_text(" ", strip=True).split(":", 1)[-1].strip()

    lat = lon = None
    if isinstance(ficha.get("geo"), dict):
        lat = _decimal(ficha["geo"].get("latitude"))
        lon = _decimal(ficha["geo"].get("longitude"))

    zonas = [
        a.get("name") for a in (ficha.get("amenityFeature") or [])
        if isinstance(a, dict) and a.get("name")
    ]

    habitaciones = None
    for propiedad in (ficha.get("additionalProperty") or []):
        if isinstance(propiedad, dict) and normalizar_texto(propiedad.get("name")) == "alcobas":
            habitaciones = _habitaciones_desde_texto(str(propiedad.get("value")) + " alcobas")

    # La galería vive en el blob de Azure; se descartan los iconos SVG, que
    # son de la interfaz y no del proyecto.
    imagenes = []
    for img in sopa.select("img[src]"):
        src = img["src"]
        if "cbolivarstorage" in src and not src.lower().endswith(".svg"):
            imagenes.append(src)

    return {
        "direccion": direccion,
        "lat": lat,
        "lon": lon,
        "zonas": zonas,
        "imagenes": imagenes,
        "habitaciones": habitaciones,
    }


def scrape_bolivar():
    """Proyectos de Constructora Bolívar en Bogotá y alrededores."""
    print("[bolivar] consultando API de proyectos...")
    crudos = _get(API_BOLIVAR.format(ciudad=CIUDAD_BOLIVAR)).json()
    print(f"[bolivar] {len(crudos)} proyectos en el listado")

    pendientes = []
    for nodo in crudos:
        externa = (nodo.get("field_url_redireccion_externa") or "").strip()
        ruta = (nodo.get("view_node") or "").strip()
        url = externa or urljoin(BASE_BOLIVAR, ruta)
        if not ruta:
            continue  # sin ficha propia no hay dirección que leer
        pendientes.append((urljoin(BASE_BOLIVAR, ruta), url, nodo))

    registros = []
    with ThreadPoolExecutor(max_workers=HILOS) as pool:
        futuros = {
            pool.submit(_ficha_bolivar, url_ficha): (url_publico, nodo)
            for url_ficha, url_publico, nodo in pendientes
        }
        for futuro in as_completed(futuros):
            url_publico, nodo = futuros[futuro]
            detalle = futuro.result()
            imagen_tarjeta = nodo.get("field_imagen_card")
            imagenes = detalle["imagenes"]
            if imagen_tarjeta and imagen_tarjeta not in imagenes:
                imagenes = [imagen_tarjeta] + imagenes

            registros.append(_registro(
                "bolivar",
                nombre_proyecto=(nodo.get("title") or "").strip(),
                direccion=detalle["direccion"],
                link_proyecto=url_publico,
                ciudad=nodo.get("field_ciudad"),
                tipo_vivienda_raw=nodo.get("field_clasificacion_proyecto_pro"),
                habitaciones_raw=detalle["habitaciones"] or _habitaciones_desde_texto(
                    nodo.get("field_alcobas_card")
                ),
                zonas_comunes_raw=detalle["zonas"],
                imagenes=imagenes,
                precio_desde_cop=_entero(nodo.get("field_precio")),
                area_desde_m2=_decimal(nodo.get("field_area_card")),
                lat=detalle["lat"],
                lon=detalle["lon"],
            ))

    print(f"[bolivar] {len(registros)} proyectos leídos")
    return registros


# --------------------------------------------------------------------------
# D.4 Colsubsidio
#
# El listado se arma con /api/basicProjectSearch, que devuelve el catálogo
# completo del país; los 29 de Bogotá son los que traen
# field_housing_project_department == "Bogotá" (el campo "city" guarda el
# sector comercial —Norte, Occidente, Centro—, no el municipio).
#
# Ese endpoint no trae dirección ni amenidades, así que cada ficha se lee
# aparte: es Drupal servido por Next.js y publica el nodo entero dentro de
# __NEXT_DATA__. Su JSON:API (cms.colsubsidio.com/jsonapi) responde vacío a
# usuarios anónimos, por eso no se usa.
# --------------------------------------------------------------------------
BASE_COLSUBSIDIO = "https://www.colsubsidio.com"
API_COLSUBSIDIO = BASE_COLSUBSIDIO + "/api/basicProjectSearch"
DEPARTAMENTO_COLSUBSIDIO = "Bogotá"

# Las rutas de imagen del nodo (/sites/default/files/...) son del Drupal que
# hay detrás, no del front: sobre www responden 404 con una página de error de
# 800 KB. Los archivos se sirven desde el CMS.
CMS_COLSUBSIDIO = "https://cms.colsubsidio.com"


def _recorrer(nodo):
    """Todos los diccionarios de un árbol JSON, en profundidad."""
    if isinstance(nodo, dict):
        yield nodo
        for valor in nodo.values():
            yield from _recorrer(valor)
    elif isinstance(nodo, list):
        for valor in nodo:
            yield from _recorrer(valor)


SITEMAP_COLSUBSIDIO = BASE_COLSUBSIDIO + "/sitemap-0.xml"
_RE_FICHA_COLSUBSIDIO = re.compile(
    r"https://www\.colsubsidio\.com/vivienda/proyectos/[a-z0-9\-]+/[a-z0-9\-]+"
)


def _urls_publicadas_colsubsidio():
    """URLs de ficha realmente publicadas, según el sitemap.

    El buscador devuelve URLs que a veces quedaron viejas: para "Abeto" apunta
    a /abeto, que responde 200 pero sin nodo, mientras la ficha viva es
    /abeto-v2. El sitemap sí está al día, así que sirve para corregirlas.
    """
    try:
        xml = _get(SITEMAP_COLSUBSIDIO, timeout=90).text
    except RuntimeError as error:
        print(f"  [colsubsidio] no se pudo leer el sitemap: {error}")
        return []
    return sorted(set(_RE_FICHA_COLSUBSIDIO.findall(xml)))


def _corregir_url_colsubsidio(url, publicadas):
    """Cambia una URL de ficha por la publicada que corresponda al mismo slug."""
    if not publicadas or url in publicadas:
        return url
    slug = url.rstrip("/").split("/")[-1]
    # El slug vivo es el mismo más un sufijo de versión (-v2, -v3...).
    candidatas = [u for u in publicadas if u.rstrip("/").split("/")[-1].startswith(slug + "-")]
    if len(candidatas) == 1:
        print(f"  [colsubsidio] URL desactualizada: {slug} -> {candidatas[0].split('/')[-1]}")
        return candidatas[0]
    return url


def _ficha_colsubsidio(url):
    """Dirección, amenidades, coordenadas e imágenes de una ficha Colsubsidio."""
    vacio = {"direccion": None, "lat": None, "lon": None, "zonas": [], "imagenes": []}
    try:
        html = _get(url).text
    except RuntimeError as error:
        print(f"  [colsubsidio] no se pudo leer {url}: {error}")
        return vacio

    datos = _next_data(html)
    if not datos:
        return vacio
    recurso = (datos.get("props") or {}).get("pageProps", {}).get("resource") or {}

    direccion = lat = lon = None
    zonas, imagenes = [], []

    for nodo in _recorrer(recurso):
        tipo = nodo.get("type")

        # La dirección del PROYECTO va en field_long_description_two del
        # módulo de mapa. Cuidado con field_address_2, del mismo bloque: esa
        # es la sala de ventas, que a veces está en otro municipio.
        if tipo and "map" in str(tipo):
            bruto = nodo.get("field_long_description_two")
            if isinstance(bruto, dict):
                bruto = bruto.get("value")
            texto = _texto_plano(bruto)
            if texto and not direccion:
                direccion = texto
            # El iframe de Google Maps lleva la coordenada: !2d<lon>!3d<lat>.
            iframe = nodo.get("field_url_iframe_2") or nodo.get("field_url_iframe") or ""
            coordenada = re.search(r"!2d(-?\d+\.\d+)!3d(-?\d+\.\d+)", str(iframe))
            if coordenada and lat is None:
                lon, lat = float(coordenada.group(1)), float(coordenada.group(2))

        # Las amenidades son paragraphs information_with_icons_item y la
        # etiqueta viaja en field_link.title, no en field_description (vacío).
        if tipo == "paragraph--information_with_icons_item":
            enlace = nodo.get("field_link")
            if isinstance(enlace, dict) and enlace.get("title"):
                zonas.append(enlace["title"])

        uri = nodo.get("uri")
        if isinstance(uri, dict) and uri.get("url"):
            imagenes.append(uri["url"])

    # Los .svg son los iconos de las amenidades y de las tipologías, no fotos.
    imagenes = [
        urljoin(CMS_COLSUBSIDIO, u) for u in dict.fromkeys(imagenes)
        if not u.lower().endswith(".svg")
    ]
    return {"direccion": direccion, "lat": lat, "lon": lon, "zonas": zonas, "imagenes": imagenes}


def scrape_colsubsidio():
    """Los 29 proyectos de Colsubsidio en Bogotá D.C."""
    print("[colsubsidio] consultando el buscador de proyectos...")
    respuesta = _get(API_COLSUBSIDIO).json()
    crudos = respuesta.get("data", [])
    objetivo = normalizar_texto(DEPARTAMENTO_COLSUBSIDIO)
    bogota = [
        n for n in crudos
        if normalizar_texto(n.get("field_housing_project_department")) == objetivo
    ]
    print(f"[colsubsidio] {len(bogota)} proyectos en Bogotá de {len(crudos)} en el país")

    publicadas = _urls_publicadas_colsubsidio()
    pendientes = []
    for nodo in bogota:
        # El campo llega como "internal:/vivienda/proyectos/bogota/acanto ".
        ruta = (nodo.get("url") or "").replace("internal:", "").strip()
        if not ruta:
            continue
        url = _corregir_url_colsubsidio(urljoin(BASE_COLSUBSIDIO, ruta), publicadas)
        pendientes.append((url, nodo))

    registros = []
    with ThreadPoolExecutor(max_workers=HILOS_POR_FUENTE.get("colsubsidio", HILOS)) as pool:
        futuros = {pool.submit(_ficha_colsubsidio, url): (url, nodo) for url, nodo in pendientes}
        for futuro in as_completed(futuros):
            url, nodo = futuros[futuro]
            detalle = futuro.result()
            imagenes = detalle["imagenes"]
            portada = nodo.get("image")
            if portada:
                portada = urljoin(CMS_COLSUBSIDIO, portada)
                if portada not in imagenes:
                    imagenes = [portada] + imagenes

            registros.append(_registro(
                "colsubsidio",
                nombre_proyecto=" ".join((nodo.get("title") or "").split()),
                direccion=detalle["direccion"],
                link_proyecto=url,
                ciudad=DEPARTAMENTO_COLSUBSIDIO,
                tipo_vivienda_raw=nodo.get("field_subsidy_type"),
                habitaciones_raw=nodo.get("field_rooms"),
                zonas_comunes_raw=detalle["zonas"],
                imagenes=imagenes,
                precio_desde_cop=_entero(nodo.get("field_price")),
                area_desde_m2=_decimal(nodo.get("field_area")),
                lat=detalle["lat"],
                lon=detalle["lon"],
            ))

    print(f"[colsubsidio] {len(registros)} proyectos leídos")
    return registros


FUENTES = {
    "amarilo": scrape_amarilo,
    "cusezar": scrape_cusezar,
    "bolivar": scrape_bolivar,
    "colsubsidio": scrape_colsubsidio,
}


# ===========================================================================
# E. Contrato de salida
#
# El encargo pide llenar "el mismo JSON" del formulario. Ese formulario
# describe a una PERSONA (nombres, apellidos, correo, teléfono, afiliado,
# salario, personas a cargo, edad) y un proyecto no tiene ninguno de esos
# datos: son justamente lo que el usuario aporta al otro lado del cruce.
#
# Se respeta el contrato al pie de la letra —las 15 llaves salen, en su orden,
# con los dominios declarados— y las que solo pueden venir del usuario salen
# en null. Así el JSON del proyecto y el del usuario son estructuralmente
# iguales y `modelo.py` puede compararlos campo a campo, que es de lo que se
# trataba. Debajo van los campos que el modelo sí necesita del proyecto
# (dirección, precio, área) y que el formulario no contempla, agrupados
# aparte para que el contrato original se lea limpio.
# ===========================================================================
LLAVES_CONTRATO = (
    "id_proyecto", "nombres", "apellidos", "correo", "telefono", "afiliado",
    "tipo_vivienda", "salario", "personas_a_cargo", "edad", "Localidad",
    "numero_habitaciones", "piso", "zonas_comunes", "link_proyecto",
)


def _a_contrato(registro, id_proyecto):
    """Traduce un registro crudo de cualquier fuente al contrato del modelo."""
    nombres, indices, no_mapeadas = mapear_zonas_comunes(registro["zonas_comunes_raw"])

    return {
        # --- contrato del formulario --------------------------------------
        "id_proyecto": id_proyecto,
        # Datos de la persona: los aporta el usuario, no el proyecto.
        "nombres": None,
        "apellidos": None,
        "correo": None,
        "telefono": None,
        "afiliado": None,
        "tipo_vivienda": tipo_vivienda_codificado(registro["tipo_vivienda_raw"]),
        # salario / personas_a_cargo / edad son el PERFIL OBJETIVO del
        # proyecto: los deriva prep.py del precio y de las amenidades, no se
        # inventan aquí.
        "salario": None,
        "personas_a_cargo": None,
        "edad": None,
        "Localidad": None,          # lo llena asignar_localidades
        "numero_habitaciones": _habitaciones_codificadas(registro["habitaciones_raw"]),
        "piso": PISO_SIN_PREFERENCIA,
        "zonas_comunes": nombres,
        "link_proyecto": registro["link_proyecto"],

        # --- datos del proyecto que el contrato del formulario no cubre ----
        "nombre_proyecto": registro["nombre_proyecto"],
        "constructora": registro["fuente"],
        "direccion": registro["direccion"],
        "precio_desde_cop": registro["precio_desde_cop"],
        "area_desde_m2": registro["area_desde_m2"],
        # Un proyecto VIS es el que da acceso al subsidio de caja, y es lo que
        # prep.py necesita saber para calcular el ingreso requerido con y sin
        # él. Ninguna de las cuatro webs lo publica como campo aparte.
        "aplica_subsidio_caja": tipo_vivienda_codificado(registro["tipo_vivienda_raw"]) == 1,
        "lat": registro["lat"],
        "lon": registro["lon"],
        "imagenes_origen": registro["imagenes"],
        "zonas_comunes_idx": indices,
        "zonas_comunes_no_mapeadas": no_mapeadas,
        "tipo_vivienda_publicado": registro["tipo_vivienda_raw"],
    }


# ---------------------------------------------------------------------------
# Proyectos publicados por dos constructoras
#
# Seis proyectos aparecen dos veces en el catálogo: Constructora Bolívar los
# construye y Colsubsidio los comercializa, cada uno con su ficha y su precio
# (el de Colsubsidio suele ser el de afiliado, más bajo). Álamo Veramonte,
# Austro de Cuatro Vientos, Baviera Park, Novum Ricaurte, Senderos de Fontibón
# y Urbana 30.
#
# Dejarlos separados se ve feo donde más importa: el Top 6 gasta dos casillas
# en el mismo edificio. Se fusionan en un registro que conserva las dos fichas.
# ---------------------------------------------------------------------------
def _clave_identidad(proyecto):
    """Nombre del proyecto reducido a lo comparable."""
    return re.sub(r"[^a-z0-9]+", " ", normalizar_texto(proyecto["nombre_proyecto"])).strip()


def _mismo_proyecto(a, b):
    """¿Son la misma obra publicada por dos constructoras?

    Se exige el mismo nombre Y que las localidades coincidan o sean vecinas.
    Lo segundo no sobra: la dirección que publica cada constructora difiere,
    y Novum Ricaurte cae en Puente Aranda por una y en Los Mártires por la
    otra. Sin ese margen no se fusionaría; sin el límite de un salto, dos
    proyectos distintos con el mismo nombre en extremos opuestos de la ciudad
    se fusionarían por error.
    """
    if a["constructora"] == b["constructora"]:
        return False        # una misma web no se duplica a sí misma
    distancia = distancia_localidades(a["Localidad"], b["Localidad"])
    return distancia is not None and distancia <= 1


def _completitud(proyecto):
    """Cuánto publica esta ficha. Decide cuál de las dos manda en la fusión."""
    return (
        len(proyecto.get("zonas_comunes") or []),
        proyecto.get("numero_habitaciones") is not None,
        len(proyecto.get("imagenes_origen") or []),
        proyecto.get("area_desde_m2") is not None,
    )


def _fusionar(grupo):
    """Combina las fichas de un mismo proyecto en un solo registro."""
    base = dict(max(grupo, key=_completitud))
    otras = [p for p in grupo if p is not max(grupo, key=_completitud)]

    precios = [p["precio_desde_cop"] for p in grupo if p.get("precio_desde_cop")]
    if precios:
        # El precio más bajo es el que de verdad puede pagar el comprador:
        # normalmente es el de Colsubsidio, que es el de afiliado.
        base["precio_desde_cop"] = min(precios)

    habitaciones = [p["numero_habitaciones"] for p in grupo if p.get("numero_habitaciones")]
    if habitaciones:
        base["numero_habitaciones"] = max(habitaciones)

    zonas = list(dict.fromkeys(z for p in grupo for z in (p.get("zonas_comunes") or [])))
    base["zonas_comunes"] = zonas
    base["zonas_comunes_idx"] = sorted({indice_zona(z) for z in zonas} - {None})
    base["zonas_comunes_no_mapeadas"] = sorted(
        {z for p in grupo for z in (p.get("zonas_comunes_no_mapeadas") or [])}
    )
    base["imagenes_origen"] = list(
        dict.fromkeys(u for p in grupo for u in (p.get("imagenes_origen") or []))
    )
    base["aplica_subsidio_caja"] = any(p.get("aplica_subsidio_caja") for p in grupo)

    base["constructoras"] = sorted({p["constructora"] for p in grupo})
    base["links_alternos"] = [p["link_proyecto"] for p in otras if p.get("link_proyecto")]
    base["_fusionado_de"] = len(grupo)
    return base


def fusionar_duplicados(catalogo):
    """Une los proyectos que dos constructoras publican por separado.

    Returns:
        (catalogo_sin_duplicados, [descripción de cada fusión])
    """
    grupos = []             # en el orden en que aparecen, para no barajar el catálogo
    por_clave = {}          # nombre normalizado -> grupos abiertos con ese nombre
    for proyecto in catalogo:
        clave = _clave_identidad(proyecto)
        candidatos = por_clave.setdefault(clave, [])
        for grupo in candidatos:
            if _mismo_proyecto(grupo[0], proyecto):
                grupo.append(proyecto)
                break
        else:
            nuevo = [proyecto]
            candidatos.append(nuevo)
            grupos.append(nuevo)

    salida, fusiones = [], []
    for grupo in grupos:
        if len(grupo) == 1:
            salida.append(grupo[0])
            continue
        fusionado = _fusionar(grupo)
        fusiones.append({
            "nombre_proyecto": fusionado["nombre_proyecto"],
            "constructoras": fusionado["constructoras"],
            "precios": sorted(p["precio_desde_cop"] for p in grupo if p.get("precio_desde_cop")),
            "localidades": sorted({p["localidad_nombre"] for p in grupo}),
        })
        salida.append(fusionado)
    return salida, fusiones


def _reintentar_sin_direccion(crudos):
    """Vuelve a pedir, ya sin concurrencia, las fichas que quedaron sin dirección.

    Bajo carga alguna ficha se cae y el proyecto se quedaría fuera del catálogo
    por un fallo de red, no por sus datos. Son pocas, así que se repiten una a
    una: es la diferencia entre una corrida reproducible y una que devuelve un
    número distinto de proyectos cada vez.
    """
    relectores = {
        "colsubsidio": (_ficha_colsubsidio, "direccion"),
        "bolivar": (_ficha_bolivar, "direccion"),
    }
    pendientes = [
        r for r in crudos
        if not r.get("direccion") and r["fuente"] in relectores and r.get("link_proyecto")
    ]
    if not pendientes:
        return
    print(f"[reintento] {len(pendientes)} fichas sin dirección, se releen una a una")
    for registro in pendientes:
        leer, llave = relectores[registro["fuente"]]
        try:
            detalle = leer(registro["link_proyecto"])
        except Exception as error:
            print(f"  [reintento] {registro['nombre_proyecto']}: {error}")
            continue
        if detalle.get(llave):
            registro["direccion"] = detalle[llave]
            registro["lat"] = registro["lat"] or detalle.get("lat")
            registro["lon"] = registro["lon"] or detalle.get("lon")
            if not registro["zonas_comunes_raw"]:
                registro["zonas_comunes_raw"] = detalle.get("zonas") or []
            if not registro["imagenes"]:
                registro["imagenes"] = detalle.get("imagenes") or []
            print(f"  [reintento] recuperado: {registro['nombre_proyecto']}")


# ---------------------------------------------------------------------------
# E.2 Resolución del barrio (sector catastral)
#
# La localidad decide la ADMISIÓN (el BFS de primer_filtro); el barrio decide
# qué tan cerca queda de verdad. Por eso se resuelve después y subordinado:
# un barrio que contradiga la localidad ya asignada no se acepta.
#
# La mayoría de las direcciones del catálogo son de malla vial ("Calle 235 #
# 52-50") y no nombran barrio, así que la señal principal aquí es la
# COORDENADA —al revés que en la localidad—, con el mismo cuidado: el pin de
# la sala de ventas se descarta si cae fuera de la localidad del proyecto.
# ---------------------------------------------------------------------------
def asignar_barrios(proyectos):
    """Agrega `barrio_id` / `barrio_nombre` a cada proyecto. No muta la entrada.

    Orden de las señales, de más a menos confiable:
        1. la dirección nombra un barrio del grafo dentro de su localidad  (alta)
        2. la coordenada cae en el polígono de un sector de su localidad    (alta)
        3. la coordenada queda a < 1,5 km del centroide de un sector suyo   (media)
        4. la dirección nombra un barrio de una localidad vecina           (media)
        5. nada de lo anterior -> null; el modelo usa solo la localidad

    Sin `barrios_bogota.json` (ver Model/grafo_barrios.py) todos salen en
    null y el recomendador funciona igual que en la v0.3.
    """
    resueltos = []
    for proyecto in proyectos:
        copia = dict(proyecto)
        localidad = copia.get("Localidad")
        veredicto = {"barrio": None, "nombre": None, "confianza": None,
                     "evidencia": "sin grafo de barrios" if not hay_grafo_barrios() else None}
        if hay_grafo_barrios() and localidad is not None:
            direccion = _primer_valor(copia, _LLAVES_DIRECCION)
            por_nombre = barrio_desde_direccion(direccion, localidad)
            if por_nombre["barrio"] and por_nombre["confianza"] == "alta":
                veredicto = por_nombre
            else:
                lat, lon = _primer_valor(copia, _LLAVES_LAT), _primer_valor(copia, _LLAVES_LON)
                por_geo = {"barrio": None}
                try:
                    if lat is not None and lon is not None:
                        por_geo = barrio_desde_coordenadas(float(lat), float(lon), localidad)
                except (TypeError, ValueError):
                    pass
                if por_geo["barrio"]:
                    veredicto = por_geo
                elif por_nombre["barrio"]:
                    veredicto = por_nombre
                else:
                    veredicto = dict(por_nombre, evidencia="ni la direccion ni la coordenada ubican un sector")
        copia["barrio_id"] = veredicto["barrio"]
        copia["barrio_nombre"] = veredicto["nombre"]
        copia["_barrio_confianza"] = veredicto["confianza"]
        copia["_barrio_evidencia"] = veredicto["evidencia"]
        resueltos.append(copia)
    return resueltos


def construir_catalogo(fuentes=None, usar_coordenadas=True):
    """Corre los scrapers pedidos, asigna localidad y numera los proyectos.

    Los proyectos que no quedan dentro de Bogotá D.C. se descartan: el modelo
    solo recomienda sobre las 20 localidades del grafo, y Cusezar y Bolívar
    mezclan municipios del área metropolitana en sus listados.

    Returns:
        (catalogo, descartados, fusiones)
    """
    fuentes = fuentes or list(FUENTES)
    crudos = []
    for nombre in fuentes:
        scraper = FUENTES.get(nombre)
        if not scraper:
            print(f"[aviso] fuente desconocida: {nombre}")
            continue
        try:
            crudos += scraper()
        except Exception as error:
            print(f"[error] {nombre} falló: {error}")

    _reintentar_sin_direccion(crudos)

    descartados = []
    residenciales = []
    for registro in crudos:
        if _es_residencial(registro):
            residenciales.append(registro)
        else:
            descartados.append({
                "nombre_proyecto": registro["nombre_proyecto"],
                "constructora": registro["fuente"],
                "direccion": registro["direccion"],
                "motivo": "no es un proyecto de vivienda",
            })

    # Se numera después de resolver la localidad para que los ids queden
    # consecutivos sobre los proyectos que de verdad entran al catálogo.
    provisionales = [_a_contrato(r, None) for r in residenciales]
    resueltos = asignar_localidades(provisionales, usar_coordenadas=usar_coordenadas)

    catalogo = []
    for proyecto in resueltos:
        if proyecto["Localidad"] is None:
            descartados.append({
                "nombre_proyecto": proyecto["nombre_proyecto"],
                "constructora": proyecto["constructora"],
                "direccion": proyecto["direccion"],
                "motivo": proyecto["_localidad_evidencia"],
            })
            continue
        catalogo.append(proyecto)

    catalogo, fusiones = fusionar_duplicados(catalogo)
    catalogo = asignar_barrios(catalogo)

    # Orden estable: por constructora y nombre, para que dos corridas seguidas
    # produzcan los mismos ids mientras el catálogo publicado no cambie.
    catalogo.sort(key=lambda p: (p["constructora"], normalizar_texto(p["nombre_proyecto"])))
    for numero, proyecto in enumerate(catalogo, start=1):
        proyecto["id_proyecto"] = numero

    return catalogo, descartados, fusiones


# ===========================================================================
# F. Imágenes
# ===========================================================================
_EXTENSIONES = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
    "image/gif": ".gif", "image/avif": ".avif",
}

# Una imagen es opcional: si el servidor la está sirviendo lento, insistir con
# el backoff largo de las fichas deja la descarga entera colgada minutos por
# un solo archivo. Se falla rápido y se sigue.
TIMEOUT_IMAGEN = 25
REINTENTOS_IMAGEN = 2


def _extension(url, content_type):
    """Extensión del archivo, prefiriendo la que declara el servidor."""
    por_tipo = _EXTENSIONES.get((content_type or "").split(";")[0].strip().lower())
    if por_tipo:
        return por_tipo
    ruta = unquote(urlparse(url).path)
    extension = os.path.splitext(ruta)[1].lower()
    return extension if extension in _EXTENSIONES.values() else ".jpg"


def descargar_imagenes(catalogo, destino=DIR_IMAGENES, rehacer=False):
    """Baja las imágenes de cada proyecto a `imagenes_proyectos/<id>/`.

    Una carpeta por proyecto, nombrada con su id, tal como pide el encargo.
    Las imágenes se numeran en el orden en que las publica la fuente, así que
    la primera es siempre la de portada.

    Args:
        rehacer: por defecto se omite el proyecto cuya carpeta ya tiene tantos
            archivos como imágenes publica la fuente. Bajar ~2.000 imágenes
            toma media hora; si una corrida se corta a la mitad, repetirla no
            debería empezar de cero.

    Returns:
        dict {id_proyecto: cantidad de imágenes descargadas}
    """
    os.makedirs(destino, exist_ok=True)
    conteo = {}

    def _bajar(proyecto):
        id_proyecto = proyecto["id_proyecto"]
        carpeta = os.path.join(destino, str(id_proyecto))
        urls = proyecto.get("imagenes_origen") or []
        if not rehacer and os.path.isdir(carpeta) and len(os.listdir(carpeta)) >= len(urls):
            return id_proyecto, len(os.listdir(carpeta))
        os.makedirs(carpeta, exist_ok=True)
        guardadas = 0
        for posicion, url in enumerate(urls, start=1):
            try:
                respuesta = _get(
                    url, timeout=TIMEOUT_IMAGEN, reintentos=REINTENTOS_IMAGEN
                )
                nombre = f"{posicion:02d}{_extension(url, respuesta.headers.get('Content-Type'))}"
                with open(os.path.join(carpeta, nombre), "wb") as archivo:
                    archivo.write(respuesta.content)
                guardadas += 1
            except Exception as error:
                print(f"  [imagen] {id_proyecto} no pudo bajar {url[:80]}: {error}")
        return id_proyecto, guardadas

    with ThreadPoolExecutor(max_workers=HILOS) as pool:
        for id_proyecto, guardadas in pool.map(_bajar, catalogo):
            conteo[id_proyecto] = guardadas

    total = sum(conteo.values())
    print(f"[imagenes] {total} archivos en {len(conteo)} carpetas bajo {destino}")
    return conteo


# ===========================================================================
# G. CLI
# ===========================================================================
def _resumen(catalogo, descartados, fusiones=()):
    """Reporte de lo que quedó, para poder revisar el catálogo de un vistazo."""
    por_fuente, por_localidad, por_confianza = {}, {}, {}
    sin_zonas = sin_habitaciones = sin_tipo = 0
    for proyecto in catalogo:
        por_fuente[proyecto["constructora"]] = por_fuente.get(proyecto["constructora"], 0) + 1
        nombre = proyecto["localidad_nombre"]
        por_localidad[nombre] = por_localidad.get(nombre, 0) + 1
        confianza = proyecto["_localidad_confianza"]
        por_confianza[confianza] = por_confianza.get(confianza, 0) + 1
        sin_zonas += not proyecto["zonas_comunes"]
        sin_habitaciones += proyecto["numero_habitaciones"] is None
        sin_tipo += proyecto["tipo_vivienda"] is None

    print("\n=== Catálogo ===")
    print(f"proyectos: {len(catalogo)}   descartados: {len(descartados)}")
    print("por constructora:", dict(sorted(por_fuente.items())))
    print("por confianza de localidad:", dict(sorted(por_confianza.items(), key=lambda kv: str(kv[0]))))
    print("por localidad:")
    for nombre, cantidad in sorted(por_localidad.items(), key=lambda kv: -kv[1]):
        print(f"   {cantidad:3d}  {nombre}")
    print(f"sin zonas comunes: {sin_zonas} | sin habitaciones: {sin_habitaciones} | sin tipo: {sin_tipo}")
    if fusiones:
        print(f"\nfusionados (misma obra publicada por dos constructoras): {len(fusiones)}")
        for f in fusiones:
            precios = " / ".join(f"${p:,.0f}".replace(",", ".") for p in f["precios"])
            print(f"   {f['nombre_proyecto'][:38]:38} {'+'.join(f['constructoras'])}  {precios}")
    if descartados:
        print("\ndescartados (fuera de Bogotá o sin dirección utilizable):")
        for item in descartados:
            print(f"   [{item['constructora']}] {item['nombre_proyecto']} -> {item['motivo']}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Construye el catálogo de proyectos de vivienda de Bogotá D.C."
    )
    parser.add_argument(
        "--fuente", nargs="+", choices=sorted(FUENTES), default=sorted(FUENTES),
        help="constructoras a consultar (por defecto, las cuatro)",
    )
    parser.add_argument("--salida", default=RUTA_SALIDA, help="ruta del JSON de salida")
    parser.add_argument(
        "--no-imagenes", action="store_true", help="no descargar las imágenes"
    )
    parser.add_argument(
        "--rehacer-imagenes", action="store_true",
        help="volver a bajar las imágenes que ya están en disco",
    )
    parser.add_argument(
        "--sin-coordenadas", action="store_true",
        help="resolver la localidad solo con la dirección, sin los límites oficiales",
    )
    parser.add_argument(
        "--solo-barrios", action="store_true",
        help="no scrapear: releer el catálogo ya guardado y (re)asignar el barrio a cada proyecto",
    )
    args = parser.parse_args(argv)

    if args.solo_barrios:
        return _reasignar_barrios(args.salida)

    catalogo, descartados, fusiones = construir_catalogo(
        fuentes=args.fuente, usar_coordenadas=not args.sin_coordenadas
    )
    if not catalogo:
        print("No se obtuvo ningún proyecto.")
        return 1

    salida = {
        "meta": {
            "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fuentes": args.fuente,
            "n_proyectos": len(catalogo),
            "n_descartados": len(descartados),
            "n_fusionados": len(fusiones),
            "localidades_bogota": list(LOCALIDADES_BOGOTA),
            "zonas_comunes": list(ZONAS_COMUNES),
            "contrato": list(LLAVES_CONTRATO),
        },
        "proyectos": catalogo,
        "descartados": descartados,
        "fusionados": fusiones,
    }
    with open(args.salida, "w", encoding="utf-8") as archivo:
        json.dump(salida, archivo, ensure_ascii=False, indent=2)
    print(f"\n[salida] {args.salida}")

    if not args.no_imagenes:
        descargar_imagenes(catalogo, rehacer=args.rehacer_imagenes)

    _resumen(catalogo, descartados, fusiones)
    return 0


def _reasignar_barrios(ruta):
    """Vuelve a resolver el barrio sobre el catálogo en disco, sin scrapear.

    Es lo que hay que correr cuando cambia el grafo de barrios y no el
    catálogo: no toca ids, localidades ni imágenes.
    """
    with open(ruta, "r", encoding="utf-8") as archivo:
        salida = json.load(archivo)
    salida["proyectos"] = asignar_barrios(salida["proyectos"])
    salida.setdefault("meta", {})["barrios_asignados_en"] = (
        datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(salida, archivo, ensure_ascii=False, indent=2)

    por_confianza = {}
    for proyecto in salida["proyectos"]:
        clave = proyecto.get("_barrio_confianza") or "sin barrio"
        por_confianza[clave] = por_confianza.get(clave, 0) + 1
    print(f"[barrios] {len(salida['proyectos'])} proyectos -> {ruta}")
    print(f"[barrios] por confianza: {por_confianza}")
    for proyecto in salida["proyectos"]:
        print(f"  {proyecto['id_proyecto']:>3} {proyecto['localidad_nombre']:<18} "
              f"{(proyecto.get('barrio_nombre') or '-'):<28} {proyecto.get('_barrio_evidencia')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
