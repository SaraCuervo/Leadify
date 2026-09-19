"""
catalogos.py
============
Catálogos canónicos y utilidades compartidas por `prep.py` y `modelo.py`.

Los índices de `ZONAS_COMUNES` (0..24) y los ids de `LOCALIDADES_BOGOTA` (1..20)
viajan dentro de `proyectos_model.json` y del perfil del usuario. Si cada módulo
definiera su propia copia de estas listas, cualquier desfase produciría cruces
silenciosamente incorrectos, por eso viven en un único lugar.
"""

from __future__ import annotations

import unicodedata
from collections import deque
from functools import lru_cache

# ---------------------------------------------------------------------------
# Localidades de Bogotá
# El id oficial va de 1 a 20; el índice dentro de la lista es (id - 1).
# ---------------------------------------------------------------------------
LOCALIDADES_BOGOTA = [
    "Usaquén",              # 1
    "Chapinero",            # 2
    "Santa Fe",             # 3
    "San Cristóbal",        # 4
    "Usme",                 # 5
    "Tunjuelito",           # 6
    "Bosa",                 # 7
    "Kennedy",              # 8
    "Fontibón",             # 9
    "Engativá",             # 10
    "Suba",                 # 11
    "Barrios Unidos",       # 12
    "Teusaquillo",          # 13
    "Los Mártires",         # 14
    "Antonio Nariño",       # 15
    "Puente Aranda",        # 16
    "La Candelaria",        # 17
    "Rafael Uribe Uribe",   # 18
    "Ciudad Bolívar",       # 19
    "Sumapaz",              # 20
]

# ---------------------------------------------------------------------------
# Zonas comunes / amenidades
# El índice dentro de la lista (0..24) es el identificador usado por el modelo.
# ---------------------------------------------------------------------------
ZONAS_COMUNES = [
    "Lobby",                 # 0
    "Piscina",               # 1
    "Zona de lavandería",    # 2
    "Zona BBQ",              # 3
    "Zona pet",              # 4
    "Zona kids",             # 5
    "Locales comerciales",   # 6
    "Zona fitness",          # 7
    "Salón social",          # 8
    "Spa mascotas",          # 9
    "Zona cool",             # 10
    "Zona cine",             # 11
    "Coworking",             # 12
    "Sala VIP",              # 13
    "Zona café",             # 14
    "Gimnasio",              # 15
    "Parqueadero",           # 16
    "Zona verde",            # 17
    "Parque",                # 18
    "Sala de juegos",        # 19
    "Pista de trote",        # 20
    "Voleibol playa",        # 21
    "Cancha de pádel",       # 22
    "Taller de bicicletas",  # 23
    "Sauna",                 # 24
]

# ---------------------------------------------------------------------------
# Grafo urbano G = (V, E, W): localidades colindantes, todas con peso 1.
# Se declara la adyacencia tal cual fue especificada y luego se simetriza,
# de modo que el grafo sea no dirigido aunque la declaración tenga omisiones.
# ---------------------------------------------------------------------------
_ADYACENCIA_DECLARADA = {
    1:  [11, 2],
    2:  [1, 12, 13, 3],
    3:  [2, 13, 14, 17, 4],
    4:  [3, 17, 15, 18, 5],
    5:  [4, 18, 6, 19, 20],
    6:  [16, 15, 18, 5, 19, 8],
    7:  [8, 19],
    8:  [9, 16, 6, 19, 7],
    9:  [10, 13, 16, 8],
    10: [11, 12, 13, 9],
    11: [1, 12, 10],
    12: [11, 2, 13, 10],
    13: [12, 2, 3, 14, 16, 9, 10],
    14: [13, 3, 17, 15, 16],
    15: [14, 4, 18, 6, 16],
    16: [13, 14, 15, 6, 8, 9],
    17: [3, 4, 14],
    18: [15, 4, 5, 6],
    19: [7, 8, 6, 5, 20],
    20: [5, 19],
}


def _construir_grafo(adyacencia):
    """Devuelve el grafo como dict{id: set(ids)}, garantizando simetría."""
    grafo = {localidad: set() for localidad in range(1, len(LOCALIDADES_BOGOTA) + 1)}
    for origen, vecinos in adyacencia.items():
        for vecino in vecinos:
            grafo[origen].add(vecino)
            grafo[vecino].add(origen)  # arista no dirigida
    return {k: sorted(v) for k, v in grafo.items()}


