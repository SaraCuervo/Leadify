"""
main.py
=======
Flujo principal del recomendador de proyectos inmobiliarios.

    python main.py --usuario usuario_ejemplo.json

Encadena las cuatro etapas de `modelo.py` y deja el resultado en
`proyectos_listos_llamativos.json`. `recomendar()` es la función que debe
invocar la capa HTTP (FastAPI/Flask) cuando se exponga como servicio.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# Ejecutable por ruta (`python Model/pipeline.py`) o como módulo
# (`python -m Model.pipeline`): en el primer caso Python pone en el path esta
# carpeta y no `backend/`, así que el paquete `Model` no se encontraría.
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Model import prep
from Model.cota_minima import COTA_MINIMA_COP, Cota_minimaBG
from Model.modelo import (
    MINIMO_PRESELECCIONADOS,
    RUTA_HISTORIAL,
    RUTA_LLAMATIVOS,
    RUTA_MODELO,
    TOP_N,
    leer_info_user,
    modelo,
    post_arreglos,
    primer_filtro,
)

from Model.rutas import RUTA_RESPUESTA, RUTA_USUARIO_DEMO, asegurar_salidas


def recomendar(path_user_info, ruta_modelo=RUTA_MODELO, ruta_historial=RUTA_HISTORIAL,
               top_n=TOP_N, semilla=None, ruta_salida=RUTA_LLAMATIVOS, preparar=False,
               verbose=True, cota_cop=COTA_MINIMA_COP):
    """Ejecuta el pipeline completo y devuelve todas las etapas intermedias.

    Es la función que debe invocar la capa HTTP.

    Args:
        path_user_info: el formulario del usuario, como dict (el payload que
            manda el front), como string JSON o como ruta a un archivo.
        preparar: fuerza la regeneración de `proyectos_model.json` desde el seed.
        cota_cop: diferencia de precio a partir de la cual `Cota_minimaBG`
            invierte dos posiciones del top aunque eso saque al usuario de la
            localidad que pidió. `None` desactiva esa capa.

    Returns:
        dict con las llaves usuario_modelo, usuario_segmentado,
        usuario_info_contacto_v1, proyectos_preseleccionados,
        proyectos_seleccionados y proyectos_listos_llamativos.
    """
    if preparar or not os.path.exists(ruta_modelo):
        # `verbose` se propaga para que `--json` no ensucie la salida estándar.
        prep.preparar(ruta_salida=ruta_modelo, verbose=verbose)

    # Etapa A: leer y partir la información del usuario.
    usuario_modelo, usuario_segmentado, usuario_info_contacto_v1 = leer_info_user(path_user_info)

    # Etapa B: filtro duro + expansión por el grafo de localidades.
    # El mínimo nunca puede quedar por debajo del top pedido: si se llama con
    # `--top` grande, el filtro tiene que traer al menos esa cantidad o el
    # Top N saldría corto.
    proyectos_preseleccionados = primer_filtro(
        usuario_segmentado, ruta_modelo=ruta_modelo,
        minimo=max(MINIMO_PRESELECCIONADOS, top_n),
    )

    # Etapa C: Nearest Neighbors -> top N con score.
    # Un afiliado a la caja que busca VIS accede al subsidio, y eso baja el
    # ingreso que el proyecto le exige: se compara contra
    # `salario_objetivo_con_subsidio`. Hasta ahora `afiliado` se capturaba en
    # el formulario y no se usaba para nada.
    usar_subsidio = bool(usuario_info_contacto_v1["afiliado"]) and \
        usuario_segmentado["tipo_vivienda"] == 1
    proyectos_seleccionados = modelo(
        proyectos_preseleccionados,
        usuario_modelo,
        ruta_historial=ruta_historial,
        top_n=top_n,
        usar_subsidio=usar_subsidio,
    )

    # Etapa D: la cota de precio y el esfuerzo de pago reordenan el top.
    # Va DESPUÉS del modelo y ANTES del porcentaje comercial: el porcentaje
    # tiene que describir el orden definitivo, no uno que todavía va a cambiar.
    proyectos_seleccionados = Cota_minimaBG(
        proyectos_seleccionados,
        usuario_modelo,
        cota_cop=cota_cop,
        usar_subsidio=usar_subsidio,
        verbose=verbose,
    )

    # Etapa E: normalización comercial del score.
    proyectos_listos_llamativos = post_arreglos(
        proyectos_seleccionados, semilla=semilla, ruta_salida=ruta_salida
    )

    return {
        "usuario_modelo": usuario_modelo,
        "usuario_segmentado": usuario_segmentado,
        "usuario_info_contacto_v1": usuario_info_contacto_v1,
        "proyectos_preseleccionados": proyectos_preseleccionados,
        "proyectos_seleccionados": proyectos_seleccionados,
        "proyectos_listos_llamativos": proyectos_listos_llamativos,
    }


# ---------------------------------------------------------------------------
# Respuesta JSON
# ---------------------------------------------------------------------------
def respuesta_json(resultado, ruta_salida=RUTA_RESPUESTA):
    """Arma el payload final con los apartamentos recomendados.

    Es la forma en que la capa HTTP debería devolver el resultado: solo los
    campos que la vista necesita, sin la metadata interna del pipeline (esa
    queda completa en `proyectos_listos_llamativos.json`).
    """
    contacto = resultado["usuario_info_contacto_v1"]
    segmentado = resultado["usuario_segmentado"]
    seleccionados = resultado["proyectos_seleccionados"]

    apartamentos = [{
        "posicion": p["posicion"],
        "compatibilidad": p["porcentaje_compatibilidad"],
        "compatibilidad_texto": p["porcentaje_texto"],
        "id_proyecto": p["id_proyecto"],
        "nombre_proyecto": p["nombre_proyecto"],
        "tipo_vivienda": p["tipo_vivienda"],
        "localidad": p["localidad"],
        # El sector catastral del proyecto y, si el usuario dio barrio, a
        # cuantos km queda por el grafo de barrios. `distancia_km_estimada`
        # avisa cuando el proyecto no tiene barrio y el numero es el tipico
        # de su salto de localidad, no una medida.
        "barrio": p.get("barrio_nombre"),
        "distancia_km": p.get("_distancia_km"),
        "distancia_km_estimada": p.get("_distancia_km_estimada", False),
        "direccion": p["direccion"],
        "precio_desde_cop": p["precio_desde_cop"],
        "area_construida_m2": p["area_construida_m2"],
        "habitaciones": p["habitaciones_cod"],
        "cumple_habitaciones": p["_cumple_habitaciones"],
        "aplica_subsidio_caja": p["aplica_subsidio_caja"],
        "cuota_mensual_estimada_cop": p["cuota_mensual_estimada_cop"],
        "ingreso_requerido_smmlv": p["ingreso_requerido_smmlv"],
        # Lo que aporta `Cota_minimaBG`: el esfuerzo de pago de ESTA persona
        # sobre ESTE proyecto. `anos_de_pago` en null significa que con su
        # tramo de ingreso la cuota no cubre ni los intereses — es un dato
        # para decir, no para esconder.
        "anos_de_pago": p.get("_anos_de_pago"),
        "alcanzable": p.get("_alcanzable"),
        "cuota_que_puede_pagar_cop": p.get("_cuota_que_puede_pagar_cop"),
        "cuota_del_proyecto_cop": p.get("_cuota_del_proyecto_cop"),
        "movido_por_cota": p.get("_movido_por_cota", 0),
        "zonas_comunes": p["zonas_comunes"],
        "zonas_en_comun": p["_zonas_coincidentes_nombres"],
        "url_ficha": p["url_ficha"],
        # Los proyectos que publican dos constructoras traen la segunda ficha:
        # la vista debe poder ofrecer las dos, porque el precio difiere.
        "fichas_alternas": p.get("links_alternos") or [],
        "constructoras": p.get("constructoras") or [],
        # Lo que la constructora no publica, dicho de frente en vez de
        # mostrarse como un cero que parecería un dato real.
        "datos_no_publicados": p.get("_dato_incompleto") or [],
        "score": p["score"],
    } for p in resultado["proyectos_listos_llamativos"]]

    payload = {
        "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "motor": seleccionados[0]["motor"] if seleccionados else None,
        "total_preseleccionados": len(resultado["proyectos_preseleccionados"]),
        "usuario": {
            "nombre_completo": contacto["nombre_completo"],
            "correo": contacto["correo"],
            "telefono": contacto["telefono"],
            "afiliado": contacto["afiliado"],
            "perfil": resultado["usuario_modelo"],
            "busqueda": {
                "tipo_vivienda": segmentado["tipo_vivienda_nombre"],
                "localidad": segmentado["localidad_nombre"],
                "barrio": segmentado.get("barrio_nombre"),
                "barrio_no_reconocido": contacto.get("barrio_no_reconocido"),
                "numero_habitaciones": segmentado["numero_habitaciones"],
                "piso": contacto["piso_nombre"],
                "zonas_comunes": segmentado["zonas_comunes_nombres"],
            },
        },
        "apartamentos": apartamentos,
    }

    if ruta_salida:
        asegurar_salidas()
        with open(ruta_salida, "w", encoding="utf-8") as archivo:
            json.dump(payload, archivo, ensure_ascii=False, indent=2)
    return payload


# ---------------------------------------------------------------------------
# Reporte por consola
# ---------------------------------------------------------------------------
def imprimir_reporte(resultado, ruta_salida=RUTA_LLAMATIVOS):
    contacto = resultado["usuario_info_contacto_v1"]
    segmentado = resultado["usuario_segmentado"]
    usuario = resultado["usuario_modelo"]
    preseleccionados = resultado["proyectos_preseleccionados"]
    llamativos = resultado["proyectos_listos_llamativos"]

    print("\n" + "=" * 78)
    print(f" USUARIO: {contacto['nombre_completo']}  <{contacto['correo']}>")
    print("=" * 78)
    print(f" Perfil modelo   : salario={usuario['salario']}  "
          f"personas_a_cargo={usuario['personas_a_cargo']}  edad={usuario['edad']}")
    barrio = (f", barrio {segmentado['barrio_nombre']}" if segmentado.get("barrio_nombre") else "")
    print(f" Busca           : {segmentado['tipo_vivienda_nombre']} en "
          f"{segmentado['localidad_nombre']} ({segmentado['localidad']}){barrio}")
    if contacto.get("barrio_no_reconocido"):
        print(f" AVISO           : barrio no reconocido -> {contacto['barrio_no_reconocido']!r}")
    print(f" Habitaciones    : {segmentado['numero_habitaciones']}+   "
          f"Piso: {contacto['piso_nombre']}   Afiliado: {'sí' if contacto['afiliado'] else 'no'}")
    print(f" Zonas comunes   : {', '.join(segmentado['zonas_comunes_nombres']) or '(ninguna)'}")
    if contacto["zonas_comunes_no_reconocidas"]:
        print(f" AVISO           : zonas no reconocidas -> {contacto['zonas_comunes_no_reconocidas']}")

    print("-" * 78)
    exactos = sum(1 for p in preseleccionados if p["_distancia_localidad"] == 0)
    distancia_max = max((p["_distancia_localidad"] for p in preseleccionados), default=0)
    sin_zonas = sum(1 for p in preseleccionados if p["_nivel_relajacion"] == 2)
    sin_habitaciones = sum(1 for p in preseleccionados if p["_nivel_relajacion"] == 3)
    print(f" PRIMER FILTRO   : {len(preseleccionados)} proyectos preseleccionados")
    print(f"   en la localidad solicitada : {exactos}")
    print(f"   expansión del grafo hasta  : {distancia_max} salto(s)")
    if sin_zonas:
        print(f"   relajado (sin match de zonas)      : {sin_zonas}")
    if sin_habitaciones:
        print(f"   relajado (menos habitaciones)      : {sin_habitaciones}")

    motor = resultado["proyectos_seleccionados"][0]["motor"] if resultado["proyectos_seleccionados"] else "-"
    print(f" MODELO          : Nearest Neighbors | motor = {motor}")
    print("-" * 78)
    print(f" TOP {len(llamativos)} RECOMENDACIONES")
    print("-" * 78)
    for proyecto in llamativos:
        print(f" {proyecto['posicion']}. {proyecto['porcentaje_texto']:>4}  "
              f"{proyecto['nombre_proyecto']}  ({proyecto['id_proyecto']})")
        aviso_hab = "" if proyecto["_cumple_habitaciones"] else "  <- menos hab. de las pedidas"
        km = proyecto.get("_distancia_km")
        cerca = ("" if km is None else
                 f" · a {km:.1f} km{' (est.)' if proyecto.get('_distancia_km_estimada') else ''}")
        lugar = f"{proyecto['localidad']}" + (f" / {proyecto['barrio_nombre']}" if proyecto.get("barrio_nombre") else "")
        print(f"        {lugar}{cerca} · {proyecto['tipo_vivienda']} · "
              f"{proyecto['area_construida_m2']} m² · "
              f"{proyecto['habitaciones_cod']} hab · "
              f"${proyecto['precio_desde_cop']:,.0f} COP".replace(",", ".") + aviso_hab)
        anos = proyecto.get("_anos_de_pago")
        esfuerzo = ("no alcanza" if anos is None
                    else f"{anos:.1f} anos".replace(".", ","))
        movido = proyecto.get("_movido_por_cota", 0)
        aviso_cota = f"   <- la cota lo subio {movido}" if movido > 0 else (
            f"   <- la cota lo bajo {-movido}" if movido < 0 else "")
        print(f"        pagaria en: {esfuerzo}  "
              f"(cuota proyecto ${proyecto.get('_cuota_del_proyecto_cop', 0):,.0f} vs. "
              f"puede ${proyecto.get('_cuota_que_puede_pagar_cop', 0):,.0f})"
              .replace(",", ".") + aviso_cota)
        print(f"        score={proyecto['score']}  (perfil={proyecto['score_afinidad_perfil']} "
              f"esfuerzo={proyecto.get('score_esfuerzo')} "
              f"zonas={proyecto['score_zonas']} localidad={proyecto['score_localidad']})")
        print(f"        zonas en común: "
              f"{', '.join(proyecto['_zonas_coincidentes_nombres']) or '(ninguna)'}")
    print("-" * 78)
    print(f" Guardado en: {os.path.basename(ruta_salida)}\n")


def main():
    # La consola de Windows suele no venir en UTF-8; evita que un acento
    # rompa el reporte.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="Recomendador de proyectos inmobiliarios.")
    parser.add_argument("--usuario", default=RUTA_USUARIO_DEMO,
                        help="Ruta del JSON con la información del usuario.")
    parser.add_argument("--modelo", default=RUTA_MODELO,
                        help="Ruta de proyectos_model.json.")
    parser.add_argument("--historial", default=RUTA_HISTORIAL,
                        help="Ruta del histórico simulado de interacciones.")
    parser.add_argument("--salida", default=RUTA_LLAMATIVOS,
                        help="Ruta del JSON final de recomendaciones.")
    parser.add_argument("--top", type=int, default=TOP_N, help="Cantidad de recomendaciones.")
    parser.add_argument("--semilla", type=int, default=None,
                        help="Semilla del porcentaje aleatorio (reproducibilidad).")
    parser.add_argument("--preparar", action="store_true",
                        help="Regenera proyectos_model.json desde el seed antes de recomendar.")
    parser.add_argument("--json", action="store_true",
                        help="Imprime solo el JSON de apartamentos (para consumo por API).")
    parser.add_argument("--respuesta", default=RUTA_RESPUESTA,
                        help="Ruta del JSON de respuesta con los apartamentos.")
    args = parser.parse_args()

    resultado = recomendar(
        args.usuario,
        ruta_modelo=args.modelo,
        ruta_historial=args.historial,
        top_n=args.top,
        semilla=args.semilla,
        ruta_salida=args.salida,
        preparar=args.preparar,
        verbose=not args.json,
    )
    payload = respuesta_json(resultado, ruta_salida=args.respuesta)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        imprimir_reporte(resultado, ruta_salida=args.salida)
        print(f" Apartamentos en JSON: {os.path.basename(args.respuesta)}\n")
    return payload


if __name__ == "__main__":
    main()
