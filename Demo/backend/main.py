"""
main.py
=======
Punto de entrada del backend por consola.

    python main.py                                  # usa el usuario de ejemplo
    python main.py --usuario mi_usuario.json
    python main.py --top 6 --json

Es un lanzador delgado: toda la lógica vive en `Model/pipeline.py`. Existe
para que la ruta más corta al recomendador siga siendo un archivo en la raíz
del backend, sin obligar a nadie a recordar el nombre del paquete.
"""

from __future__ import annotations

import os
import sys

# `backend/` tiene que estar en el path para que `Model` se importe igual desde
# cualquier directorio de trabajo, no solo desde aquí.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Model.pipeline import main  # noqa: E402

if __name__ == "__main__":
    main()
