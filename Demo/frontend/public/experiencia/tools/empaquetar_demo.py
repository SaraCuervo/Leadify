#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Empaqueta la app entera en UN SOLO archivo HTML, para poder compartirla por
link. Uso:

    pip install pillow
    python tools/empaquetar_demo.py            # escribe dist/grua-del-futuro.html

ESTO NO ES UN BUILD STEP DE LA APP. app/ sigue funcionando tal cual abriendo
index.html con cualquier servidor estatico; este script solo produce una copia
autocontenida para enviar a alguien. Si se rompe, la app no se entera.

POR QUE UN SOLO ARCHIVO
-----------------------
El visor donde se publica el link aplica una politica de seguridad que bloquea
CUALQUIER peticion externa: nada de <script src>, <link href>, fuentes, ni
fetch. Asi que todo -CSS, JS, imagenes y tipografias- tiene que ir embebido.
Por lo mismo se fuerza SIN_BACKEND (ver js/config.js): sin eso el recorrido
terminaria en la pantalla de error de red al confirmar.

PESO
----
El limite es 16 MB YA RENDERIZADO, y base64 infla un 33%. Las imagenes en
crudo son 16 MB (12 de planos), asi que se reencodan a WebP: con CALIDAD_* de
abajo quedan en ~4 MB -> ~5,5 MB en base64. Los planos son la pieza central de
la animacion del quiz, asi que van con mas calidad que las fotos de portada.
"""

from __future__ import annotations

import argparse
import base64
import io
import mimetypes
import os
import re
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("Falta Pillow:  pip install pillow")
    sys.exit(1)

AQUI = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(AQUI)
RAIZ = os.path.dirname(APP)
SALIDA = os.path.join(RAIZ, "dist", "grua-del-futuro.html")

# Los planos se ven a ~700px de ancho en la escena del quiz; las fotos de
# portada, a ~400px en la tarjeta. De ahi la diferencia de trato.
CALIDAD_PLANOS, ANCHO_PLANOS = 72, 740
CALIDAD_FOTOS, ANCHO_FOTOS = 68, 700

RE_CSS = re.compile(r'<link rel="stylesheet" href="([^"]+)"\s*/?>')
RE_JS = re.compile(r'<script src="([^"]+)"></script>')
RE_URL_CSS = re.compile(r"url\((['\"]?)(assets/[^)'\"]+)\1\)")
# En el JS las rutas viajan como cadenas: 'assets/planos/x.webp'
RE_URL_JS = re.compile(r"(['\"])(assets/[^'\"]+\.(?:webp|png|jpe?g|svg))\1")

# Catalogos GENERADOS: sus rutas las cambia el resolutor en tiempo de
# ejecucion, no aqui, porque se repiten cientos de veces (ver mas abajo).
GENERADOS = ("proyectos.js", "planos.js", "portada.js")


def sin_query(ruta: str) -> str:
    return ruta.split("?")[0]


def js_str(s: str) -> str:
    """Literal JS entre comillas simples. `</script>` dentro de una cadena
    cerraria la etiqueta antes de tiempo, de ahi el escape de la barra."""
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'").replace("</", "<\\/") + "'"


def como_data_uri(rel: str, cache: dict) -> str:
    """La imagen, reencodada y en base64. Cachea: el mismo plano sale en
    varias tipologias y embeberlo dos veces duplicaria su peso."""
    if rel in cache:
        return cache[rel]
    abs_ = os.path.join(APP, rel.replace("/", os.sep))
    if not os.path.exists(abs_):
        cache[rel] = rel
        return rel

    ext = os.path.splitext(rel)[1].lower()
    crudo = lambda: (
        open(abs_, "rb").read(),
        mimetypes.guess_type(abs_)[0] or "application/octet-stream",
    )
    if ext == ".svg":
        datos, mime = open(abs_, "rb").read(), "image/svg+xml"
    else:
        try:
            calidad, ancho = (
                (CALIDAD_PLANOS, ANCHO_PLANOS) if "/planos/" in rel else (CALIDAD_FOTOS, ANCHO_FOTOS)
            )
            im = Image.open(abs_)
            # Los iconos llevan transparencia; las fotos y planos no.
            modo = "RGBA" if im.mode in ("RGBA", "LA", "P") and "iconos" in rel else "RGB"
            im = im.convert(modo)
            if im.size[0] > ancho:
                alto = int(round(ancho * im.size[1] / im.size[0]))
                im = im.resize((ancho, alto), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=calidad, method=6)
            datos, mime = buf.getvalue(), "image/webp"
        except Exception:
            # Tres PNG del logo vienen truncados y PIL no los abre, pero el
            # navegador si los pinta. Se copian tal cual en vez de "arreglar"
            # unos assets que no son de este script.
            datos, mime = crudo()
            print("   (sin reencodar, se copia tal cual: %s)" % rel)

    uri = "data:%s;base64,%s" % (mime, base64.b64encode(datos).decode("ascii"))
    cache[rel] = uri
    return uri


def inlinear_assets(texto: str, patron: re.Pattern, cache: dict, grupo: int) -> str:
    def cambia(m):
        rel = m.group(grupo)
        uri = como_data_uri(rel, cache)
        if patron is RE_URL_CSS:
            return "url('%s')" % uri
        return "%s%s%s" % (m.group(1), uri, m.group(1))

    return patron.sub(cambia, texto)


def leer(rel: str) -> str:
    with open(os.path.join(APP, sin_query(rel).replace("/", os.sep)), encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default=SALIDA)
    args = ap.parse_args()

    html = leer("index.html")
    cache: dict = {}

    print("1) CSS...")
    def mete_css(m):
        css = leer(m.group(1))
        css = inlinear_assets(css, RE_URL_CSS, cache, 2)
        return "<style>\n%s\n</style>" % css
    html = RE_CSS.sub(mete_css, html)

    scripts = RE_JS.findall(html)
    print("2) JS (%d archivos)..." % len(scripts))

    # En el JS las rutas NO se sustituyen en el sitio. Cada icono sale citado
    # decenas de veces en el catalogo (810 apariciones para 82 archivos), asi
    # que pegar el data URI en cada una multiplicaba el peso por cinco. En vez
    # de eso se emite un diccionario con cada asset UNA vez y un resolutor que
    # recorre el catalogo ya cargado y cambia las rutas por sus data URI. Todo
    # lo de aguas abajo (plantillas, planta.js) recibe el valor ya sustituido.
    fuentes = {}
    usados = set()
    for ruta in scripts:
        js = leer(ruta)
        # La copia que se comparte no puede tocar la red (ver el docstring).
        if ruta.startswith("js/config.js"):
            js = js.replace("SIN_BACKEND: false", "SIN_BACKEND: true")
        fuentes[ruta] = js
        for _, rel in RE_URL_JS.findall(js):
            if os.path.exists(os.path.join(APP, rel.replace("/", os.sep))):
                usados.add(rel)

    # Las rutas que estan ESCRITAS A MANO en el codigo (el logo de la cabecera,
    # la marca del avatar) no las alcanza el resolutor: este recorre los
    # OBJETOS del catalogo, y esas viven como literales dentro de funciones de
    # plantilla. Se sustituyen aqui, en el sitio.
    #
    # Solo en los modulos que NO son catalogo generado, y la diferencia es
    # brutal: templates.js cita 5 assets y data.js 20, pero proyectos.js cita
    # 991 y planos.js 196. Sustituir en el sitio esos dos multiplicaria el peso
    # del archivo por cinco — por eso existe el resolutor.
    for ruta in list(fuentes):
        if any(ruta.startswith("js/" + g) for g in GENERADOS):
            continue
        fuentes[ruta] = inlinear_assets(fuentes[ruta], RE_URL_JS, cache, 2)

    print("   %d assets distintos referenciados desde el JS" % len(usados))
    mapa = ",\n".join(
        "%s: %s" % (js_str(rel), js_str(como_data_uri(rel, cache))) for rel in sorted(usados)
    )
    resolutor = (
        "<script>\n"
        "// GENERADO por tools/empaquetar_demo.py — solo existe en la copia de un\n"
        "// archivo. Cambia las rutas 'assets/...' del catalogo por su data URI,\n"
        "// una sola vez y antes de que main.js pinte nada.\n"
        "(function () {\n"
        "  var A = {\n" + mapa + "\n  };\n"
        "  function pasar(o, prof) {\n"
        "    if (!o || typeof o !== 'object' || prof > 8) return;\n"
        "    Object.keys(o).forEach(function (k) {\n"
        "      var v = o[k];\n"
        "      if (typeof v === 'string') { if (A[v]) o[k] = A[v]; }\n"
        "      else pasar(v, prof + 1);\n"
        "    });\n"
        "  }\n"
        "  pasar(window.GDF_PROYECTOS, 0);\n"
        "  pasar(window.GDF_PORTADA, 0);\n"
        "  pasar(window.GDF.data, 0);\n"
        "  // Los planos del quiz no bastan con `pasar`: GDF_PLANOS esta indexado\n"
        "  // POR RUTA (la ruta es la CLAVE, no un valor) y planta.js pinta la\n"
        "  // escena con esa misma cadena. Cambiando solo los valores, la tabla\n"
        "  // seguia respondiendo pero el CSS pedia un archivo que en el archivo\n"
        "  // unico no existe: el quiz salia SIN PLANO. Hay que cambiar las CLAVES\n"
        "  // y las dos listas a la vez, para que sigan cuadrando entre si y con\n"
        "  // el catalogo (indicePlanos cruza por src).\n"
        "  if (window.GDF_PLANOS) {\n"
        "    var T = {};\n"
        "    Object.keys(window.GDF_PLANOS).forEach(function (k) {\n"
        "      T[A[k] || k] = window.GDF_PLANOS[k];\n"
        "    });\n"
        "    window.GDF_PLANOS = T;\n"
        "  }\n"
        "  ['GDF_PLANOS_RECTOS', 'GDF_PLANOS_APTOS'].forEach(function (n) {\n"
        "    if (window[n]) window[n] = window[n].map(function (s) { return A[s] || s; });\n"
        "  });\n"
        "})();\n"
        "</script>"
    )

    def mete_js(m):
        ruta = m.group(1)
        bloque = "<script>\n%s\n</script>" % fuentes[ruta]
        # El resolutor va JUSTO ANTES de main.js: para entonces el catalogo ya
        # esta cargado y main.js todavia no ha renderizado.
        return (resolutor + "\n" + bloque) if ruta.startswith("js/main.js") else bloque

    html = RE_JS.sub(mete_js, html)

    # Las fuentes de Google no se pueden pedir: se quita el <link> y la app cae
    # a la pila de respaldo que ya declara cada regla CSS.
    html = re.sub(r'<link rel="preconnect"[^>]*>\s*', "", html)
    html = re.sub(r"<link\s+href=\"https://fonts\.googleapis[^>]*>", "", html, flags=re.S)

    # Rutas que quedarian rotas al abrir el archivo suelto. NO basta con
    # buscar 'assets/...' en el HTML: las del JS siguen ahi A PROPOSITO, en
    # texto, porque quien las cambia por su data URI es el resolutor en tiempo
    # de ejecucion (ver arriba). Contarlas daba una alarma de 300 rutas en
    # cada build que no significaba nada. Lo que si importa es una ruta que
    # exista en disco y que NADIE vaya a resolver: ni la inlino el paso de CSS
    # (`cache`) ni esta en el mapa del resolutor (`usados`).
    resueltas = set(usados) | {k for k, v in cache.items() if v}
    sueltas = [
        r for r in sorted(set(re.findall(r"assets/[\w\-./]+\.\w+", html)))
        if os.path.exists(os.path.join(APP, r.replace("/", os.sep))) and r not in resueltas
    ]
    if sueltas:
        print("   OJO: %d rutas reales quedaron sin embeber: %s" % (len(sueltas), sueltas[:5]))

    os.makedirs(os.path.dirname(args.salida), exist_ok=True)
    with open(args.salida, "w", encoding="utf-8") as fh:
        fh.write(html)

    mb = os.path.getsize(args.salida) / 1e6
    print("3) escrito %s  (%.1f MB, %d imagenes embebidas)" % (args.salida, mb, len(cache)))
    if mb > 15:
        print("   OJO: cerca del limite de 16 MB. Baja CALIDAD_PLANOS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
