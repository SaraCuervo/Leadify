"""Dibuja las plantas de la escena para una constructora que no publica ninguna.

    python app/tools/dibujar_planos.py

SALIDA
    app/assets/planos/inventado-<n>alcobas.png   (1, 2 y 3 alcobas)
    + sus entradas en app/assets/planos/manifiesto.json, marcadas `inventado`

POR QUE EXISTE ESTO
-------------------
AMARILO NO PUBLICA NI UNA PLANTA. No es que el filtro por nombre de archivo las
tire: se bajaron sus 159 imagenes y se miraron una a una en una hoja de
contactos. Son fachadas, piscinas, lobbies, salones y vistas aereas — renders
comerciales, ni un plano. Su scrape trae 4,3 imagenes por ficha frente a las
49,6 de Bolivar: publican poco, y lo que publican es catalogo de venta.

La salida facil seria prestarle a Amarilo la planta real de Bolivar. NO SE HACE:
la demo es de UNA constructora y ensenar la planta de otra dentro de ella es
exactamente la mezcla que el resto del repo se dedica a evitar. La escena es
anonima —nunca dice de que proyecto es el apartamento— asi que un plano
dibujado por nosotros encaja donde uno prestado no encajaria.

Estas laminas NO se etiquetan como de nadie: van al manifiesto con
`constructora: null` e `inventado: true`, y generar_tenants.py se las da a una
marca SOLO si no tiene ninguna propia.

LO QUE EL DIBUJO TIENE QUE CUMPLIR, QUE NO ES ESTETICO
------------------------------------------------------
analizar_planos.py mide la lamina y la rechaza si no da la talla. De ahi salen
casi todas las decisiones de aqui:

  - **El suelo va PINTADO, no en blanco.** La "densidad" de una celda es la
    fraccion de pixeles por debajo de UMBRAL_TINTA (235). Un plano de linea
    negra sobre papel blanco tiene densidad ~0,05 y lo rechaza todo. Las
    plantas reales que sirven estan AMUEBLADAS y con el suelo entintado, y por
    eso pasan. Se pide densidad > 0,55 en 7 celdas de 12 como minimo.
  - **Todo tiene que estar pegado.** El recuadro de contenido se saca de la
    componente conexa MAYOR y la lamina se rechaza si mas del 6 % de la tinta
    queda fuera (ISLAS_MAX). Como el suelo entintado toca los muros y los
    muebles, la lamina entera es una sola mancha: islas = 0.
  - **Los muros mandan donde se corta.** Los cortes de la reja 4x3 se eligen
    sobre el perfil de pixeles < UMBRAL_MURO (90), o sea los muros. Por eso los
    tabiques van cerca de 1/4, 2/4 y 3/4 a lo ancho y de 1/3 y 2/3 a lo alto:
    asi cada pieza que cae en la escena es una habitacion y no un trozo
    cualquiera.
  - **Proporcion entre 0,85 y 1,75** (RATIO_MIN/RATIO_MAX): un apartamento muy
    alargado deja la escena con franjas vacias a los lados.

NO LLEVAN UN SOLO ROTULO. Es el mismo motivo por el que estan vetadas media
docena de laminas reales: la gracia de la escena es que el apartamento se lea
como un espacio que se arma, no que venga con las respuestas escritas encima, y
al trocearlo los rotulos quedan partidos por las costuras.
"""

import json
import math
import pathlib

from PIL import Image, ImageDraw

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
DESTINO = RAIZ / "app" / "assets" / "planos"
MANIFIESTO = DESTINO / "manifiesto.json"

# Lienzo generoso: analizar_planos trabaja sobre la imagen tal cual y la escena
# la reescala. 1600x1100 da ratio 1,45, comodo dentro de 0,85-1,75.
ANCHO, ALTO = 1600, 1100
MARGEN = 60

# La paleta es GRIS, no de marca. Estas laminas no son de nadie y no tienen que
# parecerse al color de ninguna constructora.
PAPEL = (255, 255, 255)
MURO = (26, 26, 28)              # < UMBRAL_MURO (90): es lo que se lee como muro
SUELO = (216, 211, 204)          # < UMBRAL_TINTA (235): cuenta como contenido
SUELO_HUMEDO = (199, 202, 205)   # banos, cocina y ropas, un gris mas frio
ALFOMBRA = (204, 198, 190)
COLCHON = (190, 186, 180)
MUEBLE = (150, 147, 142)
MUEBLE_CLARO = (176, 173, 168)
TEXTIL = (122, 126, 130)

