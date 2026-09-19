"""Sustituye los hex de marca de css/styles.css por los tokens del `:root`.

POR QUE UN SCRIPT Y NO UN BUSCAR-Y-REEMPLAZAR
---------------------------------------------
Son 224 sustituciones, pero NO todas las apariciones de un hex se pueden
tocar: el bloque de la portada clonada tiene que conservar sus valores
literales. Un reemplazo global las cambiaria todas y el clon dejaria de serlo.

Es de UN SOLO USO. Una vez tokenizado el CSS, este archivo queda como registro
de que se cambio y por que. No hay que volver a correrlo.

QUE SE EXCLUYE, Y POR QUE
-------------------------
1. EL BLOQUE `:root`. Es la definicion de los tokens: sustituir ahi crearia
   `--marca: var(--marca)`.
2. LA PORTADA CLONADA (`.gdf-portada`, `.pt-*`). Es una copia de
   colsubsidio.com y tiene que seguir siendolo. Si tomara los tokens, vestir la
   app de otra marca la deformaria. Son 15 usos.

QUE NO HIZO FALTA EXCLUIR, comprobado antes de escribir esto:
- LA ESCENA DEL PLANO no usa ni un solo color de marca. Su gris es neutro a
  proposito (las piezas van en `mix-blend-mode: multiply`: teñir el fondo
  teñiria el apartamento entero), y resulta que ya lo era.
- NO HAY hex de marca dentro de `url(data:...)`, donde `var()` no se resuelve.
- NO HAY hex de marca dentro de `@keyframes`.

Los tres se verificaron con grep sobre el archivo real. Si alguien introduce
alguno de esos casos mas adelante, este script hay que revisarlo antes de
volver a usarlo.

Uso:
    python tools/tokenizar_css.py            # informe, no escribe
    python tools/tokenizar_css.py --escribir
"""

import argparse
import pathlib
import re
import sys

APP = pathlib.Path(__file__).resolve().parent.parent
CSS = APP / "css" / "styles.css"

# hex -> token. Tabla EXACTA, sin heuristica: si un color no esta aqui, no se
# toca. Los que faltan a proposito son los neutros de UI (#fff, #333, los grises
# de borde), el verde de exito y el naranja del error, que esta fuera de la
# paleta deliberadamente.
MAPA = {
    "#0067b1": "--marca",
    "#003f6b": "--marca-fuerte",
    "#0078c8": "--marca-viva",
    "#4a94cc": "--marca-medio",
    "#7ec0ec": "--marca-suave",
    "#a9d4ef": "--marca-borde",
    "#eaf3fa": "--marca-tinte",
    "#f2f7fb": "--marca-tinte-2",
    "#ffd000": "--acento",
    "#e6bd00": "--acento-oscuro",
    "#fff3b8": "--acento-tinte",
    "#fff8e0": "--acento-tinte-2",
    "#8a6d00": "--sobre-acento",
    "#33322f": "--tinta",
    "#575756": "--tinta-media",
    "#8a8a89": "--tinta-suave",
    "#a0a3a6": "--tinta-tenue",
    # VELOS. Aqui SI se agrupan tonos distintos, y es la unica parte de la tabla
    # que no es 1:1. Son doce tintes casi blancos que el diseño original fue
    # acumulando (#cfe2f0, #cfe3f3, #cfe4f1... todos azules palidos a menos de
    # 4/255 unos de otros), y mantener uno por cada uno seria doce tokens para
    # colores que nadie distingue.
    #
    # El agrupamiento MUEVE pixeles, al reves que el resto del refactor: hasta
    # 8/255 en los rellenos y 16/255 en los bordes, que son de 1px. Es un cambio
    # deliberado y medido, no un descuido — se comprueba con la captura.
    "#cce1ef": "--marca-velo-fuerte",
    "#e4f1fa": "--marca-velo",
    "#dceefc": "--marca-velo",
    "#eef5fb": "--marca-velo-claro",
    "#cfe3f3": "--marca-borde-suave",
    "#cfe4f1": "--marca-borde-suave",
    "#cfe2f0": "--marca-borde-suave",
    "#bfdcf0": "--marca-borde-suave",
    "#fffdf4": "--acento-velo",
    "#fffdf3": "--acento-velo",
    "#fffdf5": "--acento-velo",
    "#fffbe8": "--acento-velo",
}