GRAFO_LOCALIDADES = _construir_grafo(_ADYACENCIA_DECLARADA)

# Peso uniforme de las aristas (queda explícito para futuras variantes que
# quieran ponderar por distancia real o tiempo de desplazamiento).
PESO_ARISTA = 1


# ---------------------------------------------------------------------------
# Normalización de texto
# ---------------------------------------------------------------------------
def normalizar_texto(valor) -> str:
    """Minúsculas, sin tildes, sin signos de separación y sin espacios dobles."""
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor).strip().lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    for signo in ("_", "-", ".", "/"):
        texto = texto.replace(signo, " ")
    return " ".join(texto.split())


# ---------------------------------------------------------------------------
# Resolución de localidades
# ---------------------------------------------------------------------------
_LOCALIDAD_POR_NOMBRE = {
    normalizar_texto(nombre): idx + 1 for idx, nombre in enumerate(LOCALIDADES_BOGOTA)
}
# Variantes frecuentes en fuentes externas.
_LOCALIDAD_POR_NOMBRE.update({
    "santafe": 3,
    "san cristobal sur": 4,
    "candelaria": 17,
    "la candelaria bogota": 17,
    "martires": 14,
    "rafael uribe": 18,
    "ciudad bolivar bogota": 19,
})


def indice_localidad(valor):
    """Convierte un id (1..20) o un nombre de localidad en su id oficial.

    Devuelve None si no se puede resolver.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)) and float(valor).is_integer():
        entero = int(valor)
        return entero if 1 <= entero <= len(LOCALIDADES_BOGOTA) else None
    texto = normalizar_texto(valor)
    if not texto:
        return None
    if texto.isdigit():
        entero = int(texto)
        return entero if 1 <= entero <= len(LOCALIDADES_BOGOTA) else None
    return _LOCALIDAD_POR_NOMBRE.get(texto)


def nombre_localidad(id_localidad):
    """Nombre oficial a partir del id 1..20."""
    if id_localidad is None or not (1 <= id_localidad <= len(LOCALIDADES_BOGOTA)):
        return None
    return LOCALIDADES_BOGOTA[id_localidad - 1]


# ---------------------------------------------------------------------------
# Resolución de zonas comunes
# ---------------------------------------------------------------------------
_ZONA_POR_NOMBRE = {
    normalizar_texto(nombre): idx for idx, nombre in enumerate(ZONAS_COMUNES)
}
# Alias observados en `proyectos_seed.json` y en formularios de captura.
# Se resuelven de forma explícita (nada de coincidencias difusas) para que una
# amenidad desconocida se reporte en lugar de mapearse por error.
_ZONA_POR_NOMBRE.update({
    "zona kid": 5,
    "zona kids infantil": 5,
    "zona ninos": 5,
    "zona lavanderia": 2,
    "lavanderia": 2,
    "bbq": 3,
    "zona de bbq": 3,
    "zona mascotas": 4,
    "salon comunal": 8,
    "spa de mascotas": 9,
    "zona de cine": 11,
    "sala vip 2": 13,
    "zona cafe bar": 14,
    "gymnasio": 15,       # errata presente en el seed
    "gimnacio": 15,
    "gym": 15,
    "parqueaderos": 16,
    "zonas verdes": 17,
    "parques": 18,
    "salon de juegos": 19,
    "zona de juegos": 19,
    "pista trote": 20,
    "voleibol de playa": 21,
    "volleyball playa": 21,
    "voley playa": 21,
    "cancha e padel": 22,  # errata presente en el seed
    "cancha padel": 22,
    "cancha de padel": 22,
    "padel": 22,
    "taller de bicicleta": 23,
    "taller bicicletas": 23,
})


def indice_zona(valor):
    """Convierte un índice (0..24) o un nombre de zona común en su índice.

    Devuelve None si no se puede resolver.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)) and float(valor).is_integer():
        entero = int(valor)
        return entero if 0 <= entero < len(ZONAS_COMUNES) else None
    texto = normalizar_texto(valor)
    if not texto:
        return None
    return _ZONA_POR_NOMBRE.get(texto)


