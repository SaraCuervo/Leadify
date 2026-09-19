#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Trocea los planos oficiales de cada tipologia para que el quiz pueda ARMARLOS
por partes. Uso:

    pip install pillow
    python tools/analizar_planos.py                 # escribe js/planos.js
    python tools/analizar_planos.py --limite 12     # pruebas
    python tools/analizar_planos.py --detalle       # una linea por plano

QUE PROBLEMA RESUELVE
---------------------
El quiz construye una vivienda mientras el usuario responde. Antes dibujaba un
esquema generado (rectangulos con muebles pintados a mano) y se veia justamente
como lo que era: un esquema. Ahora arma el PLANO REAL de la ficha -con muebles
renderizados, texturas y muros gruesos- pieza a pieza.

Para eso hay que saber POR DONDE cortar la imagen. Este script lo calcula una
vez, offline, y lo deja en js/planos.js.

COMO SE CORTA (y por que asi)
-----------------------------
1. RECUADRO DE CONTENIDO. No basta `getbbox()` sobre la mascara de tinta: varios
   planos traen un inserto suelto (calia-etapa-1-tipo-2 tiene un recuadro
   punteado a la izquierda con una distribucion alternativa) y el bbox se lo
   traga entero -ratio 1,89 cuando el apartamento real ocupa el 60% derecho, y
   al trocearlo salen celdas de puro blanco. Por eso se toma la COMPONENTE
   CONEXA MAYOR de la tinta y se descarta el resto. Lo que se descarta se anota
   como `islas`, que luego sirve de filtro.

2. MUROS POR PERFIL DE PROYECCION. Se cuentan los pixeles muy oscuros (<90) por
   columna y por fila dentro del recuadro, y se toman los picos mas fuertes.
   Verificado a ojo contra las imagenes: en acanto-tipo-c-1 el corte vertical al
   84% es la pared antes de "Cocina-Ropas" y el del 58% separa "Alcoba 3" de
   "Sala-Comedor"; en urbania-bio-tipo-b-1 el horizontal al 51% es la pared
   entre las alcobas de arriba y el bano/cocina de abajo.

   No se intenta afinar esto con mas heuristica. Un mueble oscuro puede ganarle
   a un muro y partir una cama por la mitad; eso se resuelve VETANDO el plano a
   mano (ver VETADOS), no ajustando el detector sobre 150 imagenes que nadie va
   a poder verificar una por una.

3. ORDEN DE REVELACION POR ADYACENCIA, desde el centro de masa hacia afuera. Es
   lo que garantiza que el plano a medias sea siempre una MANCHA CONEXA. Por
   area descendente salen islas flotando en el aire -el peor fallo visual
   posible aqui-, y por posicion se lee como un escaner y depende de como este
   orientado el plano, que es arbitrario entre proyectos.

