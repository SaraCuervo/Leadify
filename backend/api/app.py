"""
api/app.py
==========
Capa HTTP sobre recomendar(). Expone el modelo a la landing de Leadify para
el formulario en vivo del stand de GO FEST.

    uvicorn api.app:app --reload --port 8000     # desde backend/

Desplegado en Render (ver render.yaml). CORS abierto a propósito: la
landing y la experiencia embebida son públicas, sin login, y no hay dato
sensible propio que proteger aquí — el que sí importa (la API key de Dapta)
nunca sale de las variables de entorno del servidor.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger("uvicorn.error")

# `backend/` en el path: uvicorn puede arrancarse desde la raíz del repo, y ahí
# `Model` no sería importable sin esto.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Model.catalogos import LOCALIDADES_BOGOTA, ZONAS_COMUNES, indice_localidad
from Model.grafo_barrios import barrios_de_localidad, hay_grafo_barrios
from Model.pipeline import recomendar, respuesta_json

app = FastAPI(title="Leadify Recomendador API", version="0.1")

# URL del webhook del flow de Dapta (Flow Studio) que dispara la llamada de
# Manuela. Vacío -> modo mock: arma el payload y lo devuelve sin llamar a
# nadie. Se llena con `export DAPTA_FLOW_WEBHOOK_URL=...` antes de levantar
# uvicorn, nunca hardcodeado aquí.
DAPTA_FLOW_WEBHOOK_URL = os.environ.get("DAPTA_FLOW_WEBHOOK_URL")

# API key de la cuenta de Dapta dueña del flow. El endpoint del webhook
# responde 401 sin ella (header x-api-key). Se llena con
# `export DAPTA_API_KEY=...` antes de levantar uvicorn, nunca hardcodeada aquí.
DAPTA_API_KEY = os.environ.get("DAPTA_API_KEY")

TZ_BOGOTA = timezone(timedelta(hours=-5))
# El SMMLV se lee de `Model.prep`, que es donde vive el supuesto económico.
# Antes estaba duplicado aquí y el invariante 5 pedía actualizar los dos
# archivos a mano; ahora desfasarlos es imposible.
from Model.prep import SMMLV as SMMLV_COP

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class FormularioUsuario(BaseModel):
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    correo: Optional[str] = None
    telefono: Optional[int] = None
    afiliado: Optional[int] = None
    tipo_vivienda: int
    salario: int
    personas_a_cargo: int
    edad: int
    Localidad: int
    numero_habitaciones: int
    piso: Optional[int] = None
    zonas_comunes: Optional[List[str]] = None
    # Opcional: nombre o código de sector catastral (ver GET /api/barrios).
    # No filtra; afina la distancia con la que el score mide la cercanía.
    barrio: Optional[str] = None


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/catalogos")
def catalogos():
    return {
        "localidades": [{"id": i + 1, "nombre": n} for i, n in enumerate(LOCALIDADES_BOGOTA)],
        "zonas_comunes": ZONAS_COMUNES,
    }


@app.get("/api/barrios")
def barrios(localidad: int):
    """Los barrios (sectores catastrales) de una localidad, para un desplegable
    dependiente. Es la vía para que el front mande un `barrio` que el modelo
    reconozca sin copiarse los 1.164 nombres (invariante 6 del GUIA_TECNICA.md).
    """
    if indice_localidad(localidad) is None:
        raise HTTPException(status_code=400, detail="Localidad debe estar entre 1 y 20")
    return {
        "localidad": localidad,
        "disponible": hay_grafo_barrios(),
        "barrios": [{"id": codigo, "nombre": nombre}
                    for codigo, nombre in barrios_de_localidad(localidad)],
    }


@app.post("/api/recomendar")
def api_recomendar(payload: FormularioUsuario):
    data = payload.model_dump(exclude_none=True)
    try:
        resultado = recomendar(data, ruta_salida=None, verbose=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return respuesta_json(resultado, ruta_salida=None)


def normalizar_telefono_e164(raw: str | None) -> str | None:
    """Mismo criterio que dapta_client.py: E.164 de móvil colombiano o None."""
    if not raw:
        return None
    digitos = re.sub(r"\D", "", str(raw))
    if not digitos:
        return None
    if digitos.startswith("00"):
        digitos = digitos[2:]
    if digitos.startswith("57") and len(digitos) > 10:
        digitos = digitos[2:]
    if len(digitos) == 10 and digitos.startswith("3"):
        return "+57" + digitos
    return None


class ApartamentoLlamada(BaseModel):
    nombre_proyecto: str
    localidad: str
    tipo_vivienda: str
    precio_desde_cop: float
    cuota_mensual_estimada_cop: Optional[float] = None
    aplica_subsidio_caja: bool = False


class SolicitudLlamada(BaseModel):
    nombre: str
    telefono: str
    afiliado: bool
    rango_ingreso: str
    edad: int
    personas_a_cargo: int
    entorno_deseado: str
    apartamento: ApartamentoLlamada


@app.post("/api/llamar")
def api_llamar(payload: SolicitudLlamada):
    telefono_e164 = normalizar_telefono_e164(payload.telefono)
    if not telefono_e164:
        raise HTTPException(
            status_code=400,
            detail="Ese número no parece un móvil colombiano válido (+57 3XXXXXXXXX).",
        )

    apto = payload.apartamento
    subsidio_estimado: float = (
        30 * SMMLV_COP if (apto.aplica_subsidio_caja and payload.afiliado) else 0
    )

    payload_dapta: dict[str, Any] = {
        "nombre": payload.nombre,
        "telefono": telefono_e164,
        "proyecto": apto.nombre_proyecto,
        "tipo_vivienda": apto.tipo_vivienda,
        "current_time": datetime.now(TZ_BOGOTA).strftime("%Y-%m-%d %H:%M"),
        "afiliado": payload.afiliado,
        "rango_ingreso": payload.rango_ingreso,
        "zona_interes": apto.localidad,
        "urgencia": "alta",
        "edad": payload.edad,
        "entorno_deseado": payload.entorno_deseado or "Sin preferencia declarada",
        "personas_a_cargo": payload.personas_a_cargo,
        "piso_preferido": "Sin preferencia",
        "tipo_inmueble": "apartamento",
        "proyecto_recomendado": apto.nombre_proyecto,
        "cuota_estimada_mensual": apto.cuota_mensual_estimada_cop or 0,
        "valor_estimado_vivienda": apto.precio_desde_cop,
        "subsidio_estimado": subsidio_estimado,
        "external_lead_id": f"gofest-{int(datetime.now(TZ_BOGOTA).timestamp())}",
    }

    if not DAPTA_FLOW_WEBHOOK_URL:
        return {
            "status": "mock_enqueued",
            "detalle": "DAPTA_FLOW_WEBHOOK_URL no está configurado — no se llamó a nadie.",
            "payload_enviado": payload_dapta,
        }

    import httpx

    # Se limpia cualquier resultado viejo para este número: si vuelve a llamar
    # (reintento o segunda vuelta), que el polling no devuelva el resumen de la
    # llamada anterior mientras la nueva sigue en curso.
    RESULTADOS_LLAMADAS.pop(telefono_e164, None)

    headers = {"x-api-key": DAPTA_API_KEY} if DAPTA_API_KEY else {}
    with httpx.Client(timeout=20.0) as client:
        r = client.post(DAPTA_FLOW_WEBHOOK_URL, json=payload_dapta, headers=headers)
        r.raise_for_status()
    return {
        "status": "enviado",
        "detalle": f"Manuela está llamando a {telefono_e164}.",
        "telefono": telefono_e164,
    }


# ---------------------------------------------------------------------------
# Paso 3: resumen de la llamada apenas Manuela cuelga.
#
# Dapta empuja el análisis post-llamada por su propio webhook (configurado en
# el agente, campo `webhook_url` — no está en este repo, se pone desde el
# dashboard de Dapta o por MCP). Este backend solo lo recibe, lo guarda en
# memoria por teléfono, y el frontend hace polling corto hasta que aparece.
#
# EN MEMORIA A PROPÓSITO. Un solo proceso, para un stand, sin necesidad de
# sobrevivir un redeploy: una base de datos sería reescribir todo esto para
# un problema que no existe todavía. Se pierde al reiniciar el servicio, y
# está bien que sea así.
#
# CORRELACIÓN POR TELÉFONO, con la misma limitación ya conocida del proyecto
# hermano (Colsubsidio): si dos leads comparten número en la misma ventana de
# tiempo, el resultado puede cruzarse. Para un stand de GO FEST, con tráfico
# bajo y cada quien probando con su propio celular, el riesgo es aceptable.
RESULTADOS_LLAMADAS: dict[str, dict[str, Any]] = {}


def _texto(valor: Any) -> Optional[str]:
    return str(valor) if valor not in (None, "") else None


@app.post("/webhooks/dapta/resultado")
async def webhook_resultado_llamada(request: Request):
    """Receptor del webhook post-call de Dapta (agente Manuela — Leadify).

    Escrito a la defensiva: el payload exacto no está documentado en público
    y no se puede probar sin disparar una llamada real, así que se guarda el
    cuerpo crudo completo (para depurar si algún campo no cruza donde se
    esperaba) y se intentan varias rutas conocidas para cada dato, sacadas de
    lo que sí se ve en list_calls: `custom_analysis_data` puede llegar como
    dict ya parseado o como string JSON dentro de `call_analysis`.
    """
    body = await request.json()
    logger.info("webhook post-call de Dapta: %s", json.dumps(body, ensure_ascii=False)[:4000])

    telefono = _texto(body.get("to_number") or body.get("telefono") or body.get("phone"))
    telefono_e164 = normalizar_telefono_e164(telefono) or telefono
    if not telefono_e164:
        logger.warning("webhook post-call sin to_number reconocible: %s", list(body.keys()))
        return {"status": "ignorado", "detalle": "sin to_number"}

    analisis = body.get("call_analysis")
    if isinstance(analisis, str):
        try:
            analisis = json.loads(analisis)
        except ValueError:
            analisis = {}
    analisis = analisis or {}

    datos = analisis.get("custom_analysis_data") or body.get("custom_analysis_data") or {}
    if isinstance(datos, str):
        try:
            datos = json.loads(datos)
        except ValueError:
            datos = {}

    RESULTADOS_LLAMADAS[telefono_e164] = {
        "listo": True,
        "recibido_en": datetime.now(TZ_BOGOTA).isoformat(),
        "call_status": body.get("call_status"),
        "disconnection_reason": body.get("disconnection_reason"),
        "temperatura_lead": datos.get("temperatura_lead"),
        "resumen_llamada": datos.get("resumen_llamada") or analisis.get("call_summary"),
        "recomendacion_asesor": datos.get("recomendacion_asesor"),
        "estado_del_lead": datos.get("estado_del_lead"),
        "nivel_de_urgencia": datos.get("nivel_de_urgencia"),
        "tomador_de_decision": datos.get("tomador_de_decision"),
        "presupuesto_confirmado": datos.get("presupuesto_confirmado"),
        "fecha_de_seguimiento": datos.get("fecha_de_seguimiento"),
        "objecion_principal": datos.get("objecion_principal"),
    }
    return {"status": "ok"}


@app.get("/api/llamar/resultado")
def api_resultado_llamada(telefono: str):
    telefono_e164 = normalizar_telefono_e164(telefono)
    if not telefono_e164:
        raise HTTPException(status_code=400, detail="Teléfono inválido.")
    return RESULTADOS_LLAMADAS.get(telefono_e164, {"listo": False})
