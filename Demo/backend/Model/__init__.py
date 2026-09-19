"""
Model
=====
El recomendador de Machea. Todo lo que decide qué proyecto se le muestra a
quién vive aquí dentro; `api/` solo lo expone por HTTP y `scraping/` solo lo
alimenta (invariante 8 del CLAUDE.md).

Orden del pipeline:

    catalogos.py    vocabularios canónicos + el grafo urbano
    prep.py         catálogo crudo -> perfil objetivo de cada proyecto
    modelo.py       filtro duro + Nearest Neighbors + porcentaje comercial
    cota_minima.py  Cota_minimaBG: el precio y el esfuerzo de pago reordenan
    pipeline.py     encadena las etapas y expone `recomendar()`

Uso típico desde fuera del paquete:

    from Model import recomendar, respuesta_json
"""

from Model.pipeline import recomendar, respuesta_json          # noqa: F401
from Model.modelo import TOP_N, MINIMO_PRESELECCIONADOS        # noqa: F401
from Model.cota_minima import Cota_minimaBG                    # noqa: F401

__all__ = [
    "recomendar",
    "respuesta_json",
    "Cota_minimaBG",
    "TOP_N",
    "MINIMO_PRESELECCIONADOS",
]