RENDIMIENTO
-----------
Nada de bucles de pixeles en Python puro: un plano tardaba ~2,5 s. PIL sola
basta -`resize((w,1), BOX)` devuelve la proyeccion vertical en C, y
`ImageStat` la densidad de una celda-. Los 150 salen en segundos.
"""

from __future__ import annotations

import argparse
import itertools
import os
import re
import sys

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover
    print("Falta Pillow:  pip install pillow")
    sys.exit(1)

AQUI = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(AQUI)
FUENTE_JS = os.path.join(APP, "js", "proyectos.js")
SALIDA_JS = os.path.join(APP, "js", "planos.js")

# --- parametros del troceado -------------------------------------------------
CORTES_X = 3          # -> 4 columnas
CORTES_Y = 2          # -> 3 filas
MARGEN = 0.12         # no se corta en el 12% de los bordes (ahi esta la fachada)
SEPARACION = 0.12     # dos cortes no pueden estar mas juntos que esto
UMBRAL_TINTA = 235    # por debajo de esto, el pixel es contenido y no papel
UMBRAL_MURO = 90      # por debajo de esto, el pixel es muro
# Una celda por debajo de esta densidad es casi todo papel: no merece ser una
# pieza. Es el unico parametro que conviene ajustar MIRANDO la hoja de contactos
# (#debug-planos) y no la estadistica: subirlo deja mordiscos en la silueta
# donde habia un pedacito de balcon.
#
# SUBIO DE 0,30 A 0,55, y ese mordisco pasó de efecto secundario a ser el punto.
# Es lo que permitio abrir el sorteo del quiz a los 36 planos APTOS (16
# proyectos) en vez de solo a los 23 rectangulares (8 proyectos) — que es lo que
# hace que el plano de la escena pueda perseguir al proyecto #1 del ranking.
#
# El problema de los 13 planos no rectangulares nunca fue su forma: la silueta
# YA sigue la huella real de cada plano (planta.js filtra las celdas por este
# mismo umbral y reconstruirPlano la repinta entera en cada cambio). Era la
# BANDA INTERMEDIA. De sus 156 celdas, 11 estaban por debajo de 0,30 —o sea que
# ya eran mordisco— y 111 por encima de 0,60; pero **34 caian entre 0,30 y
# 0,59**: se dibujaban como pieza siendo casi todo papel, y en el plano armado
# se leen como piezas que faltan. Con 0,55 esas 34 pasan a ser mordiscos y el
# apartamento ensena su contorno real en L o en U.
#
# 0,55 y no mas: NINGUNO de los 23 planos rectangulares tiene una sola celda por
# debajo de ese valor, asi que quedan intactos, y los 13 nuevos se quedan con
# 8-12 celdas (el minimo es UTILES_MIN=8) y densidad media 0,79-0,91. A 0,58 un
# plano cae por debajo de 8 celdas y a 0,60 caen tres.
UMBRAL_CELDA = 0.55
# Por debajo de esto una celda se ve como PAPEL EN BLANCO dentro del plano ya
# armado, o sea como una pieza que falta. Hace dos cosas: dispara la busqueda
# de otros cortes en elegir_cortes() (ver alla), y es el minimo que se le exige
# a un plano para entrar al sorteo del quiz (UMBRAL_RECT).
#
# 0,70 se midio A OJO sobre la pantalla, no por estadistica. Con 0,55 el plano
# terminado seguia enseñando dos bloques blancos del tamano exacto de una celda
# -en una pantalla grande se leen como piezas que faltan, que es justo lo que
# no puede pasar en la ultima pregunta-. Subirlo deja el sorteo en 10 planos
# (cobertura 2/5/3 alcobas); mas arriba se rompe la cobertura de 1 alcoba.
UMBRAL_CELDA_MINIMA = 0.70
# Para considerar un plano RECTANGULAR (huella que llena su recuadro, sin
# esquinas vacias) se le pide a TODAS sus celdas al menos esta densidad.
#
# Historia, porque el numero se movio tres veces: estuvo en 0,40; bajo a 0,25
# al vetar los planos con ROTULOS IMPRESOS (los dos unicos rectangulares de
# tres alcobas los llevaban y el sorteo se quedaba sin con que atender a quien
# pide tres); y con eso se colaron celdas al 26%, que en el plano armado se
# ven como PIEZAS QUE FALTAN. La solucion no fue mover mas el umbral sino
# arreglar la causa —donde caen los cortes, ver elegir_cortes()—, y con eso
# se pudo exigir que ninguna celda quede floja (0,70).
#
# AHORA ESTA DESACOPLADO de UMBRAL_CELDA_MINIMA y vale 0,60. El motivo no es
# estetico sino de MATCH: con 0,70 el sorteo se quedaba en 10 planos y solo DOS
# eran VIS, asi que a quien elegia VIS —el caso comun en una demo de vivienda
# subsidiada— la escena solo podia ensenarle uno de dos apartamentos, eligiera
# la localidad que eligiera. Con 0,60 el sorteo pasa a 23 planos y 6 VIS, y la
# cobertura por alcobas de 2/5/3 a 3/11/9.
#
# Lo que se acepta a cambio: alguna celda al 60% en vez de al 70%. Se puede
# porque el papel blanco YA no se ve —lo resuelve el 
# de .gdf-room, no este umbral (ver la seccion de templates.js en CLAUDE.md)—;
# el umbral solo gobierna cuanto de rectangular se ve la silueta.
UMBRAL_RECT = 0.60

# --- filtros de aptitud ------------------------------------------------------
# Un plano "apto" es el que se puede usar para la animacion del quiz. Los que no
# pasan siguen en el archivo (por si acaso), pero fuera de GDF_PLANOS_APTOS.
RATIO_MIN, RATIO_MAX = 0.85, 1.75   # 0,66 en una escena de 180px deja 119px de ancho
# Tinta fuera de la componente conexa mayor, o sea un inserto suelto.
#
# NO LO SUBAS PARA RECUPERAR CALIA. Los tres planos planos de Calia
# (calia-etapa-1-tipo-{2,3,a}-1) caen justo aqui, con 15-17 %, y montados en la
# escena se ven de maravilla: 12/12 celdas, sin rotulos. Es tentador. Pero
# llevan impresa una LINEA DE SECCION ROJA DISCONTINUA que cruza la lamina de
# lado a lado (mas un punto rojo): es la guia que apunta al inserto, y en el
# apartamento armado se lee como lo que es, la anotacion de un plano tecnico.
# Misma familia que los rotulos impresos, mismo veredicto.
ISLAS_MAX = 0.06
UTILES_MIN = 7                      # hay 7 preguntas; una por lo menos cada una
DENSIDAD_MEDIA_MIN = 0.55

# Vetos a mano, tras mirar la hoja de contactos. Van AQUI y no en el archivo
# generado, para que js/planos.js siga siendo 100% generado y la curacion quede
# versionada junto al criterio que la motivo.
# CURADURIA A OJO. No hay forma automatica de saber si una lamina es un render
# isometrico o si lleva rotulos impresos encima ("Alcoba 2 · 2.35 x 2.25"), y
# las dos cosas estropean la escena: el isometrico es un rombo dentro de un
# recuadro —la silueta gris prometeria una forma que no es— y los rotulos
# quedan partidos por las costuras del troceado.
#
# Asi que TODA lamina que entre al sorteo hay que MIRARLA MONTADA. La hoja de
# contactos la genera:  python plataforma/tools/hoja_planos.py
#
# Revisadas las 25 que pasan los filtros automaticos, sobre la hoja de
# contactos. Se cae MAS DE LA MITAD, y no por poco: son fallos que ningun
# umbral de densidad o de ratio puede ver.
VETADOS: dict = {
    # Renders 3D. El apartamento es un volumen en perspectiva dentro de un
    # recuadro: la silueta gris prometeria una forma que no es, y al trocearlo
    # las paredes en perspectiva quedan cortadas por la mitad.
    "assets/planos/bolivar-43-3.webp": "render isometrico 3D",
    "assets/planos/colsubsidio-70-1.webp": "render isometrico 3D (obra gris)",

    # NO SON PLANOS. El nombre del archivo decia "planta" o "tipologia" y son
    # otra cosa. Es exactamente por esto que hay que mirarlas: el filtro por
    # nombre de archivo se equivoca, y estas dos pasaron ademas todos los
    # filtros de forma y densidad.
    "assets/planos/bolivar-46-10.webp": "es una FOTO de una cocina, no un plano",
    "assets/planos/bolivar-50-7.webp": "es una FOTO de una cocina, no un plano",
    "assets/planos/colsubsidio-82-1.webp": "planta URBANA (calles, Avenida Caracas)",

    # Rotulos impresos sobre el plano. La gracia de la escena es que el
    # apartamento se lea como un espacio que se arma, no que venga con las
    # respuestas escritas encima; y al trocearlo los rotulos quedan partidos
    # por las costuras. No se intenta borrarlos: no hay forma de rellenar el
    # suelo de debajo sin que se note el parche.
    "assets/planos/colsubsidio-60-1.webp": "rotulos impresos (APTO TIPO 1, Habitacion, Bano)",
    "assets/planos/colsubsidio-61-1.webp": "rotulos impresos con medidas",
    "assets/planos/colsubsidio-64-1.webp": "rotulos impresos con medidas",
    "assets/planos/colsubsidio-67-1.webp": "rotulos impresos con medidas",
    "assets/planos/colsubsidio-81-1.webp": "rotulos impresos con medidas",
    "assets/planos/cusezar-83-1.png": "rotulos impresos (Terraza, Alcoba 1, Acceso)",
    "assets/planos/bolivar-51-1.webp": "banda de texto: 'lo recibes sin acabados'",

    # Fondo de color a toda la lamina. Las piezas van en `mix-blend-mode:
    # multiply` para que el papel blanco desaparezca contra el fondo de la
    # escena; un beige no desaparece, y el plano sale con un rectangulo de
    # color alrededor.
    "assets/planos/colsubsidio-65-1.webp": "fondo beige a toda la lamina",

    # Casi todo suelo vacio: al armarse se lee como celdas que faltan.
    "assets/planos/colsubsidio-68-3.webp": "apenas amueblado, mucho suelo vacio",
}

# VETO POR PROYECTO, y no por lamina, para no jugar al topo.
#
# Vetar una lamina hace que el analizador promueva la SIGUIENTE del mismo
# proyecto, y en estos once la siguiente fallaba por lo mismo: quien imprime
# rotulos sobre el plano los imprime en todos, quien publica el fondo beige lo
# publica en toda la serie, y el proyecto cuyas "plantas" son fotos de la
# cocina tiene fotos y no plantas. Es un defecto del ESTILO de la ficha, no de
# la lamina suelta.
#
# Revisadas dos rondas de hoja de contactos por cada uno.
PROYECTOS_VETADOS = {
    43: "renders isometricos 3D",
    50: "sus 'plantas' son fotos de interiores",
    51: "sus 'plantas' son fotos de interiores",
    60: "rotulos impresos en toda la serie",
    61: "rotulos impresos con medidas en toda la serie",
    64: "rotulos impresos con medidas en toda la serie",
    65: "fondo beige a toda la lamina en toda la serie",
    67: "rotulos impresos con medidas en toda la serie",
    68: "obra gris casi vacia en toda la serie",
    82: "plantas URBANAS (calles), no de apartamento",
}

# 83 (Borneo, de Cusezar) ESTUVO AQUI por "rotulos impresos en toda la serie" y
# se levanto a proposito. Sus tres laminas llevan escrito encima "Alcoba
# Principal", "Cocina", "Bano" y "Acceso", que es el mismo defecto por el que
# siguen fuera las de Colsubsidio.
#
# La diferencia es lo que hay al otro lado de la balanza. Colsubsidio tiene
# otras 7 laminas limpias; Cusezar no tiene NINGUNA otra: son 3 laminas de 1 de
# sus 14 proyectos, y vetarlas dejaba su demo entera sin escena. Y prestarle la
# planta de otra constructora no es una opcion —la demo es de una sola marca—,
# asi que la eleccion real era "con rotulos" contra "sin plano".
#
# Son ademas plantas cenitales decoradas y correctas, de 3 alcobas, que es el
# caso dominante de Cusezar (11 de sus 14 proyectos).
#
# SI ALGUN DIA CUSEZAR PUBLICA UNA LAMINA LIMPIA, este veto vuelve.

# Laminas que el filtro por descripcion tira y que MIRADAS estan bien. Es una
# lista blanca revisada a ojo, no un cambio del filtro: aflojar el filtro
# meteria una docena de isometricos de golpe.
RESCATADOS: set = set()


def clasificar_plano(desc: str) -> str:
    """'Plano del apartamento. Obra gris.' -> 'gris'

    DUPLICADO a proposito de `clasificarPlano` en app/js/planta.js. Si cambia
    una, cambia la otra. El orden es JERARQUICO y no es negociable: la frase
    "Sugerencia de distribucion y acabados" es la etiqueta estandar del plano
    decorado, pero tambien aparece en descripciones que terminan en "Se entrega
    en obra gris" — si "acabados" se evalua primero, 8 planos grises se
    clasifican como decorados.
    """
    t = (desc or "").lower()
    if not t:
        return "otro"
    if "axonometr" in t:
        return "axo"
    if "obra gris" in t or "sin acabados" in t:
        return "gris"
    if "acabados" in t:
        return "decorado"
    return "otro"


# --------------------------------------------------------------------------
# Lectura de los planos publicados, desde el catalogo ya generado
# --------------------------------------------------------------------------
def planos_del_catalogo() -> list:
    """[(src, desc)] leyendo assets/planos/manifiesto.json.

    Antes se parseaba js/proyectos.js con una expresion regular, porque el
    catalogo vivia ahi. Ahora las laminas las baja
    plataforma/tools/preparar_planos.py del catalogo de Bogota y deja su
    manifiesto al lado, con el proyecto y las alcobas de cada una — que es lo
    que hace falta para repartir el sorteo por numero de alcobas.
    """
    import json

    ruta = os.path.join(APP, "assets", "planos", "manifiesto.json")
    if not os.path.exists(ruta):
        print("Falta %s. Corre antes:" % ruta)
        print("  python plataforma/tools/preparar_planos.py")
        return []
    with open(ruta, encoding="utf-8") as fh:
        manifiesto = json.load(fh)
    global META
    META = {m["src"]: m for m in manifiesto}
    return sorted((m["src"], m["proyecto"]) for m in manifiesto)


# Datos del proyecto por lamina (alcobas, localidad, VIS). Lo llena
# `planos_del_catalogo` y lo usa `escribir_js` para el sorteo.
META: dict = {}


# --------------------------------------------------------------------------
# 1. Recuadro de contenido por componente conexa mayor
# --------------------------------------------------------------------------
def recuadro_contenido(tinta: Image.Image, columnas: int = 80):
    """(bbox, islas). bbox del bloque de tinta MAS GRANDE, en pixeles.

    Se trabaja sobre una rejilla gruesa (columnas x N) porque a resolucion
    completa un flood fill en Python puro no termina nunca, y porque a esta
    escala los detalles finos (una cota, una flecha de norte) se funden con el
    plano en vez de contarse como islas propias.
    """
    W, H = tinta.size
    filas = max(1, round(columnas * H / W))
    mini = tinta.resize((columnas, filas), Image.BOX)
    px = mini.load()
    # 11% de ocupacion: por debajo de eso la celda gruesa es papel con una raya
    ocupada = [[px[x, y] > 28 for y in range(filas)] for x in range(columnas)]

    visto = [[False] * filas for _ in range(columnas)]
    mejor, mejor_n, total_n = None, 0, 0
    for x0 in range(columnas):
        for y0 in range(filas):
            if not ocupada[x0][y0] or visto[x0][y0]:
                continue
            pila = [(x0, y0)]
            visto[x0][y0] = True
            grupo = []
            while pila:
                x, y = pila.pop()
                grupo.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < columnas and 0 <= ny < filas and ocupada[nx][ny] and not visto[nx][ny]:
                        visto[nx][ny] = True
                        pila.append((nx, ny))
            total_n += len(grupo)
            if len(grupo) > mejor_n:
                mejor_n, mejor = len(grupo), grupo

    if not mejor:
        bb = tinta.getbbox()
        return bb, 0.0

    ex = W / columnas
    ey = H / filas
    gx0 = min(p[0] for p in mejor) * ex
    gx1 = (max(p[0] for p in mejor) + 1) * ex
    gy0 = min(p[1] for p in mejor) * ey
    gy1 = (max(p[1] for p in mejor) + 1) * ey
    grueso = (int(gx0), int(gy0), min(W, int(gx1) + 1), min(H, int(gy1) + 1))

    # Afinado a resolucion completa DENTRO de la caja gruesa.
    fino = tinta.crop(grueso).getbbox()
    if fino:
        grueso = (grueso[0] + fino[0], grueso[1] + fino[1],
                  grueso[0] + fino[2], grueso[1] + fino[3])
    islas = 0.0 if total_n == 0 else 1.0 - mejor_n / total_n
    return grueso, islas


# --------------------------------------------------------------------------
# 2. Muros por perfil de proyeccion
# --------------------------------------------------------------------------
def perfil(muros: Image.Image, horizontal: bool) -> list:
    """Proyeccion de la mascara de muros. `resize` con BOX lo hace en C."""
    w, h = muros.size
    if horizontal:
        return list(muros.resize((w, 1), Image.BOX).tobytes())
    return list(muros.resize((1, h), Image.BOX).tobytes())


def picos(p: list, n: int) -> list:
    """Los n valles/muros mas marcados, sin bordes y sin amontonarse."""
    largo = len(p)
    if largo < 10:
        return []
    orden = sorted(range(largo), key=lambda i: -p[i])
    sel = []
    for i in orden:
        if i < largo * MARGEN or i > largo * (1 - MARGEN):
            continue
        if any(abs(i - j) < largo * SEPARACION for j in sel):
            continue
        sel.append(i)
        if len(sel) == n:
            break
    return sorted(sel)


def candidatos_muro(p: list, k: int = 10) -> list:
    """Hasta k muros plausibles, no solo los CORTES_X/Y mas fuertes.

    Mismo criterio que picos() pero conservando mas opciones y con la mitad de
    separacion, para que la busqueda de elegir_cortes() tenga de donde escoger
    sin que se le cuelen dos posiciones del mismo muro.
    """
    largo = len(p)
    if largo < 10:
        return []
    sep = largo * SEPARACION * 0.5
    sel = []
    for i in sorted(range(largo), key=lambda i: -p[i]):
        if p[i] <= 0:
            break
        if i < largo * MARGEN or i > largo * (1 - MARGEN):
            continue
        if any(abs(i - j) < sep for j in sel):
            continue
        sel.append(i)
        if len(sel) == k:
            break
    return sorted(sel)


def _combos(cands: list, n: int, sep: float):
    for combo in itertools.combinations(cands, n):
        if all(combo[i + 1] - combo[i] >= sep for i in range(n - 1)):
            yield combo


def tabla_integral(contenido: Image.Image, lado: int = 200):
    """Suma acumulada 2D de la mascara: densidad de cualquier celda en O(1).

    Hace falta porque elegir_cortes() evalua miles de combinaciones; con
    crop+ImageStat cada plano tardaba minutos. Se trabaja sobre una copia
    reducida: para decidir si una celda esta vacia sobra esa precision (los
    valores que se GUARDAN se siguen midiendo con densidad(), a resolucion
    completa).
    """
    w, h = contenido.size
    esc = min(1.0, float(lado) / max(w, h))
    gw, gh = max(1, int(round(w * esc))), max(1, int(round(h * esc)))
    mini = contenido.resize((gw, gh), Image.BOX)
    px = mini.load()
    acum = [[0] * (gw + 1) for _ in range(gh + 1)]
    for y in range(gh):
        fila = 0
        for x in range(gw):
            fila += px[x, y]
            acum[y + 1][x + 1] = acum[y][x + 1] + fila
    return acum, gw, gh, w, h


def densidad_rapida(tabla, caja) -> float:
    acum, gw, gh, w, h = tabla
    x0, y0, x1, y1 = caja
    gx0 = max(0, min(gw, int(round(x0 * gw / w))))
    gx1 = max(0, min(gw, int(round(x1 * gw / w))))
    gy0 = max(0, min(gh, int(round(y0 * gh / h))))
    gy1 = max(0, min(gh, int(round(y1 * gh / h))))
    if gx1 <= gx0 or gy1 <= gy0:
        return 0.0
    s = acum[gy1][gx1] - acum[gy0][gx1] - acum[gy1][gx0] + acum[gy0][gx0]
    return s / (255.0 * (gx1 - gx0) * (gy1 - gy0))


def elegir_cortes(px: list, py: list, tabla, bw: int, bh: int):
    """(cortes_x, cortes_y, densidad de la celda mas floja, si se reubico).

    POR QUE NO BASTA CON LOS MUROS MAS FUERTES. picos() elige por altura del
    perfil y no mira que celdas produce. Cuando la huella del apartamento no
    llena su recuadro -casi ninguna lo hace del todo- eso deja celdas de papel
    casi en blanco, y al armarse el plano se leen como PIEZAS QUE FALTAN: el
    usuario ve un apartamento con agujeros, no un apartamento terminado. Medido
    en el sorteo: Nogales A11 dejaba dos celdas al 34% y al 26%.

    Asi que los muros mas fuertes siguen mandando -es lo que hace que los
    cortes caigan sobre paredes reales y no a mitad de una cama- y solo cuando
    producen una celda por debajo de UMBRAL_CELDA_MINIMA se buscan otras
    combinaciones de muros.

    Y la busqueda NO maximiza la densidad: entre las combinaciones que llegan
    al umbral gana la que se apoya en los MUROS MAS MARCADOS, no la que deja
    las celdas mas llenas. Maximizar la densidad a secas empujaba los cortes
    lejos de las paredes (122 de 150 laminas cambiaban, con cortes a mitad de
    un mueble): el objetivo es que no haya agujeros blancos, no que las celdas
    esten lo mas llenas posible. Solo si NINGUNA combinacion llega al umbral se
    coge la menos mala, que es lo mejor disponible para ese plano.
    """
    cx, cy = picos(px, CORTES_X), picos(py, CORTES_Y)
    if not cx or not cy:
        return cx, cy, 0.0, False

    def peor(a, b):
        return min(densidad_rapida(tabla, c) for c in celdas_de(a, b, bw, bh))

    base = peor(cx, cy)
    if base >= UMBRAL_CELDA_MINIMA:
        return cx, cy, base, False

    fuerza = lambda p, c: sum(p[i] for i in c)
    # Dos carreras a la vez: la de las que SI llegan al umbral (gana la de
    # muros mas fuertes) y, por si ninguna llega, la de la celda mas llena.
    mejor_ok, mejor_ok_cortes = -1, None
    mejor_min, mejor_min_cortes = base, None

    combos_y = [(c, fuerza(py, c)) for c in _combos(candidatos_muro(py), CORTES_Y, bh * SEPARACION)]
    for combo_x in _combos(candidatos_muro(px), CORTES_X, bw * SEPARACION):
        fx = fuerza(px, combo_x)
        for combo_y, fy in combos_y:
            m = peor(combo_x, combo_y)
            if m >= UMBRAL_CELDA_MINIMA:
                if fx + fy > mejor_ok:
                    mejor_ok, mejor_ok_cortes = fx + fy, (list(combo_x), list(combo_y), m)
            elif m > mejor_min:
                mejor_min, mejor_min_cortes = m, (list(combo_x), list(combo_y), m)

    elegido = mejor_ok_cortes or mejor_min_cortes
    if not elegido:
        return cx, cy, base, False
    return elegido[0], elegido[1], elegido[2], True


# --------------------------------------------------------------------------
# 3. Celdas
# --------------------------------------------------------------------------
def celdas_de(cortes_x: list, cortes_y: list, bw: int, bh: int) -> list:
    """(cx0,cy0,cx1,cy1) en pixeles del recuadro, fila por fila.

    Se redondean los CORTES y el tamano se deduce de la diferencia, nunca al
    reves: redondeando posicion y tamano por separado, el borde de una celda no
    coincide con el de la siguiente y aparecen costuras de subpixel.
    """
    xs = [0] + list(cortes_x) + [bw]
    ys = [0] + list(cortes_y) + [bh]
    out = []
    for a in range(len(ys) - 1):
        for b in range(len(xs) - 1):
            out.append((xs[b], ys[a], xs[b + 1], ys[a + 1]))
    return out


def densidad(contenido: Image.Image, caja) -> float:
    """Fraccion de tinta de una celda. `contenido` es la mascara ya recortada."""
    x0, y0, x1, y1 = caja
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return ImageStat.Stat(contenido.crop(caja)).mean[0] / 255.0


# --------------------------------------------------------------------------
# 4. Orden de revelacion y reparto por pregunta
# --------------------------------------------------------------------------
def orden_por_adyacencia(celdas: list, utiles: list, dens: list, ncols: int) -> list:
    """Del corazon hacia afuera. Devuelve indices de celda, en orden.

    La semilla es la celda util mas cercana al centro de masa de la tinta: en un
    plano de apartamento eso cae casi siempre en la sala-comedor o en la
    circulacion, que es por donde uno entra a leer un plano. A partir de ahi
    solo se anaden celdas que TOQUEN lo ya revelado, para que el plano a medias
    sea siempre una mancha conexa y no un rompecabezas volcado.
    """
    if not utiles:
        return []

    def centro(i):
        x0, y0, x1, y1 = celdas[i]
        return ((x0 + x1) / 2, (y0 + y1) / 2)

    peso = sum(dens[i] for i in utiles) or 1
    cmx = sum(centro(i)[0] * dens[i] for i in utiles) / peso
    cmy = sum(centro(i)[1] * dens[i] for i in utiles) / peso

    def area(i):
        x0, y0, x1, y1 = celdas[i]
        return (x1 - x0) * (y1 - y0)

    restantes = set(utiles)
    semilla = min(restantes, key=lambda i: (centro(i)[0] - cmx) ** 2 + (centro(i)[1] - cmy) ** 2)
    orden = [semilla]
    restantes.discard(semilla)

    def adyacente(i, puestos):
        fi, ci = divmod(i, ncols)
        for j in puestos:
            fj, cj = divmod(j, ncols)
            if abs(fi - fj) + abs(ci - cj) == 1:
                return True
        return False

    while restantes:
        vecinas = [i for i in restantes if adyacente(i, orden)]
        # Sin vecinas la huella esta partida (el filtro de densidad se comio el
        # puente): se rescata la mejor global y se sigue.
        candidatas = vecinas or list(restantes)
        elegida = max(candidatas, key=lambda i: (dens[i] * area(i), -i))
        orden.append(elegida)
        restantes.discard(elegida)
    return orden


def reparto_por_pregunta(orden: list, celdas: list, dens: list,
                         preguntas: int = 7, cierran: int = 6) -> list:
    """vis[k] = cuantas celdas se ven tras la pregunta k.

    Por AREA de tinta acumulada y no por conteo: como el orden va de mayor a
    menor, repartir por conteo hace que la primera pregunta se lleve el 30% de
    la superficie y las ultimas cuatro solo anadan lascas.

    El plano se cierra en la pregunta `cierran` (la 6.a de 7), que es la que
    deja el apartamento TERMINADO justo cuando se pinta la ULTIMA pregunta: esa
    es la pantalla en la que se ve completo, y es lo que se pidio.

    No se puede cerrar en la 8.a: al contestarla el quiz salta a la pantalla de
    resultados, que ya no tiene escena, asi que lo que revelara esa respuesta no
    lo veria nadie.

    Se probo cerrar en la 6.a (para que el plano completo acompanara las dos
    ultimas preguntas) y se descarto: el remate tiene que caer con la ultima
    respuesta que aun anade piezas, no antes.
    """
    def tinta(i):
        x0, y0, x1, y1 = celdas[i]
        return dens[i] * (x1 - x0) * (y1 - y0)

    total = sum(tinta(i) for i in orden) or 1
    vis = []
    acum = 0.0
    puestas = 0
    for k in range(1, preguntas + 1):
        objetivo = total * min(k, cierran) / cierran
        while puestas < len(orden) and acum < objetivo:
            acum += tinta(orden[puestas])
            puestas += 1
        vis.append(puestas)

    # Garantias, en este orden:
    #   1. cada pregunta anade AL MENOS una pieza. Si no, responder no produce
    #      nada visible y el juego se siente roto. Ojo: el minimo es "una mas
    #      que la anterior", no un suelo absoluto — con un suelo absoluto un
    #      reparto como 2,3,3,5 pasaba el filtro y la tercera pregunta no
    #      movia el plano.
    #   2. la ultima respuesta cierra el plano.
    #   3. y despues de forzar la ultima, se vuelve hacia atras para que no
    #      quede una pregunta anadiendo mas piezas que las que hay.
    n = len(orden)
    # Cada pregunta hasta la que cierra anade AL MENOS una pieza. El minimo es
    # "una mas que la anterior", no un suelo absoluto: con un suelo absoluto un
    # reparto como 2,3,3,5 pasaba el filtro y la tercera pregunta no movia nada.
    for k in range(cierran):
        piso = 1 if k == 0 else vis[k - 1] + 1
        vis[k] = min(n, max(vis[k], piso))
    for k in range(cierran - 2, -1, -1):
        vis[k] = max(0, min(vis[k], vis[k + 1] - 1))
    # La que cierra completa el plano, y de ahi en adelante ya no queda nada.
    for k in range(cierran - 1, preguntas):
        vis[k] = n
    return vis


# --------------------------------------------------------------------------
# Analisis de un plano
# --------------------------------------------------------------------------
def analizar(ruta_abs: str, src: str, desc: str) -> dict | None:
    im = Image.open(ruta_abs).convert("L")
    Wi, Hi = im.size
    tinta = im.point(lambda v: 255 if v < UMBRAL_TINTA else 0)
    bbox, islas = recuadro_contenido(tinta)
    if not bbox:
        return None
    bx, by, bx1, by1 = bbox
    bw, bh = bx1 - bx, by1 - by
    if bw < 60 or bh < 60:
        return None

    muros = im.crop(bbox).point(lambda v: 255 if v < UMBRAL_MURO else 0)
    contenido = tinta.crop(bbox)

    # Los muros mas fuertes mandan, salvo que dejen una celda casi en blanco
    # (que al armarse el plano se lee como una pieza que falta): ver
    # elegir_cortes.
    cx, cy, _peor, reubicado = elegir_cortes(
        perfil(muros, horizontal=True), perfil(muros, horizontal=False),
        tabla_integral(contenido), bw, bh,
    )
    ncols = len(cx) + 1

    cajas = celdas_de(cx, cy, bw, bh)
    dens = [round(densidad(contenido, c), 3) for c in cajas]
    utiles = [i for i, d in enumerate(dens) if d > UMBRAL_CELDA]

    orden = orden_por_adyacencia(cajas, utiles, dens, ncols)
    vis = reparto_por_pregunta(orden, cajas, dens)

    media = sum(dens[i] for i in utiles) / len(utiles) if utiles else 0.0
    ratio = bw / bh
    # "Rectangular": las DOCE celdas tienen contenido, o sea que la huella del
    # apartamento llena su recuadro y no tiene esquinas vacias. Se marca aparte
    # porque en esos la silueta gris es un rectangulo limpio y el plano se ve
    # armarse entero, sin mordiscos.
    rect = len(utiles) == len(dens) and min(dens) >= UMBRAL_RECT
    motivo = None
    proyecto = META.get(src, {}).get("id_proyecto")
    if src in VETADOS:
        motivo = "vetado: " + VETADOS[src]
    elif proyecto in PROYECTOS_VETADOS:
        motivo = "proyecto vetado: " + PROYECTOS_VETADOS[proyecto]
    # AQUI SE FILTRABA POR LA DESCRIPCION DEL CMS ("obra gris" / "acabados").
    # Ya no: el catalogo de Bogota no trae descripcion por lamina, asi que ese
    # filtro rechazaba las 234 de golpe.
    #
    # Tampoco se echa de menos tanto como parece. Estaba medido que se
    # equivocaba EN LAS DOS DIRECCIONES —decia "obra gris" de plantas amuebladas
    # y limpias, y "obra gris" de renders isometricos— y por eso hubo que
    # inventar RESCATADOS para contrapesarlo. Lo que de verdad decide es lo que
    # viene debajo: la forma, la densidad y la curaduria a ojo de VETADOS.
    elif not (RATIO_MIN <= ratio <= RATIO_MAX):
        motivo = "ratio %.2f fuera de [%.2f, %.2f]" % (ratio, RATIO_MIN, RATIO_MAX)
    elif islas > ISLAS_MAX:
        motivo = "islas %.0f%% (inserto suelto?)" % (islas * 100)
    elif len(utiles) < UTILES_MIN:
        motivo = "solo %d celdas utiles" % len(utiles)
    elif media < DENSIDAD_MEDIA_MIN:
        motivo = "densidad media %.2f" % media

    return {
        "src": src,
        "Wi": Wi, "Hi": Hi,
        "bx": bx, "by": by, "bw": bw, "bh": bh,
        # En milesimas del recuadro: enteros, y el JS no tiene que saber de px.
        "cx": [int(round(1000 * v / bw)) for v in cx],
        "cy": [int(round(1000 * v / bh)) for v in cy],
        "dens": [int(round(100 * d)) for d in dens],
        "orden": orden,
        "vis": vis,
        "utiles": len(utiles),
        "islas": round(islas, 3),
        "ratio": round(ratio, 2),
        "apto": motivo is None,
        "rect": rect,
        "motivo": motivo,
        # Diagnostico, no sale al JS: la celda mas floja y si hubo que mover
        # los cortes fuera de los muros mas fuertes para conseguirla.
        # `dens` son fracciones 0..1; se pasa a porcentaje como el campo "dens".
        "peor_celda": int(round(100 * min(dens))) if dens else 0,
        "reubicado": reubicado,
    }


# --------------------------------------------------------------------------
# Salida
# --------------------------------------------------------------------------
def lista_js(v) -> str:
    return "[" + ",".join(str(x) for x in v) + "]"


# El scraper nombra los planos <slug-proyecto>-<slug-tipologia>-<n>.<ext>, asi
# que quitar el sufijo da la tipologia. Sirve para no meter el mismo apartamento
# dos veces en el sorteo: Calia Tipo 2 publica tres laminas y las tres pueden
# pasar los filtros, pero es UN apartamento.
RE_SUFIJO = re.compile(r"-\d+\.(webp|png|jpe?g)$")


def tipologia_de(src: str) -> str:
    return RE_SUFIJO.sub("", src)


def seleccionar_aptos(datos: list) -> list:
    """Un plano por tipologia: el de mas celdas utiles, desempatando por nombre."""
    por_tipologia = {}
    for d in datos:
        if not d["apto"]:
            continue
        clave = tipologia_de(d["src"])
        actual = por_tipologia.get(clave)
        if actual is None or (d["utiles"], -len(d["src"])) > (actual["utiles"], -len(actual["src"])):
            por_tipologia[clave] = d
    return sorted(por_tipologia.values(), key=lambda d: d["src"])


def escribir_js(datos: list, ruta: str) -> None:
    import datetime

    aptos = seleccionar_aptos(datos)
    lineas = [
        "// ARCHIVO GENERADO — no editar a mano.",
        "// Lo produce tools/analizar_planos.py a partir de las imagenes de",
        "// assets/planos/ (las mismas que baja tools/scrape_proyectos.py).",
        "//",
        "//   Generado: %s" % datetime.date.today().isoformat(),
        "//   Planos analizados: %d  |  aptos para la animacion: %d" % (len(datos), len(aptos)),
        "//",
        "// Es lo que le permite al quiz ARMAR el plano real por partes: por",
        "// donde cortarlo (sus muros), que celdas tienen contenido, en que orden",
        "// aparecen y cuantas se ven tras cada pregunta.",
        "//",
        "// Formato, por plano:",
        "//   [Wi, Hi,            tamano de la imagen completa, en px",
        "//    bx, by, bw, bh,    recuadro de contenido dentro de ella, en px",
        "//    [cortesX],         en MILESIMAS del ancho del recuadro",
        "//    [cortesY],         en MILESIMAS del alto del recuadro",
        "//    [densidad x100],   una por celda, en orden de lectura",
        "//    [orden],           indices de celda, en el orden en que aparecen",
        "//    [vis x7]]          cuantas celdas se ven tras cada pregunta",
        "//",
        "// Para regenerar:  python tools/analizar_planos.py",
        "window.GDF_PLANOS = {",
    ]
    for d in datos:
        lineas.append(
            "  '%s': [%d,%d, %d,%d,%d,%d, %s, %s, %s, %s, %s],"
            % (d["src"], d["Wi"], d["Hi"], d["bx"], d["by"], d["bw"], d["bh"],
               lista_js(d["cx"]), lista_js(d["cy"]), lista_js(d["dens"]),
               lista_js(d["orden"]), lista_js(d["vis"]))
        )
    lineas.append("};")
    rectos = [d for d in aptos if d["rect"]]
    lineas += [
        "",
        "// Los que pasan los filtros de aptitud y la curacion a mano. El orden",
        "// es estable para que el hash del nombre devuelva siempre el mismo",
        "// plano para la misma persona.",
        "window.GDF_PLANOS_APTOS = [",
    ]
    for d in aptos:
        lineas.append("  '%s'," % d["src"])
    lineas.append("];")
    lineas += [
        "",
        "// De esos, los RECTANGULARES: la huella del apartamento llena su",
        "// recuadro y no deja esquinas vacias, asi que la silueta es un",
        "// rectangulo limpio y el plano se ve armarse entero, sin mordiscos.",
        "// Es la lista que usa elegirApartamento (js/planta.js); si algun dia se",
        "// queda vacia al regenerar, cae a GDF_PLANOS_APTOS.",
        "window.GDF_PLANOS_RECTOS = [",
    ]
    for d in rectos:
        lineas.append("  '%s'," % d["src"])
    lineas.append("];")

    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lineas) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=0, help="solo N planos (pruebas)")
    ap.add_argument("--detalle", action="store_true", help="una linea por plano")
    args = ap.parse_args()

    planos = planos_del_catalogo()
    if args.limite:
        planos = planos[: args.limite]
    print("1) planos en el catalogo: %d" % len(planos))

    datos, faltantes, fallos = [], [], []
    for src, desc in planos:
        ruta = os.path.join(APP, src.replace("/", os.sep))
        if not os.path.exists(ruta):
            faltantes.append(src)
            continue
        try:
            d = analizar(ruta, src, desc)
            if d:
                datos.append(d)
            else:
                fallos.append((src, "sin contenido utilizable"))
        except Exception as e:
            fallos.append((src, "%s: %s" % (type(e).__name__, e)))

    print("2) analizados: %d | faltan en disco: %d | fallos: %d"
          % (len(datos), len(faltantes), len(fallos)))
    for s in faltantes:
        print("    ! no esta en disco: %s" % s)
    for s, e in fallos:
        print("    ! %s -> %s" % (s, e))

    if not datos:
        print("ABORTADO: ningun plano analizado; no se toca js/planos.js")
        return 1

    hist = {}
    for d in datos:
        hist[d["utiles"]] = hist.get(d["utiles"], 0) + 1
    print("3) celdas utiles por plano:")
    for k in sorted(hist):
        print("     %2d celdas -> %d planos" % (k, hist[k]))

    aptos = seleccionar_aptos(datos)
    pasan = sum(1 for d in datos if d["apto"])
    rectos = [d for d in aptos if d["rect"]]
    print("4) pasan los filtros: %d de %d laminas -> %d apartamentos distintos"
          % (pasan, len(datos), len(aptos)))
    print("   de esos, RECTANGULARES (los que usa el quiz): %d" % len(rectos))
    for d in rectos:
        print("     %-46s ratio %.2f  celda mas floja %2d%%%s"
              % (d["src"].replace("assets/planos/", ""), d["ratio"], d["peor_celda"],
                 "  (cortes reubicados)" if d["reubicado"] else ""))
    movidos = sum(1 for d in datos if d.get("reubicado"))
    print("   cortes reubicados para no dejar celdas en blanco: %d de %d laminas"
          % (movidos, len(datos)))
    rechazo = {}
    for d in datos:
        if d["apto"]:
            continue
        clave = d["motivo"].split(":")[0].split("(")[0].strip()
        rechazo[clave] = rechazo.get(clave, 0) + 1
    for k in sorted(rechazo, key=lambda x: -rechazo[x]):
        print("     %-34s %d" % (k, rechazo[k]))

    if args.detalle:
        print("5) detalle:")
        for d in sorted(datos, key=lambda x: (not x["apto"], x["src"])):
            print("   %s %-46s ratio %.2f  utiles %2d  islas %.2f  %s"
                  % ("OK " if d["apto"] else "-- ", d["src"].replace("assets/planos/", ""),
                     d["ratio"], d["utiles"], d["islas"], d["motivo"] or ""))

    # Ademas del .js, un JSON con lo mismo: lo consume
    # plataforma/tools/generar_tenants.py para repartir el pool por
    # constructora. Parsear el .js con expresiones regulares para eso seria
    # pedir un fallo silencioso.
    import json as _json
    aptos_src = [d["src"] for d in seleccionar_aptos(datos)]
    analisis = {
        "aptos": aptos_src,
        "rectos": [d["src"] for d in seleccionar_aptos(datos) if d["rect"]],
        "planos": {d["src"]: [d["Wi"], d["Hi"], d["bx"], d["by"], d["bw"], d["bh"],
                              d["cx"], d["cy"], d["dens"], d["orden"], d["vis"]]
                   for d in datos if d["src"] in set(aptos_src)},
    }
    with open(os.path.join(APP, "assets", "planos", "analisis.json"), "w",
              encoding="utf-8") as fh:
        _json.dump(analisis, fh, ensure_ascii=False)

    escribir_js(datos, SALIDA_JS)
    print("6) escrito %s (%d KB)" % (SALIDA_JS, os.path.getsize(SALIDA_JS) // 1024))
    if len(aptos) < 12:
        print("   OJO: quedan pocos aptos. Antes de aflojar el umbral de densidad,")
        print("   aflojar el filtro de ratio (es el que mas descarta).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