def mapear_zonas(valor):
    """Mapea una colección de zonas comunes a índices.

    Acepta list/tuple/set de strings o enteros, o un único string con los
    nombres separados por comas (formato del formulario de usuario).

    Returns:
        (indices_ordenados_sin_repetir, tokens_no_reconocidos)
    """
    if valor is None:
        return [], []
    if isinstance(valor, str):
        crudos = [parte for parte in valor.split(",") if parte.strip()]
    elif isinstance(valor, (list, tuple, set)):
        crudos = list(valor)
    else:
        crudos = [valor]

    indices, desconocidos = set(), []
    for crudo in crudos:
        idx = indice_zona(crudo)
        if idx is None:
            texto = str(crudo).strip()
            if texto:
                desconocidos.append(texto)
        else:
            indices.add(idx)
    return sorted(indices), desconocidos


def vector_zonas(indices):
    """Vector binario de 25 posiciones (one-hot múltiple) para clustering."""
    vector = [0] * len(ZONAS_COMUNES)
    for idx in indices:
        if 0 <= idx < len(ZONAS_COMUNES):
            vector[idx] = 1
    return vector


def nombres_zonas(indices):
    """Nombres canónicos a partir de una lista de índices."""
    return [ZONAS_COMUNES[i] for i in indices if 0 <= i < len(ZONAS_COMUNES)]


# ---------------------------------------------------------------------------
# Tipo de vivienda
# ---------------------------------------------------------------------------
def codigo_tipo_vivienda(valor):
    """Normaliza el tipo de vivienda a 1 = VIS, 0 = No VIS. None si es ambiguo."""
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, (int, float)) and float(valor).is_integer():
        entero = int(valor)
        return entero if entero in (0, 1) else None
    texto = normalizar_texto(valor)
    if texto in ("vis", "1", "si", "true"):
        return 1
    if texto in ("no vis", "novis", "0", "no", "false"):
        return 0
    return None


def nombre_tipo_vivienda(codigo):
    """Etiqueta legible del tipo de vivienda."""
    return {1: "VIS", 0: "No VIS"}.get(codigo)


# ---------------------------------------------------------------------------
# Recorridos sobre el grafo urbano
# ---------------------------------------------------------------------------
@lru_cache(maxsize=256)
def _bfs_niveles(origen, distancia_maxima):
    """BFS cacheado. Devuelve una estructura inmutable: el grafo no cambia."""
    niveles = {0: [origen]}
    visitados = {origen}
    cola = deque([(origen, 0)])
    while cola:
        actual, distancia = cola.popleft()
        if distancia_maxima is not None and distancia >= distancia_maxima:
            continue
        for vecino in GRAFO_LOCALIDADES.get(actual, []):
            if vecino in visitados:
                continue
            visitados.add(vecino)
            niveles.setdefault(distancia + PESO_ARISTA, []).append(vecino)
            cola.append((vecino, distancia + PESO_ARISTA))
    return tuple((d, tuple(sorted(ids))) for d, ids in sorted(niveles.items()))


def localidades_por_distancia(origen, distancia_maxima=None):
    """BFS por niveles desde `origen`.

    Returns:
        dict{distancia: [ids de localidad]}, con distancia 0 = la propia
        localidad de origen. Al tener todas las aristas peso 1, el número de
        saltos del BFS es la distancia mínima del grafo. Se devuelve una copia
        mutable nueva en cada llamada: el cálculo se cachea, el resultado no
        se comparte.
    """
    origen = indice_localidad(origen)
    if origen is None:
        return {}
    return {d: list(ids) for d, ids in _bfs_niveles(origen, distancia_maxima)}


def orden_expansion(origen, distancia_maxima=None):
    """Lista plana [(id_localidad, distancia), ...] ordenada por cercanía."""
    niveles = localidades_por_distancia(origen, distancia_maxima)
    return [(loc, dist) for dist, ids in niveles.items() for loc in ids]


def distancia_localidades(origen, destino):
    """Saltos mínimos entre dos localidades. None si alguna no se resuelve."""
    origen, destino = indice_localidad(origen), indice_localidad(destino)
    if origen is None or destino is None:
        return None
    for distancia, ids in localidades_por_distancia(origen).items():
        if destino in ids:
            return distancia
    return None