# Selectores cuyo interior NO se toca.
#
# OJO CON EL ANCLA. La primera version llevaba solo `^:root\b` y NO protegio el
# bloque `:root`: el parseo acumula todo lo que hay desde la ultima llave, asi
# que un comentario justo encima queda pegado delante del selector y `^` deja de
# casar. El resultado fue `--marca: var(--marca)`, una autorreferencia ciclica
# que CSS descarta — y no se noto en pantalla porque js/tema.js reescribe esos
# valores por encima. El clon si se salvo, pero por accidente: lo cubria la
# alternativa `\s\.gdf-portada`.
#
# Ahora `selector_limpio()` quita el comentario antes de comparar, y las
# alternativas con `\s` se quedan como segunda red.
EXCLUIR = re.compile(r"^:root\b|^\.gdf-portada\b|^\.pt-|\s:root\b|\s\.gdf-portada\b|\s\.pt-")

RE_COMENTARIO = re.compile(r"/\*.*?\*/", re.S)


def selector_limpio(sel):
    """El selector sin los comentarios que lo preceden."""
    sin = RE_COMENTARIO.sub(" ", sel)
    # Un comentario sin cerrar (porque el bloque abre en otra linea) deja basura
    # por delante: nos quedamos con lo que hay tras el ultimo cierre.
    if "*/" in sin:
        sin = sin.split("*/")[-1]
    return sin.strip()

RE_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def contextos(lineas):
    """Para cada linea, la pila de selectores que la contienen.

    Hace falta porque el mismo hex se sustituye o no segun DONDE este. El
    parseo es de llaves, no un parser de CSS completo: alcanza porque este
    archivo no tiene llaves dentro de cadenas ni comentarios con llaves
    desbalanceadas (comprobado).
    """
    pila = []
    pendiente = ""
    fuera = []
    for linea in lineas:
        # El selector puede venir repartido en varias lineas ("h1,\nh2,\nh3 {").
        # Se acumula lo que no es cuerpo hasta encontrar la llave.
        resto = linea
        actual = list(pila)
        primero = True
        while resto:
            i_abre = resto.find("{")
            i_cierra = resto.find("}")
            if i_abre < 0 and i_cierra < 0:
                pendiente += " " + resto
                break
            if i_abre >= 0 and (i_cierra < 0 or i_abre < i_cierra):
                sel = selector_limpio(pendiente + " " + resto[:i_abre])
                pendiente = ""
                pila.append(sel)
                if primero:
                    # La linea que ABRE un bloque pertenece al bloque de fuera
                    # para el selector, pero su parte derecha ya es cuerpo.
                    primero = False
                resto = resto[i_abre + 1 :]
                actual = list(pila)
            else:
                pendiente = ""
                if pila:
                    pila.pop()
                resto = resto[i_cierra + 1 :]
                actual = list(pila)
        fuera.append(actual)
    return fuera


def excluida(pila):
    return any(EXCLUIR.search(s or "") for s in pila)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escribir", action="store_true", help="aplica los cambios")
    args = ap.parse_args()

    texto = CSS.read_text(encoding="utf-8")
    lineas = texto.split("\n")
    pilas = contextos(lineas)

    cambios = 0
    saltados = 0
    sin_mapear = {}
    salida = []

    for linea, pila in zip(lineas, pilas):
        if excluida(pila):
            saltados += len(
                [h for h in RE_HEX.findall(linea) if h.lower() in MAPA]
            )
            salida.append(linea)
            continue

        def rep(m):
            nonlocal cambios
            h = m.group(0)
            token = MAPA.get(h.lower())
            if not token:
                sin_mapear[h.lower()] = sin_mapear.get(h.lower(), 0) + 1
                return h
            cambios += 1
            return "var(%s)" % token

        salida.append(RE_HEX.sub(rep, linea))

    print("sustituciones:      %d" % cambios)
    print("saltadas (el clon): %d" % saltados)
    print("\nhex que NO se tocan (neutros de UI, exito, error):")
    for h, n in sorted(sin_mapear.items(), key=lambda kv: -kv[1])[:14]:
        print("  %-10s %d" % (h, n))

    if args.escribir:
        CSS.write_text("\n".join(salida), encoding="utf-8")
        print("\nescrito: %s" % CSS)
    else:
        print("\n(informe: nada escrito; usa --escribir para aplicar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
