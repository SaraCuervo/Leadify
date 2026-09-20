# -*- coding: utf-8 -*-
"""Prueba de humo del motor de recomendación.

No mide la calidad de lo que recomienda —para eso están `evaluar.py` y los
calibradores de `Model/simulacion/`— sino que el recorrido completo no se
rompió: que los datos cargan, que `recomendar()` responde y que la respuesta
cumple el contrato que el front espera.

Se corre desde `Demo/backend/`:

    python pruebas/prueba_humo.py

Devuelve 0 si todo pasa y 1 si algo falla, para que sirva en la verificación
automática (.github/workflows/verificacion.yml).
"""
from __future__ import annotations

import os
import sys

# `Demo/backend/` tiene que estar en el path para que `Model` se importe igual
# desde cualquier directorio de trabajo.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from Model import recomendar, respuesta_json  # noqa: E402
from Model.catalogos import LOCALIDADES_BOGOTA, ZONAS_COMUNES  # noqa: E402

TOP_ESPERADO = 18

# El formulario mínimo del contrato: los seis campos obligatorios. Se usa el
# mínimo a propósito, porque es el caso que más fácil se rompe cuando alguien
# agrega un campo y olvida darle un valor por defecto.
FORMULARIO_MINIMO = {
    "tipo_vivienda": 1,
    "salario": 2,
    "personas_a_cargo": 3,
    "edad": 34,
    "Localidad": 7,
    "numero_habitaciones": 3,
}

# Uno completo, con los campos que solo aporta la persona.
FORMULARIO_COMPLETO = dict(
    FORMULARIO_MINIMO,
    nombres="Ana",
    apellidos="Torres",
    correo="ana@ejemplo.com",
    telefono=3009998877,
    afiliado=1,
    piso=1,
    zonas_comunes=["Lobby", "Zona kids", "Parque", "Gimnasio"],
)

fallos: list[str] = []


def revisar(condicion: bool, mensaje: str) -> None:
    if condicion:
        print("  ok   %s" % mensaje)
    else:
        print("  FALLA %s" % mensaje)
        fallos.append(mensaje)


def main() -> int:
    print("1. Vocabularios canónicos")
    revisar(len(LOCALIDADES_BOGOTA) == 20, "las 20 localidades de Bogotá")
    revisar(len(ZONAS_COMUNES) == 25, "las 25 zonas comunes")

    print("2. El motor responde al formulario mínimo")
    resultado = recomendar(FORMULARIO_MINIMO, ruta_salida=None, verbose=False)
    payload = respuesta_json(resultado, ruta_salida=None)
    apartamentos = payload["apartamentos"]
    revisar(len(apartamentos) == TOP_ESPERADO,
            "devuelve %d proyectos (devolvió %d)" % (TOP_ESPERADO, len(apartamentos)))
    revisar(payload.get("motor") in ("colaborativo+contenido", "contenido"),
            "declara con qué motor recomendó: %r" % payload.get("motor"))

    print("3. El contrato de cada proyecto")
    obligatorios = ("posicion", "compatibilidad", "id_proyecto", "nombre_proyecto",
                    "tipo_vivienda", "localidad")
    faltantes = {c for a in apartamentos for c in obligatorios if c not in a}
    revisar(not faltantes, "todos traen los campos del contrato (faltan: %s)" % sorted(faltantes))

    porcentajes = [a["compatibilidad"] for a in apartamentos]
    revisar(all(0 <= p <= 100 for p in porcentajes),
            "los porcentajes caen entre 0 y 100")
    revisar(len(set(porcentajes)) == len(porcentajes),
            "ningún porcentaje se repite: dos iguales dejan al usuario sin criterio")
    revisar(porcentajes == sorted(porcentajes, reverse=True),
            "los porcentajes bajan con la posición")

    ids = [a["id_proyecto"] for a in apartamentos]
    revisar(len(set(ids)) == len(ids), "ningún proyecto sale dos veces")

    print("4. El tipo de vivienda no se relaja nunca")
    revisar(all(a["tipo_vivienda"] == "VIS" for a in apartamentos),
            "se pidió VIS y todos los recomendados son VIS")

    print("5. El formulario completo, con zonas comunes y afiliación")
    completo = respuesta_json(
        recomendar(FORMULARIO_COMPLETO, ruta_salida=None, verbose=False),
        ruta_salida=None,
    )
    revisar(len(completo["apartamentos"]) == TOP_ESPERADO,
            "también devuelve %d proyectos" % TOP_ESPERADO)
    revisar(completo["usuario"]["nombre_completo"] == "Ana Torres",
            "los datos de contacto viajan a la respuesta")

    print("6. Es determinista: el mismo formulario da el mismo resultado")
    otra = respuesta_json(
        recomendar(FORMULARIO_MINIMO, ruta_salida=None, verbose=False),
        ruta_salida=None,
    )
    revisar([a["id_proyecto"] for a in otra["apartamentos"]] == ids,
            "dos corridas seguidas devuelven el mismo orden")

    print()
    if fallos:
        print("FALLARON %d comprobaciones:" % len(fallos))
        for f in fallos:
            print("  - %s" % f)
        return 1
    print("Todo en orden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