GRUESO_MURO = 16
GRUESO_TABIQUE = 11


def _rect(d, caja, relleno=None, borde=None, grosor=1, radio=0):
    x0, y0, x1, y1 = [int(v) for v in caja]
    if x1 < x0 or y1 < y0:
        return
    if radio:
        d.rounded_rectangle([x0, y0, x1, y1], radio, fill=relleno, outline=borde, width=grosor)
    else:
        d.rectangle([x0, y0, x1, y1], fill=relleno, outline=borde, width=grosor)


def _elipse(d, centro, rx, ry, relleno=None, borde=None, grosor=2):
    cx, cy = centro
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=relleno, outline=borde, width=grosor)


# --------------------------------------------------------------------------
# Muebles
# --------------------------------------------------------------------------
# Todos se dibujan DENTRO de su habitacion y ninguno cruza un tabique: una cama
# partida por un muro se lee como un error de dibujo justo cuando la escena
# trocea la lamina por ahi, que es lo que hace.

def _cama(d, caja, doble=True):
    x0, y0, x1, y1 = caja
    an, al = x1 - x0, y1 - y0
    _rect(d, caja, COLCHON, MURO, 3, radio=10)
    _rect(d, (x0 - 6, y0 - 16, x1 + 6, y0 + 4), MUEBLE, MURO, 3, radio=4)   # cabecero
    alm = al * 0.16
    if doble:
        med = (x0 + x1) / 2
        _rect(d, (x0 + 14, y0 + 14, med - 8, y0 + alm + 14), PAPEL, MURO, 2, radio=7)
        _rect(d, (med + 8, y0 + 14, x1 - 14, y0 + alm + 14), PAPEL, MURO, 2, radio=7)
    else:
        _rect(d, (x0 + an * 0.22, y0 + 14, x1 - an * 0.22, y0 + alm + 14), PAPEL, MURO, 2, radio=7)
    # La manta a los pies: es lo que le da a la cama su lectura cenital.
    _rect(d, (x0 + 4, y1 - al * 0.30, x1 - 4, y1 - 4), TEXTIL, None, radio=8)
    if an > 250:
        _rect(d, (x0 - 4, y0 + 6, x0 + 40, y0 + 50), MUEBLE, MURO, 2, radio=4)
        _rect(d, (x1 - 40, y0 + 6, x1 + 4, y0 + 50), MUEBLE, MURO, 2, radio=4)


def _armario(d, caja, vertical=True):
    """Un armario cenital son dos cosas: el frente y las baldas."""
    x0, y0, x1, y1 = caja
    _rect(d, caja, MUEBLE, MURO, 3)
    for i in range(1, 4):
        if vertical:
            y = y0 + (y1 - y0) * i / 4
            d.line([x0, y, x1, y], fill=MURO, width=2)
        else:
            x = x0 + (x1 - x0) * i / 4
            d.line([x, y0, x, y1], fill=MURO, width=2)


def _sofa(d, caja):
    x0, y0, x1, y1 = caja
    _rect(d, caja, MUEBLE, MURO, 3, radio=14)
    _rect(d, (x0 + 16, y0 + 18, x1 - 16, y1 - 12), MUEBLE_CLARO, MURO, 2, radio=10)


def _mesa_redonda(d, centro, rx, ry, sillas=4):
    cx, cy = centro
    _elipse(d, (cx, cy), rx, ry, MUEBLE_CLARO, MURO, 3)
    for i in range(sillas):
        ang = i * (2 * math.pi / sillas) + math.pi / sillas
        _elipse(d, (cx + (rx + 30) * math.cos(ang), cy + (ry + 30) * math.sin(ang)),
                17, 17, MUEBLE, MURO, 2)


def _cocina(d, caja):
    """Meson en L contra dos muros, con fregadero, placa y una isla."""
    x0, y0, x1, y1 = caja
    f = 56
    _rect(d, (x0, y0, x1, y0 + f), MUEBLE_CLARO, MURO, 3)
    _rect(d, (x0, y0, x0 + f, y1 - 46), MUEBLE_CLARO, MURO, 3)
    _elipse(d, (x0 + f + 84, y0 + f / 2), 26, 19, PAPEL, MURO, 2)          # fregadero
    for i in range(4):                                                      # placa
        _elipse(d, (x1 - 118 + (i % 2) * 42, y0 + f / 2 - 12 + (i // 2) * 24),
                10, 10, MURO)
    _rect(d, (x0 + f + 34, y1 - 132, x1 - 34, y1 - 66), MUEBLE, MURO, 3, radio=6)
    for i in range(3):                                                      # taburetes
        _elipse(d, (x0 + f + 84 + i * 66, y1 - 34), 16, 16, MUEBLE, MURO, 2)


def _bano(d, caja, con_ducha=True):
    x0, y0, x1, y1 = caja
    _rect(d, caja, SUELO_HUMEDO)
    _rect(d, (x0 + 12, y0 + 10, x0 + 64, y0 + 42), PAPEL, MURO, 3, radio=4)   # lavamanos
    _elipse(d, (x0 + 38, y0 + 26), 16, 11, PAPEL, MURO, 2)
    _rect(d, (x0 + 90, y0 + 8, x0 + 136, y0 + 68), PAPEL, MURO, 3, radio=14)  # inodoro
    _elipse(d, (x0 + 113, y0 + 44), 19, 17, PAPEL, MURO, 2)
    if con_ducha and (y1 - y0) > 150:
        dx0, dy0 = x0 + 12, y1 - 116
        _rect(d, (dx0, dy0, x1 - 12, y1 - 12), PAPEL, MURO, 3)
        _elipse(d, ((dx0 + x1 - 12) / 2, (dy0 + y1 - 12) / 2), 9, 9, MURO)     # sumidero
        d.line([dx0, dy0, dx0 + 46, dy0], fill=MURO, width=5)                  # mampara


def _lavadora(d, caja):
    x0, y0, x1, y1 = caja
    _rect(d, caja, MUEBLE_CLARO, MURO, 3, radio=4)
    _elipse(d, ((x0 + x1) / 2, (y0 + y1) / 2 + 4), 21, 21, PAPEL, MURO, 3)


def _escritorio(d, caja):
    x0, y0, x1, y1 = caja
    _rect(d, (x0, y0, x1, y0 + 46), MUEBLE_CLARO, MURO, 3, radio=4)
    _elipse(d, ((x0 + x1) / 2, y0 + 82), 19, 19, MUEBLE, MURO, 2)


# --------------------------------------------------------------------------
# Obra
# --------------------------------------------------------------------------

def _tabique(d, x0, y0, x1, y1, grosor=None):
    """Un tabique es un rectangulo relleno, no una linea: asi mide lo mismo
    mirado por el perfil horizontal que por el vertical, que es lo que lee
    elegir_cortes()."""
    g = grosor or GRUESO_TABIQUE
    if abs(x1 - x0) < abs(y1 - y0):
        _rect(d, (x0 - g / 2, y0, x0 + g / 2, y1), MURO)
    else:
        _rect(d, (x0, y0 - g / 2, x1, y0 + g / 2), MURO)


def _puerta(d, x, y, luz, vertical, hacia=1):
    """Vano, hoja y barrido, con la bisagra en (x, y).

    El arco de una puerta es lo que hace que un dibujo se lea como un PLANO y
    no como un diagrama de cajas.

    El vano se rellena con el SUELO y no con papel: un agujero blanco en mitad
    del tabique le baja la densidad a la celda justo donde mas apretado va el
    umbral, y en la escena esa celda pasa de pieza a mordisco.

    Los angulos de PIL van en el sentido de las agujas desde las 3 en punto, y
    la caja del arco tiene que ir SIEMPRE ordenada: con `hacia=-1` salia
    invertida y reventaba con "x1 must be greater than or equal to x0".
    """
    g = GRUESO_TABIQUE + 6
    caja = (x - luz, y - luz, x + luz, y + luz)
    if vertical:
        _rect(d, (x - g / 2, y, x + g / 2, y + luz), SUELO)
        ini, fin = (0, 90) if hacia > 0 else (90, 180)
        d.line([x, y, x + luz * hacia, y], fill=MURO, width=5)
    else:
        _rect(d, (x, y - g / 2, x + luz, y + g / 2), SUELO)
        ini, fin = (0, 90) if hacia > 0 else (270, 360)
        d.line([x, y, x, y + luz * hacia], fill=MURO, width=5)
    d.arc([int(v) for v in caja], ini, fin, fill=MURO, width=3)


def _ventana(d, caja):
    x0, y0, x1, y1 = caja
    _rect(d, caja, PAPEL, MURO, 3)
    if x1 - x0 > y1 - y0:
        d.line([x0, (y0 + y1) / 2, x1, (y0 + y1) / 2], fill=MURO, width=3)
    else:
        d.line([(x0 + x1) / 2, y0, (x0 + x1) / 2, y1], fill=MURO, width=3)


def dibujar(alcobas):
    """La lamina de N alcobas.

    Las tres comparten caja y organizacion —cocina y zona de dia a la
    izquierda, banos y ropas en la banda central, alcobas a la derecha— porque
    lo que cambia entre un apartamento de 1 y uno de 3 alcobas es cuantas
    piezas caben, no como se ordenan. Las franjas de alcoba que sobran se
    amueblan como estudio: una celda vacia se lee en la escena como una pieza
    que falta, y fingir una alcoba que no hay seria peor.
    """
    im = Image.new("RGB", (ANCHO, ALTO), PAPEL)
    d = ImageDraw.Draw(im)

    x0, y0 = MARGEN, MARGEN
    x1, y1 = ANCHO - MARGEN, ALTO - MARGEN
    an, al = x1 - x0, y1 - y0

    # Los tabiques van donde analizar_planos va a querer cortar.
    vx = [x0 + an * f for f in (0.25, 0.52, 0.76)]
    hy = [y0 + al * f for f in (0.34, 0.67)]

    # LA HUELLA ES UN RECTANGULO ENTERO, y esto costo una vuelta. La primera
    # version le mordia la esquina de abajo a la izquierda para que la silueta
    # no se leyera como una caja. Dos cosas salieron mal: la mordida era
    # demasiado pequena para que analizar_planos la contara como celda vacia
    # (esa celda seguia al 77 %, o sea que seguia siendo pieza), y en la escena
    # la pieza caia con el papel BLANCO de la mordida dentro. Ese blanco no
    # desaparece: la losa que hay debajo es clara, y multiply de blanco sobre
    # claro sigue siendo claro. El resultado era un pico blanco colgando de la
    # esquina del apartamento.
    #
    # Con el rectangulo entero las doce celdas son pieza, que es lo que
    # analizar_planos llama "rectangular" y lo que hacen la mayoria de las
    # laminas reales que pasan la criba.
    huella = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    d.polygon(huella, fill=SUELO)

    # --- cocina, arriba a la izquierda
    _cocina(d, (x0 + 26, y0 + 26, vx[0] - 26, hy[0] - 26))

    # --- sala-comedor, las dos columnas de la izquierda en la franja del medio
    _rect(d, (x0 + 56, hy[0] + 36, vx[1] - 66, hy[1] - 36), ALFOMBRA, MURO, 2, radio=4)
    _sofa(d, (x0 + 86, hy[0] + 58, x0 + 322, hy[0] + 166))
    _rect(d, (vx[1] - 126, hy[0] + 66, vx[1] - 78, hy[1] - 66), MUEBLE, MURO, 3)  # mueble de TV
    _mesa_redonda(d, ((x0 + vx[1]) / 2 + 16, hy[1] - 128), 72, 55, sillas=4)

    # --- balcon y deposito, en la franja de abajo a la izquierda
    _rect(d, (x0 + 26, hy[1] + 34, vx[0] - 26, y1 - 26), SUELO_HUMEDO)
    _armario(d, (x0 + 44, hy[1] + 54, x0 + 96, y1 - 46))
    _escritorio(d, (x0 + 130, hy[1] + 54, vx[0] - 44, y1 - 46))
    _rect(d, (vx[0] + 24, hy[1] + 34, vx[1] - 24, y1 - 26), SUELO_HUMEDO, MURO, 3)
    for i in range(7):
        bx = vx[0] + 44 + i * ((vx[1] - vx[0] - 88) / 6)
        d.line([bx, hy[1] + 50, bx, y1 - 40], fill=MUEBLE, width=3)

    # --- banda de servicios: banos, y ropas abajo
    _rect(d, (vx[1] + 8, y0 + 8, vx[2] - 8, hy[0] - 8), SUELO_HUMEDO)
    _bano(d, (vx[1] + 22, y0 + 22, vx[2] - 22, hy[0] - 22))
    if alcobas >= 2:
        _rect(d, (vx[1] + 8, hy[0] + 8, vx[2] - 8, hy[1] - 8), SUELO_HUMEDO)
        _bano(d, (vx[1] + 22, hy[0] + 22, vx[2] - 22, hy[1] - 22))
    else:
        _armario(d, (vx[1] + 28, hy[0] + 30, vx[1] + 76, hy[1] - 30))
        _escritorio(d, (vx[1] + 106, hy[0] + 40, vx[2] - 28, hy[1] - 40))
    _rect(d, (vx[1] + 8, hy[1] + 8, vx[2] - 8, y1 - 8), SUELO_HUMEDO)
    _lavadora(d, (vx[1] + 26, hy[1] + 30, vx[1] + 94, hy[1] + 98))
    _lavadora(d, (vx[1] + 106, hy[1] + 30, vx[1] + 174, hy[1] + 98))
    _armario(d, (vx[1] + 26, y1 - 86, vx[2] - 26, y1 - 30), vertical=False)

    # --- alcobas, la columna de la derecha: una por franja
    franjas = [(y0, hy[0]), (hy[0], hy[1]), (hy[1], y1)]
    for i, (fy0, fy1) in enumerate(franjas):
        cx0 = vx[2] + 30
        _armario(d, (x1 - 74, fy0 + 40, x1 - 32, fy1 - 40))
        if i < alcobas:
            _cama(d, (cx0 + 18, fy0 + 62, x1 - 102, fy1 - 54), doble=(i == 0))
        else:
            _escritorio(d, (cx0, fy0 + 46, x1 - 106, fy1 - 40))

    # --- obra: perimetro, tabiques, puertas y ventanas
    d.line(huella + [huella[0]], fill=MURO, width=GRUESO_MURO, joint="curve")
    for x in vx:
        _tabique(d, x, y0, x, y1)
    for y in hy:
        _tabique(d, x0, y, x1, y)

    _puerta(d, vx[0], y0 + al * 0.14, 96, vertical=True, hacia=1)
    _puerta(d, vx[1], y0 + al * 0.10, 90, vertical=True, hacia=-1)
    _puerta(d, vx[2], y0 + al * 0.12, 96, vertical=True, hacia=-1)
    for y in hy:
        _puerta(d, vx[2] + 44, y, 92, vertical=False, hacia=1)
        _puerta(d, vx[1] + 38, y, 84, vertical=False, hacia=-1)

    for fy0, fy1 in franjas:
        _ventana(d, (x1 - 10, fy0 + 70, x1 + 10, fy1 - 70))
    _ventana(d, (x0 - 10, hy[0] + 56, x0 + 10, hy[1] - 56))
    _ventana(d, (vx[0] + 56, y1 - 10, vx[1] - 56, y1 + 10))

    return im


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    manifiesto = []
    if MANIFIESTO.is_file():
        manifiesto = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    # Se rehacen las nuestras y se respetan las bajadas del catalogo.
    manifiesto = [m for m in manifiesto if not m.get("inventado")]

    for alcobas in (1, 2, 3):
        nombre = "inventado-%dalcobas.png" % alcobas
        dibujar(alcobas).save(DESTINO / nombre)
        manifiesto.append({
            "src": "assets/planos/" + nombre,
            # NO lleva constructora ni proyecto: no es de nadie. Es lo que mira
            # generar_tenants.py para darselas solo a quien no tiene ninguna.
            "id_proyecto": None,
            "proyecto": "Apartamento ilustrativo de %d alcoba%s" % (
                alcobas, "" if alcobas == 1 else "s"),
            "constructora": None,
            "inventado": True,
            "habitaciones": alcobas,
            "localidad": "",
            "vis": alcobas <= 2,
            "origen": "dibujado por app/tools/dibujar_planos.py",
        })
        print("%-26s %d alcoba%s  %dx%d px"
              % (nombre, alcobas, "" if alcobas == 1 else "s", ANCHO, ALTO))

    MANIFIESTO.write_text(json.dumps(manifiesto, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    print("\nmanifiesto: %d laminas (%d dibujadas)"
          % (len(manifiesto), sum(1 for m in manifiesto if m.get("inventado"))))
    print("Siguiente:  python app/tools/analizar_planos.py")
    print("            python plataforma/tools/generar_tenants.py")


if __name__ == "__main__":
    main()
